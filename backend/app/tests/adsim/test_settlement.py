from app.adsim.exchange.settlement import SECOND_PRICE_INCREMENT_MICROS, settle
from app.adsim.models.enums import AuctionType
from app.adsim.money import usd_to_micros

FLOOR = usd_to_micros(1)


def test_first_price_pays_own_bid():
    prices = [usd_to_micros(5), usd_to_micros(3)]
    assert settle(prices, FLOOR, AuctionType.FIRST_PRICE) == usd_to_micros(5)


def test_second_price_pays_second_plus_increment():
    prices = [usd_to_micros(5), usd_to_micros(3)]
    c = settle(prices, FLOOR, AuctionType.SECOND_PRICE_PLUS)
    assert c == usd_to_micros(3) + SECOND_PRICE_INCREMENT_MICROS


def test_second_price_capped_at_own_bid_on_tie():
    prices = [usd_to_micros(3), usd_to_micros(3)]
    # second+increment would exceed the winner's own bid -> capped to own bid.
    assert settle(prices, FLOOR, AuctionType.SECOND_PRICE_PLUS) == usd_to_micros(3)


def test_second_price_never_below_floor():
    prices = [usd_to_micros(5), usd_to_micros(2)]
    high_floor = usd_to_micros(4)
    # second bid (2) is below the floor (4): the floor is the effective second price.
    c = settle(prices, high_floor, AuctionType.SECOND_PRICE_PLUS)
    assert c == high_floor + SECOND_PRICE_INCREMENT_MICROS


def test_single_bidder_second_price_pays_floor():
    prices = [usd_to_micros(5)]
    assert settle(prices, usd_to_micros(2), AuctionType.SECOND_PRICE_PLUS) == usd_to_micros(2)


def test_empty_settles_zero():
    assert settle([], FLOOR, AuctionType.FIRST_PRICE) == 0
