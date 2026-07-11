"""KPI derivation from raw aggregate counters. All ratios return None when undefined
(divide-by-zero), so the cabinet renders '—' rather than a fake 0."""
from dataclasses import dataclass

from ..money import micros_to_usd


def _div(a, b):
    return (a / b) if b else None


def ctr(clicks, impressions):
    return _div(clicks, impressions)


def cvr(conversions, clicks):
    return _div(conversions, clicks)


def cpm_micros(spend_micros, impressions):
    return int(spend_micros * 1000 / impressions) if impressions else None


def cpc_micros(spend_micros, clicks):
    return int(spend_micros / clicks) if clicks else None


def cpa_micros(spend_micros, conversions):
    return int(spend_micros / conversions) if conversions else None


def roas(revenue_micros, spend_micros):
    return _div(revenue_micros, spend_micros)


def win_rate(impressions, auctions):
    return _div(impressions, auctions)


@dataclass
class Kpis:
    auctions: int = 0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend_micros: int = 0
    revenue_micros: int = 0

    def to_dict(self) -> dict:
        return {
            "auctions": self.auctions,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": round(micros_to_usd(self.spend_micros), 2),
            "revenue": round(micros_to_usd(self.revenue_micros), 2),
            "ctr": ctr(self.clicks, self.impressions),
            "cvr": cvr(self.conversions, self.clicks),
            "cpm": _usd(cpm_micros(self.spend_micros, self.impressions)),
            "cpc": _usd(cpc_micros(self.spend_micros, self.clicks)),
            "cpa": _usd(cpa_micros(self.spend_micros, self.conversions)),
            "roas": roas(self.revenue_micros, self.spend_micros),
            "win_rate": win_rate(self.impressions, self.auctions),
        }


def _usd(micros):
    return None if micros is None else round(micros_to_usd(micros), 2)


def rollup(deltas) -> Kpis:
    """Sum a list of SegmentDeltas into one Kpis."""
    k = Kpis()
    for d in deltas:
        k.auctions += d.auctions
        k.impressions += d.impressions
        k.clicks += d.clicks
        k.conversions += d.conversions
        k.spend_micros += d.spend_micros
        k.revenue_micros += d.revenue_micros
    return k
