"""Phase 1 verification: print a full OpenRTB auction trace and an accelerated delivery
curve, entirely from the pure engine. Run from backend/:

    .venv/Scripts/python scripts/demo_auction.py
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adsim.dsp.campaign import Line, Targeting  # noqa: E402
from app.adsim.materialize import sampled_auction  # noqa: E402
from app.adsim.metrics.kpis import rollup  # noqa: E402
from app.adsim.models.creative import NativeCreative  # noqa: E402
from app.adsim.models.enums import BillingEvent, Objective, Pacing  # noqa: E402
from app.adsim.money import micros_to_usd, usd_to_micros  # noqa: E402
from app.adsim.simulation.delivery import run_tick  # noqa: E402
from app.adsim.simulation.state import DeliveryState  # noqa: E402
from app.adsim.world import load_world  # noqa: E402


def money(m: int) -> str:
    return f"${micros_to_usd(m):.2f}"


def main() -> None:
    world = load_world()
    creative = NativeCreative(
        title="Meet the new Nimbus X",
        body="Fast, quiet, unreasonably good.",
        cta_text="Shop now",
        brand_name="Nimbus",
        main_image_key="stock/nimbus.jpg",
        link_url="https://nimbus.example/x",
    )
    line = Line(
        ad_id="ad-001", ad_set_id="set-001", campaign_id="camp-001",
        account_id="acct-nimbus", seat="acct-nimbus",
        objective=Objective.CONVERSIONS, bid_micros=usd_to_micros(35),
        billing_event=BillingEvent.CPM,
        targeting=Targeting(interests=frozenset({"tech"}), geos=frozenset({"USA"})),
        daily_budget_micros=usd_to_micros(500),
        baseline_conv_value_micros=usd_to_micros(80),
        creative=creative, adomain="nimbus.example", pacing=Pacing.EVEN,
    )

    seg = world.segments["tech|USA|25-34|F"]
    rng = random.Random(7)

    print("=" * 72)
    print("QUANTA ADS  -single auction trace (OpenRTB 2.6)")
    print("=" * 72)
    req, res = sampled_auction(
        world, seg, line, ctr=0.018, cvr=0.05, rng=rng, n_phantoms=5, request_id="auc-demo-1"
    )
    print("\nBidRequest:")
    print(json.dumps(req.to_dict(), indent=2))

    print("\nSeat bids:")
    for rb in res.eligible:
        print(f"  ok  {rb.seat:<22} {money(rb.bid.price_micros):>9}")
    for fb in res.filtered:
        print(f"  x   {fb.seat:<22} {money(fb.bid.price_micros):>9}   filtered: {fb.reason.name}")

    if res.won:
        print(
            f"\nWINNER: {res.winner.seat}  bid {money(res.winner.bid.price_micros)}"
            f"  ->  clears at {money(res.clearing_micros)}  [{res.auction_type.name}]"
        )
    print("\nNotices fired (macros expanded):")
    for e in res.notices:
        tag = "BILLED" if e.billed else e.kind.upper()
        print(f"  [{tag:<7}] {e.seat}: {e.url}")

    print("\n" + "=" * 72)
    print("QUANTA ADS  -30-tick delivery (Conversions campaign, learning ramps)")
    print("=" * 72)
    state = DeliveryState()
    print(f"\n{'tick':>4} {'auctions':>9} {'impr':>8} {'clicks':>7} {'conv':>5} {'spend':>9} {'signal':>7}")
    for t in range(1, 31):
        deltas = run_tick(
            world, [line], state,
            sim_seconds_per_tick=60, day_fraction=t / 30, tick_index=t, seed=42, stochastic=True,
        )
        k = rollup(deltas)
        sig = state.learning_signal.get("set-001", 0.0)
        print(
            f"{t:>4} {k.auctions:>9} {k.impressions:>8} {k.clicks:>7} "
            f"{k.conversions:>5} {money(k.spend_micros):>9} {sig:>7.0f}"
        )
    print()


if __name__ == "__main__":
    main()
