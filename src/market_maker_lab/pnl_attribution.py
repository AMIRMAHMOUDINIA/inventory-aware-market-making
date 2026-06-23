"""Exact market-making P&L attribution."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .simulator import SimulationResult

@dataclass(frozen=True)
class PnlAttribution:
    passive_spread_capture: float
    maker_fee_pnl: float
    forced_execution_pnl: float
    drift_price_pnl: float
    information_price_pnl: float
    noise_price_pnl: float
    jump_price_pnl: float
    unclassified_price_pnl: float
    direct_adverse_selection_pnl: float
    carried_information_pnl: float
    terminal_inventory_adjustment_pnl: float
    attributed_terminal_pnl: float
    reported_terminal_pnl: float
    reconciliation_error: float


def attribute_market_making_pnl(result: SimulationResult) -> PnlAttribution:
    x = result.intervals
    spread = float(x["spread_capture"].sum())
    maker = -float(x["maker_fees"].sum())
    forced = float(x["forced_execution_pnl"].sum())
    price_total = float(x["price_move_pnl"].sum())
    classified_cols = ["drift_price_pnl", "information_price_pnl", "noise_price_pnl", "jump_price_pnl"]
    has_classified = all(c in x for c in classified_cols) and x[classified_cols].notna().any().any()
    if has_classified:
        drift, info, noise, jump = (float(np.nansum(x[c])) for c in classified_cols)
        unclassified = price_total - drift - info - noise - jump
    else:
        drift = info = noise = jump = 0.0
        unclassified = price_total
    direct = float(np.nansum(x["new_fill_information_pnl"])) if "new_fill_information_pnl" in x else 0.0
    carried = float(np.nansum(x["carried_information_pnl"])) if "carried_information_pnl" in x else 0.0
    interval_total = float((x["wealth_end"] - x["wealth_start"]).sum())
    terminal_adjustment = result.terminal_pnl - interval_total
    attributed = spread + maker + forced + drift + info + noise + jump + unclassified + terminal_adjustment
    return PnlAttribution(spread, maker, forced, drift, info, noise, jump, unclassified, direct, carried,
                          terminal_adjustment, attributed, result.terminal_pnl, result.terminal_pnl - attributed)


def attribution_table(a: PnlAttribution) -> pd.DataFrame:
    return pd.DataFrame([
        ("Passive spread capture", a.passive_spread_capture),
        ("Maker fees", a.maker_fee_pnl),
        ("Forced execution", a.forced_execution_pnl),
        ("Drift inventory P&L", a.drift_price_pnl),
        ("Information inventory P&L", a.information_price_pnl),
        ("Noise inventory P&L", a.noise_price_pnl),
        ("Jump inventory P&L", a.jump_price_pnl),
        ("Unclassified price P&L", a.unclassified_price_pnl),
        ("Terminal inventory adjustment", a.terminal_inventory_adjustment_pnl),
        ("Attributed terminal P&L", a.attributed_terminal_pnl),
        ("Reported terminal P&L", a.reported_terminal_pnl),
        ("Reconciliation error", a.reconciliation_error),
    ], columns=["component", "pnl"])


def summarize_trade_markouts(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {"total_traded_quantity": 0.0, "markout_per_unit": 0.0, "price_component_per_unit": 0.0,
                "negative_markout_probability": 0.0, "toxic_fraction": 0.0}
    q = trades["quantity"].to_numpy(float)
    total = float(q.sum())
    return {
        "total_traded_quantity": total,
        "markout_per_unit": float(trades["one_step_markout"].sum()/total),
        "price_component_per_unit": float(trades["post_trade_price_component"].sum()/total),
        "negative_markout_probability": float(np.average((trades["one_step_markout"].to_numpy(float)<0).astype(float), weights=q)),
        "toxic_fraction": float(trades["toxic_quantity"].sum()/total) if "toxic_quantity" in trades else 0.0,
    }


def compute_markout_curve(trades: pd.DataFrame, intervals: pd.DataFrame, horizons=(1,5,20,50)) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["horizon_steps","markout_per_unit","price_component_per_unit","total_quantity"])
    ordered = intervals.sort_values("step")
    grid = np.concatenate(([ordered["mid_start"].iloc[0]], ordered["mid_end"].to_numpy(float)))
    rows=[]
    for h in horizons:
        total_q=total_m=total_p=0.0
        for tr in trades.itertuples(index=False):
            target=int(tr.step)+int(h)
            if target >= len(grid): continue
            direction=1.0 if tr.side=="buy" else -1.0
            q=float(tr.quantity)
            total_q += q
            total_m += q*direction*(grid[target]-float(tr.price))
            total_p += q*direction*(grid[target]-float(tr.quote_mid))
        if total_q>0:
            rows.append({"horizon_steps":h,"markout_per_unit":total_m/total_q,
                         "price_component_per_unit":total_p/total_q,"total_quantity":total_q})
    return pd.DataFrame(rows)
