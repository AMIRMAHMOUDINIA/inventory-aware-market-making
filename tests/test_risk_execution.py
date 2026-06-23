import math
import pytest
from market_maker_lab.risk_controls import *
from market_maker_lab.aggressive_execution import *
from market_maker_lab.ledger import MarketMakerLedger
from market_maker_lab.market_primitives import Quote

def manager(**kwargs):
    limits=RiskLimits(10,20,5,maximum_loss=kwargs.get("maximum_loss",50),maximum_drawdown=kwargs.get("maximum_drawdown",30),
                      maximum_absolute_price_jump=kwargs.get("jump"),cooldown_steps=3)
    m=MarketMakerRiskManager(limits); m.reset(0); return m

def snap(inv=0,wealth=0,jump=None): return RiskSnapshot(0,0,100,inv,0,wealth,wealth,None,jump)

@pytest.mark.parametrize("inv,state",[(0,RiskState.NORMAL),(9,RiskState.NORMAL),(12,RiskState.REDUCE_ONLY),(22,RiskState.FORCED_REDUCTION),(-12,RiskState.REDUCE_ONLY),(-22,RiskState.FORCED_REDUCTION)])
def test_position_states(inv,state): assert manager().assess(snap(inv)).state==state

def test_reduce_only_sides():
    long=manager().assess(snap(12)); short=manager().assess(snap(-12))
    assert not long.allow_bid and long.allow_ask and short.allow_bid and not short.allow_ask

def test_loss_halt_persistent():
    m=manager(); d=m.assess(snap(0,-55)); assert d.state==RiskState.HALTED and m.assess(snap()).state==RiskState.HALTED

def test_drawdown_halt_while_profitable():
    m=manager(); m.assess(snap(0,40)); d=m.assess(snap(0,5)); assert d.state==RiskState.HALTED

def test_jump_cooldown(): assert manager(jump=.5).assess(snap(jump=.8)).state==RiskState.COOLDOWN

def test_overlay_caps_capacity():
    d=RiskDecision(RiskState.NORMAL,(),True,True,None,False,0,0)
    q=apply_risk_overlay(Quote(99.95,100.05,5,5),9,d,10); assert q.bid_size==1

@pytest.mark.parametrize("target,side",[(5,"sell"),(-5,"buy")])
def test_forced_execution(target,side):
    l=MarketMakerLedger(0,20 if target>0 else -20); c=AggressiveExecutionConfig(.05,.01,.001)
    r=execute_to_target_inventory(l,target,100,0,c)
    assert r.trade.side==side and math.isclose(l.inventory,target)
    q=15; assert math.isclose(r.total_execution_cost,q*.05+.001*q*q+q*.01)
