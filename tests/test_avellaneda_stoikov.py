"""Tests for the finite-horizon Avellaneda-Stoikov strategy."""

from math import log1p

import pytest

from market_maker_lab.avellaneda_stoikov import (
    AvellanedaStoikovStrategy,
    optimal_half_spread,
    reservation_price,
)
from market_maker_lab.volatility_estimators import (
    ConstantVolatilityEstimator,
)


def build_strategy() -> AvellanedaStoikovStrategy:
    return AvellanedaStoikovStrategy(
        risk_aversion=0.003,
        distance_sensitivity=18.0,
        time_horizon=1.0,
        order_size=4.0,
        tick_size=0.01,
        inventory_limit=40.0,
        minimum_quote_distance=0.001,
        maximum_quote_distance=0.40,
        volatility_estimator=ConstantVolatilityEstimator(1.0),
    )


def test_reservation_price_zero_inventory_equals_mid() -> None:
    result = reservation_price(
        mid_price=100.0,
        inventory=0.0,
        risk_aversion=0.003,
        volatility=1.0,
        time_to_horizon=1.0,
    )

    assert result == pytest.approx(100.0)


def test_reservation_price_moves_against_inventory() -> None:
    long_inventory = reservation_price(
        mid_price=100.0,
        inventory=10.0,
        risk_aversion=0.003,
        volatility=1.0,
        time_to_horizon=1.0,
    )

    short_inventory = reservation_price(
        mid_price=100.0,
        inventory=-10.0,
        risk_aversion=0.003,
        volatility=1.0,
        time_to_horizon=1.0,
    )

    assert long_inventory == pytest.approx(99.97)
    assert short_inventory == pytest.approx(100.03)


def test_inventory_effect_disappears_at_horizon() -> None:
    result = reservation_price(
        mid_price=100.0,
        inventory=20.0,
        risk_aversion=0.003,
        volatility=2.0,
        time_to_horizon=0.0,
    )

    assert result == pytest.approx(100.0)


def test_optimal_half_spread_matches_formula() -> None:
    gamma = 0.003
    sigma = 1.0
    tau = 1.0
    k = 18.0

    expected = (
        0.5 * gamma * sigma**2 * tau
        + log1p(gamma / k) / gamma
    )

    result = optimal_half_spread(
        risk_aversion=gamma,
        volatility=sigma,
        time_to_horizon=tau,
        distance_sensitivity=k,
    )

    assert result == pytest.approx(expected)


def test_half_spread_narrows_toward_horizon() -> None:
    early = optimal_half_spread(
        risk_aversion=0.003,
        volatility=1.0,
        time_to_horizon=1.0,
        distance_sensitivity=18.0,
    )

    late = optimal_half_spread(
        risk_aversion=0.003,
        volatility=1.0,
        time_to_horizon=0.0,
        distance_sensitivity=18.0,
    )

    assert early > late
    assert late > 0.0


def test_zero_inventory_produces_symmetric_quote() -> None:
    strategy = build_strategy()

    quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=0.0,
        time=0.0,
    )

    assert quote.bid == pytest.approx(99.94)
    assert quote.ask == pytest.approx(100.06)
    assert 100.0 - quote.bid == pytest.approx(
        quote.ask - 100.0
    )


def test_positive_inventory_shifts_quotes_down() -> None:
    strategy = build_strategy()

    quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=10.0,
        time=0.0,
    )

    diagnostics = strategy.diagnostics()

    assert diagnostics["reservation_price"] == pytest.approx(
        99.97
    )
    assert quote.bid < 99.94
    assert quote.ask < 100.06
    assert diagnostics["as_bid_distance"] > (
        diagnostics["as_ask_distance"]
    )


def test_negative_inventory_shifts_quotes_up() -> None:
    strategy = build_strategy()

    quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=-10.0,
        time=0.0,
    )

    diagnostics = strategy.diagnostics()

    assert diagnostics["reservation_price"] == pytest.approx(
        100.03
    )
    assert quote.bid > 99.94
    assert quote.ask > 100.06
    assert diagnostics["as_bid_distance"] < (
        diagnostics["as_ask_distance"]
    )


def test_passive_constraint_clips_marketable_side() -> None:
    strategy = build_strategy()

    quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=40.0,
        time=0.0,
    )

    diagnostics = strategy.diagnostics()

    assert quote.ask > 100.0
    assert diagnostics["as_ask_clipped"] == 1.0
    assert diagnostics["as_bid_clipped"] == 0.0


def test_inventory_limit_controls_displayed_size() -> None:
    strategy = build_strategy()

    long_limit_quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=40.0,
        time=0.0,
    )

    short_limit_quote = strategy.generate_quote(
        mid_price=100.0,
        inventory=-40.0,
        time=0.0,
    )

    assert long_limit_quote.bid_size == pytest.approx(0.0)
    assert long_limit_quote.ask_size == pytest.approx(4.0)

    assert short_limit_quote.bid_size == pytest.approx(4.0)
    assert short_limit_quote.ask_size == pytest.approx(0.0)


def test_invalid_core_parameters_raise() -> None:
    with pytest.raises(ValueError):
        reservation_price(
            mid_price=100.0,
            inventory=0.0,
            risk_aversion=0.0,
            volatility=1.0,
            time_to_horizon=1.0,
        )

    with pytest.raises(ValueError):
        optimal_half_spread(
            risk_aversion=0.003,
            volatility=1.0,
            time_to_horizon=1.0,
            distance_sensitivity=0.0,
        )