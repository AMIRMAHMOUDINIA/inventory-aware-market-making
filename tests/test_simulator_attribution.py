import math

import numpy as np
import pytest

from market_maker_lab.monte_carlo import run_path
from market_maker_lab.pnl_attribution import (
    attribute_market_making_pnl,
    compute_markout_curve,
)
from market_maker_lab.strategy_factory import DEFAULT_STRATEGIES
from market_maker_lab.validation import validate_simulation_result


@pytest.mark.parametrize(
    "scenario",
    [
        "clean",
        "high_volatility",
        "toxic",
        "one_sided",
        "regime_switching",
        "stress",
    ],
)
def test_scenario_reconciles(scenario):
    result = run_path(
        scenario,
        DEFAULT_STRATEGIES[2],
        123,
        steps=80,
    )

    validation = validate_simulation_result(
        result,
        tolerance=1e-8,
    )

    assert bool(validation.interval_reconciliation_pass)
    assert bool(validation.terminal_reconciliation_pass)
    assert abs(result.final_inventory) < 1e-12


@pytest.mark.parametrize(
    "strategy",
    DEFAULT_STRATEGIES,
)
def test_strategy_reconciles(strategy):
    result = run_path(
        "toxic",
        strategy,
        321,
        steps=100,
    )

    attribution = attribute_market_making_pnl(result)

    assert math.isclose(
        attribution.reported_terminal_pnl,
        attribution.attributed_terminal_pnl,
        abs_tol=1e-8,
    )

    assert result.intervals.reconciliation_error.abs().max() < 1e-8


def test_same_seed_same_price_path_across_strategies():
    fixed_result = run_path(
        "toxic",
        DEFAULT_STRATEGIES[0],
        99,
        steps=120,
    )

    adaptive_result = run_path(
        "toxic",
        DEFAULT_STRATEGIES[3],
        99,
        steps=120,
    )

    np.testing.assert_allclose(
        fixed_result.intervals.mid_end,
        adaptive_result.intervals.mid_end,
    )


def test_different_seed_changes_path():
    first_result = run_path(
        "clean",
        DEFAULT_STRATEGIES[0],
        99,
        steps=80,
    )

    second_result = run_path(
        "clean",
        DEFAULT_STRATEGIES[0],
        100,
        steps=80,
    )

    assert not np.allclose(
        first_result.intervals.mid_end,
        second_result.intervals.mid_end,
    )


def test_information_components_sum_to_price_pnl():
    result = run_path(
        "toxic",
        DEFAULT_STRATEGIES[0],
        77,
        steps=100,
    )

    intervals = result.intervals

    combined_price_pnl = (
        intervals.drift_price_pnl
        + intervals.information_price_pnl
        + intervals.noise_price_pnl
        + intervals.jump_price_pnl
    )

    np.testing.assert_allclose(
        combined_price_pnl,
        intervals.price_move_pnl,
        atol=1e-10,
    )


def test_new_and_carried_sum_to_price_pnl():
    result = run_path(
        "one_sided",
        DEFAULT_STRATEGIES[1],
        77,
        steps=100,
    )

    intervals = result.intervals

    np.testing.assert_allclose(
        intervals.new_fill_price_pnl + intervals.carried_inventory_price_pnl,
        intervals.price_move_pnl,
        atol=1e-10,
    )


def test_markout_curve_available():
    result = run_path(
        "toxic",
        DEFAULT_STRATEGIES[0],
        42,
        steps=120,
    )

    curve = compute_markout_curve(
        result.trades,
        result.intervals,
        (1, 5, 20),
    )

    assert set(curve.horizon_steps).issubset({1, 5, 20})
    assert len(curve) > 0


def test_risk_strategy_respects_limit():
    result = run_path(
        "stress",
        DEFAULT_STRATEGIES[-1],
        222,
        steps=200,
    )

    assert result.intervals.inventory_after_fills.abs().max() <= 28 + 1e-9
