"""OpenRTB BidResponse / SeatBid / Bid.

`price_micros` is the bid CPM in micros; to_dict emits it as a USD float (`price`),
matching the wire format. Notice URLs (nurl/burl/lurl) carry ${AUCTION_PRICE} macros the
exchange expands at settlement time.
"""
from dataclasses import dataclass, field

from ..money import micros_to_usd
from ._serial import compact
from .enums import MarkupType


@dataclass
class Bid:
    id: str
    impid: str
    price_micros: int                 # bid CPM (micros)
    adid: str = ""
    nurl: str = ""                    # win notice URL (may carry ${AUCTION_PRICE})
    burl: str = ""                    # billing notice URL (spend accrues here)
    lurl: str = ""                    # loss notice URL
    adm: dict | str | None = None     # native markup
    adomain: list[str] = field(default_factory=list)
    cid: str = ""                     # campaign id
    crid: str = ""                    # creative id
    cat: list[str] = field(default_factory=list)  # creative's IAB categories
    w: int | None = None
    h: int | None = None
    mtype: int = int(MarkupType.NATIVE)
    dealid: str = ""

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "impid": self.impid,
                "price": micros_to_usd(self.price_micros),
                "adid": self.adid,
                "nurl": self.nurl,
                "burl": self.burl,
                "lurl": self.lurl,
                "adm": self.adm,
                "adomain": self.adomain,
                "cid": self.cid,
                "crid": self.crid,
                "cat": self.cat,
                "w": self.w,
                "h": self.h,
                "mtype": self.mtype,
                "dealid": self.dealid,
            }
        )


@dataclass
class SeatBid:
    bid: list[Bid]
    seat: str = ""
    group: int = 0

    def to_dict(self) -> dict:
        return compact(
            {"bid": [b.to_dict() for b in self.bid], "seat": self.seat, "group": self.group}
        )


@dataclass
class BidResponse:
    id: str
    seatbid: list[SeatBid] = field(default_factory=list)
    bidid: str = ""
    cur: str = "USD"
    nbr: int | None = None  # no-bid reason (when seatbid is empty)

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "seatbid": [s.to_dict() for s in self.seatbid],
                "bidid": self.bidid,
                "cur": self.cur,
                "nbr": self.nbr,
            }
        )
