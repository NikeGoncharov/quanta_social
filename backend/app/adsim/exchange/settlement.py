"""Auction settlement: the clearing (paid) price given the eligible bids.

  at=1 First Price          -> winner pays its own bid.
  at=2 Second Price Plus    -> winner pays max(second_bid, floor) + $0.01, capped at its
                               own bid; a lone eligible bidder pays the floor (the floor
                               acts as the second price).

The floor guarantees the publisher never sells below `bidfloor`.
"""
from ..models.enums import AuctionType

SECOND_PRICE_INCREMENT_MICROS = 10_000  # $0.01


def settle(
    ranked_prices_micros: list[int],
    floor_micros: int,
    auction_type: AuctionType,
) -> int:
    """Clearing price in micros. `ranked_prices_micros` are the eligible bid CPMs sorted
    descending (each already >= floor)."""
    if not ranked_prices_micros:
        return 0
    top = ranked_prices_micros[0]

    if auction_type == AuctionType.FIRST_PRICE:
        return top

    # Second price plus.
    if len(ranked_prices_micros) >= 2:
        base = max(ranked_prices_micros[1], floor_micros)
        return min(top, base + SECOND_PRICE_INCREMENT_MICROS)
    # Lone eligible bidder: pay the floor.
    return min(top, floor_micros)
