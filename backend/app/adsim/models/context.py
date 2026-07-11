"""OpenRTB context objects: who/what/where the impression is for.

Site (Quanta is a desktop website), Publisher, Device, Geo, User, and the DMP-style
Data/Segment objects that carry audience segments (synthesized, not onboarded).
"""
from dataclasses import dataclass, field

from ._serial import compact
from .enums import DeviceType


@dataclass
class Geo:
    country: str = ""   # simplified code (e.g. "USA", "GBR")
    region: str = ""
    city: str = ""

    def to_dict(self) -> dict:
        return compact({"country": self.country, "region": self.region, "city": self.city})


@dataclass
class Device:
    ua: str = ""
    devicetype: int = int(DeviceType.PERSONAL_COMPUTER)
    os: str = "Windows"
    geo: Geo | None = None
    language: str = "en"

    def to_dict(self) -> dict:
        return compact(
            {
                "ua": self.ua,
                "devicetype": self.devicetype,
                "os": self.os,
                "geo": self.geo.to_dict() if self.geo else None,
                "language": self.language,
            }
        )


@dataclass
class Segment:
    id: str
    name: str = ""
    value: str = ""

    def to_dict(self) -> dict:
        return compact({"id": self.id, "name": self.name, "value": self.value})


@dataclass
class Data:
    """A data provider's audience segments (the DMP hook)."""
    id: str
    name: str = ""
    segment: list[Segment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return compact(
            {"id": self.id, "name": self.name, "segment": [s.to_dict() for s in self.segment]}
        )


@dataclass
class User:
    id: str = ""
    buyeruid: str = ""
    yob: int | None = None
    gender: str = ""  # "M" | "F"
    geo: Geo | None = None
    data: list[Data] = field(default_factory=list)

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "buyeruid": self.buyeruid,
                "yob": self.yob,
                "gender": self.gender,
                "geo": self.geo.to_dict() if self.geo else None,
                "data": [d.to_dict() for d in self.data],
            }
        )


@dataclass
class Publisher:
    id: str
    name: str = ""
    cat: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return compact({"id": self.id, "name": self.name, "cat": self.cat})


@dataclass
class Site:
    id: str
    name: str = ""
    domain: str = ""
    cat: list[str] = field(default_factory=list)
    publisher: Publisher | None = None

    def to_dict(self) -> dict:
        return compact(
            {
                "id": self.id,
                "name": self.name,
                "domain": self.domain,
                "cat": self.cat,
                "publisher": self.publisher.to_dict() if self.publisher else None,
            }
        )
