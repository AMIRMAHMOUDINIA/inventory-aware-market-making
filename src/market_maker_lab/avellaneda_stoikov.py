"""Finite-horizon Avellaneda-Stoikov market-making strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, log1p

from .market_primitives import (
    Quote,
    round_ask_to_tick,
    round_bid_to_tick,
    validate_quote,
)
from .volatility_estimators import EWMAAbsoluteVolatilityEstimator


def reservation_price(
    mid_price: float,
    inventory: float,
    risk_aversion: float,
    volatility: float,
    time_to_horizon: float,
) -> float:
    """Return the Avellaneda-Stoikov reservation price.

    r = S - q * gamma * sigma^2 * (T - t)
    """
    values = (
        mid_price,
        inventory,
        risk_aversion,
        volatility,
        time_to_horizon,
    )

    if not all(isfinite(value) for value in values):
        raise ValueError("Reservation-price inputs must be finite.")

    if mid_price <= 0:
        raise ValueError("Mid price must be positive.")

    if risk_aversion <= 0:
        raise ValueError("Risk aversion must be positive.")

    if volatility < 0:
        raise ValueError("Volatility cannot be negative.")

    if time_to_horizon < 0:
        raise ValueError("Time to horizon cannot be negative.")

    return float(
        mid_price - inventory * risk_aversion * volatility**2 * time_to_horizon
    )


def optimal_half_spread(
    risk_aversion: float,
    volatility: float,
    time_to_horizon: float,
    distance_sensitivity: float,
) -> float:
    """Return the finite-horizon Avellaneda-Stoikov optimal half-spread.

    h = 0.5 * gamma * sigma^2 * (T - t)
        + log(1 + gamma / k) / gamma
    """
    values = (
        risk_aversion,
        volatility,
        time_to_horizon,
        distance_sensitivity,
    )

    if not all(isfinite(value) for value in values):
        raise ValueError("Half-spread inputs must be finite.")

    if risk_aversion <= 0:
        raise ValueError("Risk aversion must be positive.")

    if volatility < 0:
        raise ValueError("Volatility cannot be negative.")

    if time_to_horizon < 0:
        raise ValueError("Time to horizon cannot be negative.")

    if distance_sensitivity <= 0:
        raise ValueError("Distance sensitivity must be positive.")

    inventory_risk_component = 0.5 * risk_aversion * volatility**2 * time_to_horizon

    liquidity_component = log1p(risk_aversion / distance_sensitivity) / risk_aversion

    return float(inventory_risk_component + liquidity_component)


@dataclass
class AvellanedaStoikovStrategy:
    """Finite-horizon Avellaneda-Stoikov quoting benchmark."""

    risk_aversion: float
    distance_sensitivity: float
    time_horizon: float
    order_size: float
    tick_size: float
    inventory_limit: float
    minimum_quote_distance: float = 0.001
    maximum_quote_distance: float = 0.40
    volatility_estimator: object = field(
        default_factory=lambda: EWMAAbsoluteVolatilityEstimator(
            decay=0.94,
            initial_volatility=1.0,
            minimum_volatility=0.0,
            maximum_volatility=10.0,
        )
    )
    name: str = "avellaneda_stoikov"

    _last_reservation_price: float = field(
        init=False,
        default=float("nan"),
        repr=False,
    )
    _last_target_half_spread: float = field(
        init=False,
        default=float("nan"),
        repr=False,
    )
    _last_time_to_horizon: float = field(
        init=False,
        default=float("nan"),
        repr=False,
    )
    _last_bid_distance: float = field(
        init=False,
        default=float("nan"),
        repr=False,
    )
    _last_ask_distance: float = field(
        init=False,
        default=float("nan"),
        repr=False,
    )
    _last_bid_clipped: float = field(
        init=False,
        default=0.0,
        repr=False,
    )
    _last_ask_clipped: float = field(
        init=False,
        default=0.0,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isfinite(self.risk_aversion) or self.risk_aversion <= 0:
            raise ValueError("Risk aversion must be finite and positive.")

        if not isfinite(self.distance_sensitivity) or self.distance_sensitivity <= 0:
            raise ValueError("Distance sensitivity must be finite and positive.")

        if not isfinite(self.time_horizon) or self.time_horizon <= 0:
            raise ValueError("Time horizon must be finite and positive.")

        if not isfinite(self.order_size) or self.order_size <= 0:
            raise ValueError("Order size must be finite and positive.")

        if not isfinite(self.tick_size) or self.tick_size <= 0:
            raise ValueError("Tick size must be finite and positive.")

        if not isfinite(self.inventory_limit) or self.inventory_limit <= 0:
            raise ValueError("Inventory limit must be finite and positive.")

        if (
            not isfinite(self.minimum_quote_distance)
            or self.minimum_quote_distance <= 0
        ):
            raise ValueError("Minimum quote distance must be finite and positive.")

        if (
            not isfinite(self.maximum_quote_distance)
            or self.maximum_quote_distance < self.minimum_quote_distance
        ):
            raise ValueError("Invalid maximum quote distance.")

        if not hasattr(
            self.volatility_estimator,
            "current_volatility",
        ):
            raise ValueError("Volatility estimator must expose current_volatility.")

    def reset(self) -> None:
        reset = getattr(
            self.volatility_estimator,
            "reset",
            None,
        )

        if callable(reset):
            reset()

        self._last_reservation_price = float("nan")
        self._last_target_half_spread = float("nan")
        self._last_time_to_horizon = float("nan")
        self._last_bid_distance = float("nan")
        self._last_ask_distance = float("nan")
        self._last_bid_clipped = 0.0
        self._last_ask_clipped = 0.0

    def observe_market(
        self,
        mid_price: float,
        time: float,
    ) -> None:
        self.volatility_estimator.update(
            mid_price,
            time,
        )

    def generate_quote(
        self,
        mid_price: float,
        inventory: float,
        time: float,
    ) -> Quote:
        if not all(
            isfinite(value)
            for value in (
                mid_price,
                inventory,
                time,
            )
        ):
            raise ValueError("Quote inputs must be finite.")

        if mid_price <= 0:
            raise ValueError("Mid price must be positive.")

        if time < 0 or time > self.time_horizon + 1e-12:
            raise ValueError("Quote time must lie within the strategy horizon.")

        if abs(inventory) > self.inventory_limit + 1e-12:
            raise ValueError("Inventory exceeds configured limit.")

        volatility = float(self.volatility_estimator.current_volatility)

        if not isfinite(volatility) or volatility < 0:
            raise ValueError("Estimated volatility must be finite and non-negative.")

        time_to_horizon = max(
            self.time_horizon - time,
            0.0,
        )

        target_reservation_price = reservation_price(
            mid_price=mid_price,
            inventory=inventory,
            risk_aversion=self.risk_aversion,
            volatility=volatility,
            time_to_horizon=time_to_horizon,
        )

        target_half_spread = optimal_half_spread(
            risk_aversion=self.risk_aversion,
            volatility=volatility,
            time_to_horizon=time_to_horizon,
            distance_sensitivity=self.distance_sensitivity,
        )

        theoretical_bid = target_reservation_price - target_half_spread

        theoretical_ask = target_reservation_price + target_half_spread

        theoretical_bid_distance = mid_price - theoretical_bid

        theoretical_ask_distance = theoretical_ask - mid_price

        bid_distance = min(
            max(
                theoretical_bid_distance,
                self.minimum_quote_distance,
            ),
            self.maximum_quote_distance,
        )

        ask_distance = min(
            max(
                theoretical_ask_distance,
                self.minimum_quote_distance,
            ),
            self.maximum_quote_distance,
        )

        bid_clipped = not (
            self.minimum_quote_distance
            <= theoretical_bid_distance
            <= self.maximum_quote_distance
        )

        ask_clipped = not (
            self.minimum_quote_distance
            <= theoretical_ask_distance
            <= self.maximum_quote_distance
        )

        unrounded_bid = mid_price - bid_distance

        unrounded_ask = mid_price + ask_distance

        if unrounded_bid <= 0:
            raise ValueError("Configured quote distance produces a non-positive bid.")

        bid = round_bid_to_tick(
            unrounded_bid,
            self.tick_size,
        )

        ask = round_ask_to_tick(
            unrounded_ask,
            self.tick_size,
        )

        bid_size = max(
            0.0,
            min(
                self.order_size,
                self.inventory_limit - inventory,
            ),
        )

        ask_size = max(
            0.0,
            min(
                self.order_size,
                self.inventory_limit + inventory,
            ),
        )

        quote = Quote(
            bid=bid,
            ask=ask,
            bid_size=float(bid_size),
            ask_size=float(ask_size),
        )

        validate_quote(quote)

        self._last_reservation_price = target_reservation_price
        self._last_target_half_spread = target_half_spread
        self._last_time_to_horizon = time_to_horizon
        self._last_bid_distance = bid_distance
        self._last_ask_distance = ask_distance
        self._last_bid_clipped = float(bid_clipped)
        self._last_ask_clipped = float(ask_clipped)

        return quote

    def diagnostics(self) -> dict[str, float]:
        return {
            "estimated_volatility": float(self.volatility_estimator.current_volatility),
            "reservation_price": float(self._last_reservation_price),
            "target_half_spread": float(self._last_target_half_spread),
            "time_to_horizon": float(self._last_time_to_horizon),
            "as_bid_distance": float(self._last_bid_distance),
            "as_ask_distance": float(self._last_ask_distance),
            "as_bid_clipped": float(self._last_bid_clipped),
            "as_ask_clipped": float(self._last_ask_clipped),
        }
