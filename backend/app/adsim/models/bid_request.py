"""OpenRTB BidRequest and its impression objects.

Money (bidfloor) is stored as integer micros internally but serialized as a USD float in
to_dict(), matching the OpenRTB wire format (a plain CPM in currency units).
"""
from dataclasses import dataclass, field

from ..money import micros_to_usd
from ._serial import compact
from .context import Device, Site, User
from .enums import AuctionType


@dataclass
class NativeRequest:
    """Imp.native — a native ad slot. `request` is the (opaque, for us) Native request
    JSON string; we keep a light placeholder plus the version."""
    request: str = "{}"
    ver: str = "1.2"

    def to_dict(self) -> dict:
        return compact({"request": self.request, "ver": self.ver})


@dataclass
class Deal:
    id: str
    bidfloor_micros: int = 0
    at: int | None = None            # overrides BidRequest.at within the deal
    wseat: list[str] = field(default_factory=list)
    wadomain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "bidfloor": micros_to_usd(self.bidfloor_micros),
                "at": self.at,
                "wseat": self.wseat,
                "wadomain": self.wadomain,
            }
        )


@dataclass
class Pmp:
    private_auction: int = 0
    deals: list[Deal] = field(default_factory=list)

    def to_dict(self) -> dict:
        return compact(
            {
                "private_auction": self.private_auction,
                "deals": [d.to_dict() for d in self.deals],
            }
        )


@dataclass
class Imp:
    id: str
    native: NativeRequest | None = None
    bidfloor_micros: int = 0
    bidfloorcur: str = "USD"
    tagid: str = ""          # placement id (e.g. "feed")
    secure: int = 1
    pmp: Pmp | None = None

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "native": self.native.to_dict() if self.native else None,
                "bidfloor": micros_to_usd(self.bidfloor_micros),
                "bidfloorcur": self.bidfloorcur,
                "tagid": self.tagid,
                "secure": self.secure,
                "pmp": self.pmp.to_dict() if self.pmp else None,
            }
        )


@dataclass
class BidRequest:
    id: str
    imp: list[Imp]
    site: Site | None = None
    device: Device | None = None
    user: User | None = None
    at: int = int(AuctionType.FIRST_PRICE)  # Quanta runs a unified first-price auction
    tmax: int = 120                         # simulated latency budget (ms)
    cur: list[str] = field(default_factory=lambda: ["USD"])
    bcat: list[str] = field(default_factory=list)   # blocked IAB categories
    badv: list[str] = field(default_factory=list)   # blocked advertiser domains
    wseat: list[str] = field(default_factory=list)  # allowed buyer seats

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "imp": [i.to_dict() for i in self.imp],
                "site": self.site.to_dict() if self.site else None,
                "device": self.device.to_dict() if self.device else None,
                "user": self.user.to_dict() if self.user else None,
                "at": self.at,
                "tmax": self.tmax,
                "cur": self.cur,
                "bcat": self.bcat,
                "badv": self.badv,
                "wseat": self.wseat,
            }
        )
