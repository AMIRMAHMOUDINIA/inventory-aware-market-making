"""Paired strategy comparisons."""
from __future__ import annotations
import numpy as np
import pandas as pd

def paired_differences(results: pd.DataFrame, scenario: str, strategy_a: str, strategy_b: str, metric: str="terminal_pnl") -> np.ndarray:
    p=results[results.scenario==scenario].pivot(index="path_id",columns="strategy",values=metric)
    return (p[strategy_a]-p[strategy_b]).dropna().to_numpy(float)

def paired_bootstrap_interval(differences: np.ndarray, number_of_bootstraps: int=3000, seed: int=123) -> dict[str,float]:
    if len(differences)==0: raise ValueError("No paired differences.")
    rng=np.random.default_rng(seed); n=len(differences)
    means=np.array([rng.choice(differences,n,replace=True).mean() for _ in range(number_of_bootstraps)])
    return {"mean_difference":float(differences.mean()),"lower_bound":float(np.quantile(means,.025)),
            "upper_bound":float(np.quantile(means,.975)),"probability_positive":float(np.mean(means>0))}
