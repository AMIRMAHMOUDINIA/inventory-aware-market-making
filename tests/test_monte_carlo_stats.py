import numpy as np
import pandas as pd
from market_maker_lab.monte_carlo import run_strategy_comparison
from market_maker_lab.strategy_factory import DEFAULT_STRATEGIES
from market_maker_lab.metrics import summarize_strategy_results
from market_maker_lab.statistical_comparison import paired_differences, paired_bootstrap_interval


def small_results():
    return run_strategy_comparison(["clean","toxic"],DEFAULT_STRATEGIES[:3],8,900,steps=60)


def test_comparison_shape_and_pairing():
    r=small_results(); assert len(r)==2*3*8
    assert r.groupby(["scenario","strategy"]).size().eq(8).all()


def test_summary_contains_tail_metrics():
    s=summarize_strategy_results(small_results())
    assert {"expected_shortfall_5","pnl_5_percentile","probability_of_loss"}.issubset(s.columns)


def test_paired_differences_length():
    r=small_results(); d=paired_differences(r,"toxic","inventory_volatility","fixed")
    assert len(d)==8 and np.isfinite(d).all()


def test_bootstrap_interval_order():
    out=paired_bootstrap_interval(np.array([1,2,3,4,5.]),500,1)
    assert out["lower_bound"]<out["mean_difference"]<out["upper_bound"]


def test_reconciliation_small_across_mc():
    r=small_results(); assert r.reconciliation_error.abs().max()<1e-8
