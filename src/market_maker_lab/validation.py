"""Simulation integrity checks."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .pnl_attribution import attribute_market_making_pnl

def validate_simulation_result(result, hard_inventory_limit: float|None=None, tolerance: float=1e-8) -> pd.Series:
    x=result.intervals; a=attribute_market_making_pnl(result)
    checks={
        "positive_mid_prices":bool((x.mid_start>0).all() and (x.mid_end>0).all()),
        "non_crossed_quotes":bool((x.quote_ask>=x.quote_bid).all()),
        "interval_reconciliation_pass":bool(x.reconciliation_error.abs().max()<=tolerance),
        "terminal_reconciliation_pass":bool(abs(a.reconciliation_error)<=tolerance),
        "maximum_interval_error":float(x.reconciliation_error.abs().max()),
        "terminal_reconciliation_error":float(a.reconciliation_error),
    }
    if hard_inventory_limit is not None:
        checks["inventory_limit_pass"]=bool(x.inventory_after_fills.abs().max()<=hard_inventory_limit+tolerance)
    if not result.trades.empty:
        checks["markout_identity_pass"]=bool(np.allclose(result.trades.one_step_markout,
             result.trades.immediate_spread_capture+result.trades.post_trade_price_component,atol=tolerance))
    return pd.Series(checks)
