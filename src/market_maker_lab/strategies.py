"""Quoting strategies."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections.abc import Sequence
from .market_primitives import Quote, Trade
from .quoting import construct_quote, volatility_adjusted_half_spread
from .volatility_estimators import ConstantVolatilityEstimator, EWMAAbsoluteVolatilityEstimator
from .adverse_selection_estimators import EWMAAdverseSelectionEstimator

@dataclass
class AdaptiveMarketMakingStrategy:
    name: str
    base_half_spread: float
    order_size: float
    tick_size: float
    inventory_limit: float
    inventory_skew: float = 0.0
    volatility_sensitivity: float = 0.0
    quote_horizon: float = 0.001
    minimum_half_spread: float = 0.005
    maximum_half_spread: float = 0.30
    minimum_quote_distance: float = 0.001
    maximum_quote_distance: float = 0.40
    toxicity_sensitivity: float = 0.0
    volatility_estimator: object = field(default_factory=lambda: ConstantVolatilityEstimator(0.0))
    adverse_selection_estimator: EWMAAdverseSelectionEstimator = field(default_factory=lambda: EWMAAdverseSelectionEstimator(0.9))
    _last_target_half_spread: float = field(init=False, default=float("nan"), repr=False)

    def reset(self) -> None:
        if hasattr(self.volatility_estimator, "reset"):
            self.volatility_estimator.reset()
        self.adverse_selection_estimator.reset()
        self._last_target_half_spread = float("nan")

    def observe_market(self, mid_price: float, time: float) -> None:
        self.volatility_estimator.update(mid_price, time)

    def observe_interval(self, mid_price_start: float, mid_price_end: float, trades: Sequence[Trade]) -> None:
        self.adverse_selection_estimator.update(trades, mid_price_start, mid_price_end)

    def generate_quote(self, mid_price: float, inventory: float, time: float) -> Quote:
        del time
        h = volatility_adjusted_half_spread(
            self.base_half_spread,
            float(self.volatility_estimator.current_volatility),
            self.volatility_sensitivity,
            self.quote_horizon,
            self.minimum_half_spread,
            self.maximum_half_spread,
        )
        self._last_target_half_spread = h
        return construct_quote(
            mid_price=mid_price,
            inventory=inventory,
            half_spread=h,
            inventory_skew=self.inventory_skew,
            minimum_quote_distance=self.minimum_quote_distance,
            maximum_quote_distance=self.maximum_quote_distance,
            order_size=self.order_size,
            tick_size=self.tick_size,
            inventory_limit=self.inventory_limit,
            bid_adverse_loss=self.adverse_selection_estimator.bid_loss,
            ask_adverse_loss=self.adverse_selection_estimator.ask_loss,
            toxicity_sensitivity=self.toxicity_sensitivity,
        )

    def diagnostics(self) -> dict[str, float]:
        return {
            "estimated_volatility": float(self.volatility_estimator.current_volatility),
            "target_half_spread": float(self._last_target_half_spread),
            "estimated_bid_adverse_loss": float(self.adverse_selection_estimator.bid_loss),
            "estimated_ask_adverse_loss": float(self.adverse_selection_estimator.ask_loss),
        }


def fixed_strategy(half_spread: float, order_size: float, tick_size: float, inventory_limit: float) -> AdaptiveMarketMakingStrategy:
    return AdaptiveMarketMakingStrategy(
        name="fixed", base_half_spread=half_spread, order_size=order_size, tick_size=tick_size,
        inventory_limit=inventory_limit, minimum_half_spread=half_spread, maximum_half_spread=half_spread,
        minimum_quote_distance=min(tick_size, half_spread), maximum_quote_distance=1.0,
    )


def inventory_strategy(half_spread: float, inventory_skew: float, order_size: float, tick_size: float, inventory_limit: float) -> AdaptiveMarketMakingStrategy:
    s = fixed_strategy(half_spread, order_size, tick_size, inventory_limit)
    s.name = "inventory"
    s.inventory_skew = inventory_skew
    return s


def volatility_inventory_strategy(
    base_half_spread: float, inventory_skew: float, volatility_sensitivity: float,
    order_size: float, tick_size: float, inventory_limit: float, quote_horizon: float,
    initial_volatility: float = 1.0, volatility_decay: float = 0.94,
) -> AdaptiveMarketMakingStrategy:
    return AdaptiveMarketMakingStrategy(
        name="inventory_volatility", base_half_spread=base_half_spread, order_size=order_size,
        tick_size=tick_size, inventory_limit=inventory_limit, inventory_skew=inventory_skew,
        volatility_sensitivity=volatility_sensitivity, quote_horizon=quote_horizon,
        minimum_half_spread=max(tick_size, 0.005), maximum_half_spread=0.30,
        minimum_quote_distance=max(tick_size, 0.001), maximum_quote_distance=0.40,
        volatility_estimator=EWMAAbsoluteVolatilityEstimator(volatility_decay, initial_volatility, 0.0, 10.0),
    )


def full_adaptive_strategy(
    base_half_spread: float, inventory_skew: float, volatility_sensitivity: float, toxicity_sensitivity: float,
    order_size: float, tick_size: float, inventory_limit: float, quote_horizon: float,
    initial_volatility: float = 1.0, volatility_decay: float = 0.94, toxicity_decay: float = 0.90,
) -> AdaptiveMarketMakingStrategy:
    s = volatility_inventory_strategy(
        base_half_spread, inventory_skew, volatility_sensitivity, order_size, tick_size,
        inventory_limit, quote_horizon, initial_volatility, volatility_decay,
    )
    s.name = "full_adaptive"
    s.toxicity_sensitivity = toxicity_sensitivity
    s.adverse_selection_estimator = EWMAAdverseSelectionEstimator(toxicity_decay, maximum_loss=1.0)
    return s
