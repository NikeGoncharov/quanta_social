"""The SSP (sell) side: publisher inventory + BidRequest generation from an ad opportunity."""
from .request_gen import build_bid_request

__all__ = ["build_bid_request"]
