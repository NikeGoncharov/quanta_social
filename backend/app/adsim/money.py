"""Money is stored and computed as integer micros (1 USD = 1_000_000 micros) to avoid
float drift under continuous accrual. CPM math is centralized here.

  micros            integer millionths of a dollar
  CPM               price per 1000 impressions, quoted in micros
  spend(imps, cpm)  = imps * cpm / 1000   (all integer)
"""
MICROS_PER_USD = 1_000_000


def usd_to_micros(usd: float) -> int:
    return int(round(usd * MICROS_PER_USD))


def micros_to_usd(micros: int) -> float:
    return micros / MICROS_PER_USD


def spend_micros(impressions: int, cpm_micros: int) -> int:
    """Cost of `impressions` at a CPM (price per 1000), in micros."""
    return impressions * cpm_micros // 1000


def cpc_to_ecpm_micros(cpc_micros: int, ctr: float) -> int:
    """Effective CPM of a CPC bid: expected cost per 1000 impressions = CPC * CTR * 1000."""
    return int(round(cpc_micros * ctr * 1000))


def cpa_to_ecpm_micros(target_cpa_micros: int, cvr_per_impression: float) -> int:
    """Effective CPM of a target-CPA bid: bid up to target_cpa * (conversions per imp) * 1000."""
    return int(round(target_cpa_micros * cvr_per_impression * 1000))
