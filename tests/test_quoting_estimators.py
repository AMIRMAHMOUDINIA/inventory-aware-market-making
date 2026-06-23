import math
import pytest
from market_maker_lab.quoting import construct_quote, volatility_adjusted_half_spread
from market_maker_lab.volatility_estimators import EWMAAbsoluteVolatilityEstimator, ConstantVolatilityEstimator
from market_maker_lab.adverse_selection_estimators import EWMAAdverseSelectionEstimator
from market_maker_lab.market_primitives import Trade

@pytest.mark.parametrize("inventory,relation",[(5,"long"),(-5,"short"),(0,"flat")])
def test_inventory_quote_direction(inventory,relation):
    q=construct_quote(100,inventory,.05,.004,.005,.4,5,.001,20)
    bd,ad=100-q.bid,q.ask-100
    assert (bd>ad if relation=="long" else bd<ad if relation=="short" else math.isclose(bd,ad,abs_tol=.002))

def test_size_capped_by_capacity():
    q=construct_quote(100,19,.05,.003,.005,.4,5,.001,20)
    assert q.bid_size==1 and q.ask_size==5

@pytest.mark.parametrize("vol",[0,.5,1,2,5])
def test_spread_monotone(vol):
    h=volatility_adjusted_half_spread(.02,vol,1,.001,.01,.2)
    assert .01<=h<=.2

def test_high_vol_wider():
    assert volatility_adjusted_half_spread(.02,2,1,.001,.01,.2)>volatility_adjusted_half_spread(.02,.5,1,.001,.01,.2)

def test_ewma_shock_and_decay():
    e=EWMAAbsoluteVolatilityEstimator(.9,.5)
    assert e.update(100,0)==.5
    shocked=e.update(101,.01); calm=e.update(101,.02)
    assert shocked>.5 and calm<shocked
    e.reset(); assert e.current_volatility==.5

def test_constant_estimator():
    e=ConstantVolatilityEstimator(1.2); assert e.update(100,0)==1.2; assert e.current_volatility==1.2

@pytest.mark.parametrize("side,end,attr",[("buy",99.8,"bid_loss"),("sell",100.2,"ask_loss")])
def test_adverse_estimator(side,end,attr):
    e=EWMAAdverseSelectionEstimator(.5)
    e.update([Trade(0,side,99.95 if side=="buy" else 100.05,1)],100,end)
    assert getattr(e,attr)>0

def test_toxicity_widens_selected_side():
    neutral=construct_quote(100,0,.05,0,.005,.4,5,.001,20)
    defensive=construct_quote(100,0,.05,0,.005,.4,5,.001,20,bid_adverse_loss=.03,toxicity_sensitivity=1)
    assert defensive.bid<neutral.bid and defensive.ask==neutral.ask
