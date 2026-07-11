"""OpenRTB substitution macros used in nurl/burl/lurl (and adm).

The exchange expands `${AUCTION_PRICE}` to the clearing price before firing a notice —
this is how the winning DSP learns what it actually pays. We use plain CPM in
${AUCTION_PRICE} (skipping Google-style microunit encryption), per the teaching design.
"""
from ..money import micros_to_usd

# Canonical macro names (OpenRTB 2.6).
AUCTION_ID = "AUCTION_ID"
AUCTION_BID_ID = "AUCTION_BID_ID"
AUCTION_IMP_ID = "AUCTION_IMP_ID"
AUCTION_SEAT_ID = "AUCTION_SEAT_ID"
AUCTION_AD_ID = "AUCTION_AD_ID"
AUCTION_PRICE = "AUCTION_PRICE"
AUCTION_CURRENCY = "AUCTION_CURRENCY"
AUCTION_LOSS = "AUCTION_LOSS"
AUCTION_MIN_TO_WIN = "AUCTION_MIN_TO_WIN"


def expand(template: str, ctx: dict) -> str:
    """Replace every ${MACRO} in `template` with str(ctx[MACRO]) where present."""
    if not template:
        return template
    out = template
    for name, value in ctx.items():
        out = out.replace("${" + name + "}", str(value))
    return out


def price_ctx(
    *,
    auction_id: str,
    bid_id: str,
    imp_id: str,
    seat_id: str = "",
    ad_id: str = "",
    clearing_micros: int,
    currency: str = "USD",
) -> dict:
    """Build the macro context for a win/billing notice. ${AUCTION_PRICE} is the clearing
    CPM in dollars (2-decimal), matching how a real exchange quotes a plain price."""
    return {
        AUCTION_ID: auction_id,
        AUCTION_BID_ID: bid_id,
        AUCTION_IMP_ID: imp_id,
        AUCTION_SEAT_ID: seat_id,
        AUCTION_AD_ID: ad_id,
        AUCTION_PRICE: f"{micros_to_usd(clearing_micros):.2f}",
        AUCTION_CURRENCY: currency,
    }
