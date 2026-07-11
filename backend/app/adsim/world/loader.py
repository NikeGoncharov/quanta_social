"""Load world.yaml into a World. Segments are the cross product of the interest x geo x
age_band x gender dimensions, with per-cell parameters derived from the dimension params.
"""
from pathlib import Path

import yaml

from ..money import usd_to_micros
from .schema import Economy, Fatigue, Learning, PhantomSeat, Segment, World

_DEFAULT_PATH = Path(__file__).with_name("world.yaml")
_SECONDS_PER_SIM_DAY = 86_400


def load_world(path: str | Path | None = None) -> World:
    p = Path(path) if path else _DEFAULT_PATH
    with open(p, "r", encoding="utf-8") as f:
        d = yaml.safe_load(f)

    population = int(d["population"])
    eco = d["economy"]
    daily_opps = int(eco["daily_opportunities"])

    interests = d["interests"]
    geos = d["geos"]
    ages = d["age_bands"]
    genders = d["genders"]

    segments: dict[str, Segment] = {}
    for it in interests:
        for g in geos:
            for a in ages:
                for gen in genders:
                    frac = it["size"] * g["frac"] * a["frac"] * gen["frac"]
                    size = int(round(population * frac))
                    opp_rate = daily_opps * frac / _SECONDS_PER_SIM_DAY
                    seg_id = f"{it['id']}|{g['id']}|{a['id']}|{gen['id']}"
                    segments[seg_id] = Segment(
                        id=seg_id,
                        interest=it["id"],
                        geo=g["id"],
                        age_band=a["id"],
                        gender=gen["id"],
                        size=size,
                        opportunity_rate=opp_rate,
                        base_ctr=float(it["base_ctr"]) * float(a["ctr_mult"]),
                        base_cvr=float(it["base_cvr"]) * float(a["cvr_mult"]),
                        value_multiplier=float(it["value"]) * float(gen["value_mult"]),
                        reference_bid_micros=usd_to_micros(
                            float(it["reference_cpm"]) * float(g["cpm_mult"])
                        ),
                    )

    economy = Economy(
        currency=eco.get("currency", "USD"),
        auction_type=int(eco.get("auction_type", 1)),
        default_floor_micros=usd_to_micros(float(eco["default_floor_cpm"])),
        market_density=float(eco.get("market_density", 1.0)),
        daily_opportunities=daily_opps,
    )
    learning = Learning(
        start_lift=float(d["learning"]["start_lift"]),
        target_lift=float(d["learning"]["target_lift"]),
        threshold=float(d["learning"]["threshold"]),
        noise=float(d["learning"].get("noise", 0.2)),
    )
    fatigue = Fatigue(
        free_frequency=float(d["fatigue"]["free_frequency"]),
        k=float(d["fatigue"]["k"]),
    )
    phantom = tuple(
        PhantomSeat(name=s["name"], aggressiveness=float(s["aggressiveness"]))
        for s in d["phantom_seats"]
    )

    return World(
        interests=tuple(it["id"] for it in interests),
        geos=tuple(g["id"] for g in geos),
        age_bands=tuple(a["id"] for a in ages),
        genders=tuple(gen["id"] for gen in genders),
        segments=segments,
        phantom_seats=phantom,
        economy=economy,
        learning=learning,
        fatigue=fatigue,
        relevance_uplift=float(d["relevance_uplift"]),
        baseline_conv_value_micros=usd_to_micros(float(d["baseline_conv_value"])),
        population=population,
    )
