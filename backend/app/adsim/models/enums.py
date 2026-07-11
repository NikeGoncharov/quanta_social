"""OpenRTB 2.6 / AdCOM enumerations (as IntEnum, matching the spec integers) plus a few
Quanta-domain enums. Keeping the spec integers means a serialized BidRequest/Bid is
recognizable to a real RTB engineer.
"""
from enum import Enum, IntEnum


# --- OpenRTB / AdCOM ---------------------------------------------------------
class AuctionType(IntEnum):
    """BidRequest.at"""
    FIRST_PRICE = 1
    SECOND_PRICE_PLUS = 2


class DeviceType(IntEnum):
    MOBILE_TABLET = 1
    PERSONAL_COMPUTER = 2  # Quanta is desktop-only
    CONNECTED_TV = 3
    PHONE = 4
    TABLET = 5
    CONNECTED_DEVICE = 6
    SET_TOP_BOX = 7
    OOH_DEVICE = 8


class ConnectionType(IntEnum):
    UNKNOWN = 0
    ETHERNET = 1
    WIFI = 2
    CELLULAR_UNKNOWN = 3
    CELL_2G = 4
    CELL_3G = 5
    CELL_4G = 6
    CELL_5G = 7


class MarkupType(IntEnum):
    """Bid.mtype (2.6)"""
    BANNER = 1
    VIDEO = 2
    AUDIO = 3
    NATIVE = 4


class NoBidReason(IntEnum):
    """BidResponse.nbr"""
    UNKNOWN = 0
    TECHNICAL_ERROR = 1
    INVALID_REQUEST = 2
    KNOWN_SPIDER = 3
    SUSPECTED_NONHUMAN = 4
    CLOUD_DC_PROXY = 5
    UNSUPPORTED_DEVICE = 6
    BLOCKED_PUBLISHER = 7
    UNMATCHED_USER = 8


class LossReason(IntEnum):
    """${AUCTION_LOSS} in lurl."""
    WON = 0
    INTERNAL_ERROR = 1
    IMPRESSION_OPPORTUNITY_EXPIRED = 2
    BELOW_AUCTION_FLOOR = 100
    BELOW_DEAL_FLOOR = 101
    LOST_TO_HIGHER_BID = 102
    LOST_TO_PMP_DEAL = 103
    CREATIVE_FILTERED_CATEGORY = 205
    CREATIVE_FILTERED_ADVERTISER = 206


# --- Quanta domain -----------------------------------------------------------
class Objective(str, Enum):
    AWARENESS = "awareness"      # optimize impressions/reach — CPM (TOF)
    TRAFFIC = "traffic"          # optimize link clicks — CPC (MOF)
    ENGAGEMENT = "engagement"    # optimize post reactions (MOF)
    CONVERSIONS = "conversions"  # optimize conversions — CPA/ROAS, learning phase (BOF)


class BillingEvent(str, Enum):
    CPM = "cpm"
    CPC = "cpc"


class BidStrategy(str, Enum):
    LOWEST_COST = "lowest_cost"
    COST_CAP = "cost_cap"
    BID_CAP = "bid_cap"
    MANUAL = "manual"


class Pacing(str, Enum):
    EVEN = "even"
    ASAP = "asap"


# Which billing event an objective bills on by default.
OBJECTIVE_BILLING = {
    Objective.AWARENESS: BillingEvent.CPM,
    Objective.TRAFFIC: BillingEvent.CPC,
    Objective.ENGAGEMENT: BillingEvent.CPC,
    Objective.CONVERSIONS: BillingEvent.CPM,  # optimized to conversions, billed on impressions
}

# Objectives whose delivery goes through a learning phase (need conversion/engagement signal).
LEARNING_OBJECTIVES = frozenset({Objective.CONVERSIONS, Objective.ENGAGEMENT})

# Funnel stage label per objective (a small teaching touch surfaced in the cabinet).
FUNNEL_STAGE = {
    Objective.AWARENESS: "TOF",
    Objective.TRAFFIC: "MOF",
    Objective.ENGAGEMENT: "MOF",
    Objective.CONVERSIONS: "BOF",
}
