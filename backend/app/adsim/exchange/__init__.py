"""The exchange: eligibility filtering, ranking, settlement, and notice lifecycle.

`run_auction` is a pure function used by BOTH the materialized path (real feed views and
the sampled auctions shown in the RTB Inspector) and — via its settlement math — the
statistical aggregate path in `simulation.delivery`.
"""
from .auction import AuctionResult, FilteredBid, RankedBid, run_auction
from .settlement import SECOND_PRICE_INCREMENT_MICROS, settle

__all__ = [
    "AuctionResult",
    "FilteredBid",
    "RankedBid",
    "run_auction",
    "settle",
    "SECOND_PRICE_INCREMENT_MICROS",
]
