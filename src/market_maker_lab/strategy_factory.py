"""Fresh strategy and risk-control instances for Monte Carlo paths."""
from __future__ import annotations
from dataclasses import dataclass
from .strategies import fixed_strategy, inventory_strategy, volatility_inventory_strategy, full_adaptive_strategy
from .risk_controls import RiskLimits, MarketMakerRiskManager
from .aggressive_execution import AggressiveExecutionConfig

@dataclass(frozen=True)
class StrategySpec:
    name: str
    base_half_spread: float = 0.05
    inventory_skew: float = 0.0
    volatility_sensitivity: float = 0.0
    toxicity_sensitivity: float = 0.0
    order_size: float = 4.0
    tick_size: float = 0.01
    inventory_limit: float = 40.0
    risk_controlled: bool = False


def build_strategy(spec: StrategySpec, quote_horizon: float, initial_volatility: float=1.0):
    if spec.name == "fixed":
        return fixed_strategy(spec.base_half_spread,spec.order_size,spec.tick_size,spec.inventory_limit)
    if spec.name == "inventory":
        return inventory_strategy(spec.base_half_spread,spec.inventory_skew,spec.order_size,spec.tick_size,spec.inventory_limit)
    if spec.name == "inventory_volatility":
        return volatility_inventory_strategy(spec.base_half_spread,spec.inventory_skew,spec.volatility_sensitivity,
                                             spec.order_size,spec.tick_size,spec.inventory_limit,quote_horizon,initial_volatility)
    if spec.name in {"full_adaptive","full_risk"}:
        s=full_adaptive_strategy(spec.base_half_spread,spec.inventory_skew,spec.volatility_sensitivity,
                                 spec.toxicity_sensitivity,spec.order_size,spec.tick_size,spec.inventory_limit,
                                 quote_horizon,initial_volatility)
        s.name=spec.name
        return s
    raise ValueError(f"Unknown strategy: {spec.name}")


def build_risk_manager(spec: StrategySpec) -> tuple[MarketMakerRiskManager|None,AggressiveExecutionConfig]:
    execution=AggressiveExecutionConfig(0.05,0.002,0.0008)
    if not spec.risk_controlled and spec.name != "full_risk":
        return None,execution
    limits=RiskLimits(
        soft_position_limit=18.0,hard_position_limit=28.0,recovery_position_limit=8.0,
        maximum_inventory_notional=3600.0,maximum_loss=18.0,maximum_drawdown=14.0,
        minimum_cash=-10000.0,maximum_estimated_volatility=4.5,
        maximum_absolute_price_jump=0.65,cooldown_steps=8,liquidate_on_halt=True,
    )
    return MarketMakerRiskManager(limits),execution

DEFAULT_STRATEGIES=(
    StrategySpec("fixed"),
    StrategySpec("inventory",inventory_skew=0.003),
    StrategySpec("inventory_volatility",inventory_skew=0.003,volatility_sensitivity=0.55),
    StrategySpec("full_adaptive",inventory_skew=0.003,volatility_sensitivity=0.55,toxicity_sensitivity=1.1),
    StrategySpec("full_risk",inventory_skew=0.003,volatility_sensitivity=0.55,toxicity_sensitivity=1.1,risk_controlled=True),
)
