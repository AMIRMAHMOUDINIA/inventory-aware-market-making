"""Paired Monte Carlo strategy comparison."""
from __future__ import annotations
import pandas as pd
from .simulator import SimulationConfig, run_market_making_simulation
from .scenarios import build_scenario_model, SCENARIOS
from .strategy_factory import StrategySpec, build_strategy, build_risk_manager
from .metrics import summarize_simulation

def run_path(scenario: str, spec: StrategySpec, seed: int, steps: int=400):
    config=SimulationConfig(number_of_steps=steps,time_horizon=1.0,seed=seed,liquidate_at_end=True)
    strategy=build_strategy(spec,1.0/steps,SCENARIOS[scenario].volatility)
    risk,execution=build_risk_manager(spec)
    model=build_scenario_model(scenario,steps)
    return run_market_making_simulation(config,strategy,coupled_market_model=model,
                                        risk_manager=risk,aggressive_execution_config=execution)

def run_strategy_comparison(scenarios, strategies, number_of_paths: int, base_seed: int, steps: int=400) -> pd.DataFrame:
    rows=[]
    for scenario in scenarios:
        for path_id in range(number_of_paths):
            seed=base_seed+path_id
            for spec in strategies:
                result=run_path(scenario,spec,seed,steps)
                rows.append({"scenario":scenario,"strategy":spec.name,"path_id":path_id,"seed":seed,**summarize_simulation(result)})
    return pd.DataFrame(rows)
