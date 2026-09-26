"""Inventory-aware market-making research simulator."""

from .monte_carlo import run_strategy_comparison
from .simulator import SimulationConfig, SimulationResult, run_market_making_simulation
from .strategy_factory import DEFAULT_STRATEGIES, StrategySpec

__all__ = [
    "DEFAULT_STRATEGIES",
    "SimulationConfig",
    "SimulationResult",
    "StrategySpec",
    "run_market_making_simulation",
    "run_strategy_comparison",
]
