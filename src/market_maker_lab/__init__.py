"""Inventory-aware market-making research simulator."""
from .simulator import SimulationConfig, SimulationResult, run_market_making_simulation
from .strategy_factory import StrategySpec, DEFAULT_STRATEGIES
from .monte_carlo import run_strategy_comparison
__all__=["SimulationConfig","SimulationResult","run_market_making_simulation","StrategySpec","DEFAULT_STRATEGIES","run_strategy_comparison"]
