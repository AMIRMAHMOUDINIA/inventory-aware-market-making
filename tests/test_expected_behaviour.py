import numpy as np
from market_maker_lab.monte_carlo import run_strategy_comparison
from market_maker_lab.strategy_factory import DEFAULT_STRATEGIES


def test_volatility_strategy_trades_less_in_high_volatility():
    r=run_strategy_comparison(["high_volatility"],[DEFAULT_STRATEGIES[0],DEFAULT_STRATEGIES[2]],25,1200,steps=100)
    m=r.groupby("strategy").total_traded_quantity.mean()
    assert m["inventory_volatility"]<m["fixed"]


def test_adaptive_improves_markout_in_toxic_market():
    r=run_strategy_comparison(["toxic"],[DEFAULT_STRATEGIES[0],DEFAULT_STRATEGIES[3]],30,1400,steps=100)
    m=r.groupby("strategy").markout_per_unit.mean()
    assert m["full_adaptive"]>m["fixed"]


def test_inventory_control_reduces_inventory_in_one_sided_flow():
    r=run_strategy_comparison(["one_sided"],[DEFAULT_STRATEGIES[0],DEFAULT_STRATEGIES[1]],30,1600,steps=100)
    m=r.groupby("strategy").mean_absolute_inventory.mean()
    assert m["inventory"]<m["fixed"]
