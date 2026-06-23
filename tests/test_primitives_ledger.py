import math
import pytest
from market_maker_lab.market_primitives import Quote, Trade, validate_quote, round_bid_to_tick, round_ask_to_tick
from market_maker_lab.ledger import MarketMakerLedger
from market_maker_lab.markouts import immediate_spread_capture, post_trade_price_component, trade_markout

@pytest.mark.parametrize("bid,ask,mid,spread",[(99.95,100.05,100,0.10),(10,10.2,10.1,0.2),(1,1.02,1.01,0.02)])
def test_quote_properties(bid,ask,mid,spread):
    q=Quote(bid,ask,1,1); validate_quote(q)
    assert math.isclose(q.mid,mid); assert math.isclose(q.spread,spread)

@pytest.mark.parametrize("side,expected",[("buy",2.0),("sell",-2.0)])
def test_trade_sign(side,expected): assert Trade(0,side,100,2).signed_quantity==expected

def test_crossed_quote_rejected():
    with pytest.raises(ValueError): validate_quote(Quote(101,100,1,1))

@pytest.mark.parametrize("price,tick,expected",[(99.947,.01,99.94),(100,.01,100),(1.239,.05,1.2)])
def test_bid_rounding(price,tick,expected): assert math.isclose(round_bid_to_tick(price,tick),expected,abs_tol=1e-12)

@pytest.mark.parametrize("price,tick,expected",[(100.003,.01,100.01),(100,.01,100),(1.201,.05,1.25)])
def test_ask_rounding(price,tick,expected): assert math.isclose(round_ask_to_tick(price,tick),expected,abs_tol=1e-12)

def test_round_trip_earns_spread():
    l=MarketMakerLedger(); l.apply_trade(Trade(0,"buy",99.95,10)); l.apply_trade(Trade(1,"sell",100.05,10))
    assert math.isclose(l.cash,1.0); assert l.inventory==0

@pytest.mark.parametrize("side,price,later,expected",[("buy",99.95,100.1,0.15),("buy",99.95,99.8,-0.15),("sell",100.05,99.9,0.15),("sell",100.05,100.3,-0.25)])
def test_markout_signs(side,price,later,expected):
    t=Trade(0,side,price,1)
    assert math.isclose(trade_markout(t,later),expected,abs_tol=1e-12)
    assert math.isclose(trade_markout(t,later),immediate_spread_capture(t,100)+post_trade_price_component(t,100,later),abs_tol=1e-12)
