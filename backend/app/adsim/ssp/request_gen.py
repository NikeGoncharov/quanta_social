"""Build an OpenRTB BidRequest from an ad opportunity (a segment + a viewing user).

Quanta is a single desktop website publisher; the feed slot is a native impression. The
segment's interest/age/gender ride along as User.data segments (the DMP hook), so a real
RTB engineer would recognize the audience signal.
"""
from ..models.bid_request import BidRequest, Imp, NativeRequest
from ..models.context import Data, Device, Geo, Publisher, Site, User
from ..models.context import Segment as CtxSegment
from ..models.enums import DeviceType

_YOB_BY_AGE = {"18-24": 2004, "25-34": 1996, "35-44": 1986, "45+": 1975}


def build_bid_request(
    *,
    request_id: str,
    world_segment,
    user_id: str = "u-synthetic",
    placement: str = "feed",
    floor_micros: int,
    auction_type: int,
) -> BidRequest:
    geo = Geo(country=world_segment.geo)
    device = Device(
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        devicetype=int(DeviceType.PERSONAL_COMPUTER),
        os="Windows",
        geo=geo,
    )
    user = User(
        id=user_id,
        yob=_YOB_BY_AGE.get(world_segment.age_band),
        gender=world_segment.gender,
        geo=geo,
        data=[
            Data(
                id="quanta-audiences",
                name="Quanta Audiences",
                segment=[
                    CtxSegment(id=world_segment.interest, name="interest", value="1"),
                    CtxSegment(id=world_segment.age_band, name="age_band", value="1"),
                    CtxSegment(id=world_segment.gender, name="gender", value="1"),
                ],
            )
        ],
    )
    imp = Imp(
        id="1",
        native=NativeRequest(),
        bidfloor_micros=floor_micros,
        tagid=placement,
        secure=1,
    )
    site = Site(
        id="quanta",
        name="Quanta Social",
        domain="quanta-social.com",
        cat=["IAB14"],  # Society / Social Networking
        publisher=Publisher(id="quanta-pub", name="Quanta"),
    )
    return BidRequest(
        id=request_id,
        imp=[imp],
        site=site,
        device=device,
        user=user,
        at=int(auction_type),
        cur=["USD"],
    )
