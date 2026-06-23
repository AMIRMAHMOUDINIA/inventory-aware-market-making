import math
import numpy as np
import pytest
from market_maker_lab.monte_carlo import run_path
from market_maker_lab.strategy_factory import DEFAULT_STRATEGIES, StrategySpec
from market_maker_lab.pnl_attribution import attribute_market_making_pnl, compute_markout_curve
from market_maker_lab.validation import validate_simulation_result

@pytest.mark.parametrize("scenario",["clean","high_volatility","toxic","one_sided","regime_switching","stress"])
def test_scenario_reconciles(scenario):
    r=run_path(scenario,DEFAULT_STRATEGIES[2],123,steps=80)
    v=validate_simulation_result(r,tolerance=1e-8)
    assert bool(v.interval_reconciliation_pass) and bool(v.terminal_reconciliation_pass)
    assert abs(r.final_inventory)<1e-12

@pytest.mark.parametrize("strategy",DEFAULT_STRATEGIES)
def test_strategy_reconciles(strategy):
    r=run_path("toxic",strategy,321,steps=100)
    a=attribute_market_making_pnl(r)
    assert math.isclose(a.reported_terminal_pnl,a.attributed_terminal_pnl,abs_tol=1e-8)
    assert r.intervals.reconciliation_error.abs().max()<1e-8


def test_same_seed_same_price_path_across_strategies():
    a=run_path("toxic",DEFAULT_STRATEGIES[0],99,steps=120)
    b=run_path("toxic",DEFAULT_STRATEGIES[3],99,steps=120)
    np.testing.assert_allclose(a.intervals.mid_end,b.intervals.mid_end)


def test_different_seed_changes_path():
    a=run_path("clean",DEFAULT_STRATEGIES[0],99,steps=80)
    b=run_path("clean",DEFAULT_STRATEGIES[0],100,steps=80)
    assert not np.allclose(a.intervals.mid_end,b.intervals.mid_end)


def test_information_components_sum_to_price_pnl():
    r=run_path("toxic",DEFAULT_STRATEGIES[0],77,steps=100)
    x=r.intervals
    combined=x.drift_price_pnl+x.information_price_pnl+x.noise_price_pnl+x.jump_price_pnl
    np.testing.assert_allclose(combined,x.price_move_pnl,atol=1e-10)


def test_new_and_carried_sum_to_price_pnl():
    r=run_path("one_sided",DEFAULT_STRATEGIES[1],77,steps=100)
    x=r.intervals
    np.testing.assert_allclose(x.new_fill_price_pnl+x.carried_inventory_price_pnl,x.price_move_pnl,atol=1e-10)


def test_markout_curve_available():
    r=run_path("toxic",DEFAULT_STRATEGIES[0],42,steps=120)
    curve=compute_markout_curve(r.trades,r.intervals,(1,5,20))
    assert set(curve.horizon_steps).issubset({1,5,20}) and len(curve)>0


def test_risk_strategy_respects_limit():
    r=run_path("stress",DEFAULT_STRATEGIES[-1],222,steps=200)
    assert r.intervals.inventory_after_fills.abs().max()<=28+1e-9
