"""Path and strategy performance metrics."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .simulator import SimulationResult
from .pnl_attribution import attribute_market_making_pnl, summarize_trade_markouts

def summarize_simulation(result: SimulationResult) -> dict[str, float | bool]:
    x=result.intervals
    inv=x["inventory_after_fills"].to_numpy(float)
    wealth=x["wealth_end"].to_numpy(float)
    peak=np.maximum.accumulate(np.concatenate(([result.initial_wealth],wealth)))
    path=np.concatenate(([result.initial_wealth],wealth))
    dd=peak-path
    a=attribute_market_making_pnl(result)
    m=summarize_trade_markouts(result.trades)
    return {
        "terminal_pnl":result.terminal_pnl,
        "total_traded_quantity":m["total_traded_quantity"],
        "total_spread_capture":a.passive_spread_capture,
        "maker_fee_pnl":a.maker_fee_pnl,
        "information_price_pnl":a.information_price_pnl,
        "noise_price_pnl":a.noise_price_pnl,
        "jump_price_pnl":a.jump_price_pnl,
        "forced_execution_pnl":a.forced_execution_pnl,
        "terminal_adjustment_pnl":a.terminal_inventory_adjustment_pnl,
        "mean_absolute_inventory":float(np.mean(np.abs(inv))),
        "maximum_absolute_inventory":float(np.max(np.abs(inv))),
        "maximum_drawdown":float(np.max(dd)),
        "markout_per_unit":m["markout_per_unit"],
        "price_component_per_unit":m["price_component_per_unit"],
        "negative_markout_probability":m["negative_markout_probability"],
        "toxic_fraction":m["toxic_fraction"],
        "forced_reduction_count":result.forced_reduction_count,
        "permanently_halted":result.permanently_halted,
        "reconciliation_error":a.reconciliation_error,
        "maximum_interval_error":float(x["reconciliation_error"].abs().max()),
    }

def summarize_strategy_results(path_results: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for (scenario,strategy),g in path_results.groupby(["scenario","strategy"],sort=True):
        pnl=g.terminal_pnl.to_numpy(float); q5=float(np.quantile(pnl,.05)); tail=pnl[pnl<=q5]
        rows.append({
            "scenario":scenario,"strategy":strategy,"number_of_paths":len(g),
            "mean_terminal_pnl":float(pnl.mean()),"median_terminal_pnl":float(np.median(pnl)),
            "pnl_standard_deviation":float(pnl.std(ddof=1)),"pnl_1_percentile":float(np.quantile(pnl,.01)),
            "pnl_5_percentile":q5,"pnl_95_percentile":float(np.quantile(pnl,.95)),
            "worst_terminal_pnl":float(pnl.min()),"probability_of_loss":float(np.mean(pnl<0)),
            "expected_shortfall_5":float(tail.mean()),"mean_maximum_drawdown":float(g.maximum_drawdown.mean()),
            "mean_absolute_inventory":float(g.mean_absolute_inventory.mean()),
            "mean_maximum_inventory":float(g.maximum_absolute_inventory.mean()),
            "mean_traded_quantity":float(g.total_traded_quantity.mean()),
            "mean_markout_per_unit":float(g.markout_per_unit.mean()),
            "mean_toxic_fraction":float(g.toxic_fraction.mean()),
            "mean_forced_reduction_count":float(g.forced_reduction_count.mean()),
            "halt_probability":float(g.permanently_halted.mean()),
            "maximum_reconciliation_error":float(g.reconciliation_error.abs().max()),
        })
    return pd.DataFrame(rows)
