"""Factory and simulator integration tests for Avellaneda-Stoikov."""

import math

import pytest

from market_maker_lab.avellaneda_stoikov import (
    AvellanedaStoikovStrategy,
)
from market_maker_lab.monte_carlo import run_path
from market_maker_lab.strategy_factory import (
    DEFAULT_STRATEGIES,
    StrategySpec,
    build_risk_manager,
    build_strategy,
)


def test_factory_builds_avellaneda_stoikov_strategy() -> None:
    spec = StrategySpec(
        "avellaneda_stoikov",
        risk_aversion=0.003,
        distance_sensitivity=18.0,
    )

    strategy = build_strategy(
        spec,
        quote_horizon=0.01,
        initial_volatility=1.5,
        time_horizon=1.0,
    )

    assert isinstance(
        strategy,
        AvellanedaStoikovStrategy,
    )
    assert strategy.name == "avellaneda_stoikov"
    assert strategy.risk_aversion == pytest.approx(0.003)
    assert strategy.distance_sensitivity == pytest.approx(18.0)
    assert strategy.time_horizon == pytest.approx(1.0)
    assert strategy.volatility_estimator.current_volatility == (pytest.approx(1.5))


def test_default_strategy_set_remains_original_five() -> None:
    names = tuple(spec.name for spec in DEFAULT_STRATEGIES)

    assert names == (
        "fixed",
        "inventory",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
    )


def test_avellaneda_stoikov_has_no_risk_overlay_by_default() -> None:
    spec = StrategySpec("avellaneda_stoikov")

    risk_manager, execution = build_risk_manager(spec)

    assert risk_manager is None
    assert execution is not None


def test_avellaneda_stoikov_runs_through_monte_carlo_path() -> None:
    spec = StrategySpec(
        "avellaneda_stoikov",
        risk_aversion=0.003,
        distance_sensitivity=18.0,
    )

    result = run_path(
        scenario="clean",
        spec=spec,
        seed=12345,
        steps=40,
    )

    assert len(result.intervals) == 40
    assert not result.intervals.empty

    required_columns = {
        "estimated_volatility",
        "reservation_price",
        "target_half_spread",
        "time_to_horizon",
        "as_bid_distance",
        "as_ask_distance",
        "as_bid_clipped",
        "as_ask_clipped",
    }

    assert required_columns.issubset(result.intervals.columns)

    assert math.isfinite(result.terminal_pnl)

    assert result.intervals["reservation_price"].notna().all()

    assert result.intervals["target_half_spread"].gt(0.0).all()


def test_factory_preserves_custom_time_horizon() -> None:
    spec = StrategySpec("avellaneda_stoikov")

    strategy = build_strategy(
        spec,
        quote_horizon=0.01,
        initial_volatility=1.0,
        time_horizon=2.0,
    )

    strategy.generate_quote(
        mid_price=100.0,
        inventory=5.0,
        time=0.5,
    )

    diagnostics = strategy.diagnostics()

    assert strategy.time_horizon == pytest.approx(2.0)
    assert diagnostics["time_to_horizon"] == pytest.approx(1.5)
