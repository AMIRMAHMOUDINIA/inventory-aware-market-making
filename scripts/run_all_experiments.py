"""Rebuild all reproducible tables, figures, and representative path data."""
from __future__ import annotations
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))

from market_maker_lab.analysis import fill_intensity, expected_spread_rate
from market_maker_lab.monte_carlo import run_strategy_comparison, run_path
from market_maker_lab.strategy_factory import DEFAULT_STRATEGIES, StrategySpec, build_strategy
from market_maker_lab.metrics import summarize_strategy_results, summarize_simulation
from market_maker_lab.statistical_comparison import paired_differences, paired_bootstrap_interval
from market_maker_lab.pnl_attribution import attribute_market_making_pnl, attribution_table, compute_markout_curve
from market_maker_lab.validation import validate_simulation_result
from market_maker_lab.scenarios import SCENARIOS, build_scenario_model
from market_maker_lab.simulator import SimulationConfig, run_market_making_simulation
from market_maker_lab.risk_controls import RiskLimits, MarketMakerRiskManager
from market_maker_lab.aggressive_execution import AggressiveExecutionConfig

FIG=ROOT/"outputs"/"figures"; TAB=ROOT/"outputs"/"tables"; DATA=ROOT/"outputs"/"data"
for d in (FIG,TAB,DATA): d.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(FIG/name,dpi=180,bbox_inches="tight"); plt.close()

def core_experiments():
    scenarios=list(SCENARIOS)
    results=run_strategy_comparison(scenarios,DEFAULT_STRATEGIES,40,50000,steps=250)
    results.to_csv(DATA/"path_results.csv.gz",index=False,compression="gzip")
    summary=summarize_strategy_results(results)
    summary.to_csv(TAB/"strategy_summary.csv",index=False)
    summary.to_csv(TAB/"scenario_summary.csv",index=False)

    pairs=[]
    for scenario in scenarios:
        for a,b in (("inventory","fixed"),("inventory_volatility","inventory"),("full_adaptive","inventory_volatility"),("full_risk","full_adaptive")):
            d=paired_differences(results,scenario,a,b)
            out=paired_bootstrap_interval(d,2500,seed=81)
            pairs.append({"scenario":scenario,"strategy_a":a,"strategy_b":b,**out})
    pd.DataFrame(pairs).to_csv(TAB/"paired_strategy_comparisons.csv",index=False)

    attrib_cols=["total_spread_capture","maker_fee_pnl","information_price_pnl","noise_price_pnl","jump_price_pnl","forced_execution_pnl","terminal_adjustment_pnl","terminal_pnl"]
    attrib=results.groupby(["scenario","strategy"])[attrib_cols].mean().reset_index()
    attrib.to_csv(TAB/"pnl_attribution_summary.csv",index=False)
    stress=summary[summary.scenario=="stress"].copy()
    stress.to_csv(TAB/"stress_test_summary.csv",index=False)
    return results,summary,attrib

def robustness_experiments():
    rows=[]
    for skew in (0.0,.0015,.003,.006):
        spec=StrategySpec("inventory",inventory_skew=skew)
        r=run_strategy_comparison(["one_sided"],[spec],18,70000,steps=140)
        row=summarize_strategy_results(r).iloc[0].to_dict(); row["inventory_skew"]=skew; rows.append(row)
    pd.DataFrame(rows).to_csv(TAB/"robustness_inventory_skew.csv",index=False)

    rows=[]
    for sens in (0.0,.25,.55,1.0):
        spec=StrategySpec("inventory_volatility",inventory_skew=.003,volatility_sensitivity=sens)
        r=run_strategy_comparison(["high_volatility"],[spec],18,71000,steps=140)
        row=summarize_strategy_results(r).iloc[0].to_dict(); row["volatility_sensitivity"]=sens; rows.append(row)
    pd.DataFrame(rows).to_csv(TAB/"robustness_volatility.csv",index=False)

    rows=[]
    for sens in (0.0,.5,1.1,2.0):
        spec=StrategySpec("full_adaptive",inventory_skew=.003,volatility_sensitivity=.55,toxicity_sensitivity=sens)
        r=run_strategy_comparison(["toxic"],[spec],18,72000,steps=140)
        row=summarize_strategy_results(r).iloc[0].to_dict(); row["toxicity_sensitivity"]=sens; rows.append(row)
    pd.DataFrame(rows).to_csv(TAB/"robustness_toxicity.csv",index=False)

    # Selected two-factor grid for a compact robustness heatmap.
    grid=[]
    for skew in (0.0,.002,.004,.006):
        for size in (1.0,4.0,8.0):
            spec=StrategySpec("inventory",inventory_skew=skew,order_size=size)
            r=run_strategy_comparison(["one_sided"],[spec],12,73000,steps=120)
            grid.append({"inventory_skew":skew,"order_size":size,
                         "mean_terminal_pnl":r.terminal_pnl.mean(),
                         "mean_absolute_inventory":r.mean_absolute_inventory.mean()})
    pd.DataFrame(grid).to_csv(TAB/"robustness_interaction_grid.csv",index=False)

    # Risk-limit comparison using the same adaptive strategy and market seeds.
    risk_rows=[]
    for hard in (18.0,28.0,40.0):
        for path_id in range(16):
            steps=140; seed=74000+path_id
            spec=StrategySpec("full_risk",inventory_skew=.003,volatility_sensitivity=.55,toxicity_sensitivity=1.1,risk_controlled=True)
            strategy=build_strategy(spec,1/steps,SCENARIOS["stress"].volatility)
            limits=RiskLimits(soft_position_limit=.65*hard,hard_position_limit=hard,recovery_position_limit=.3*hard,
                              maximum_loss=18,maximum_drawdown=14,maximum_absolute_price_jump=.65,
                              maximum_estimated_volatility=4.5,cooldown_steps=8,liquidate_on_halt=True)
            risk=MarketMakerRiskManager(limits); execution=AggressiveExecutionConfig(.05,.002,.0008)
            res=run_market_making_simulation(SimulationConfig(number_of_steps=steps,seed=seed),strategy,
                    coupled_market_model=build_scenario_model("stress",steps),risk_manager=risk,aggressive_execution_config=execution)
            risk_rows.append({"hard_position_limit":hard,"path_id":path_id,**summarize_simulation(res)})
    rr=pd.DataFrame(risk_rows)
    rr.groupby("hard_position_limit").agg(mean_terminal_pnl=("terminal_pnl","mean"),pnl_5_percentile=("terminal_pnl",lambda x: x.quantile(.05)),
       mean_maximum_inventory=("maximum_absolute_inventory","mean"),mean_forced_reductions=("forced_reduction_count","mean"),halt_probability=("permanently_halted","mean")).reset_index().to_csv(TAB/"robustness_risk_limits.csv",index=False)

def representative_outputs():
    chosen={}
    for scenario,strategy in (("toxic",DEFAULT_STRATEGIES[0]),("regime_switching",DEFAULT_STRATEGIES[3])):
        res=run_path(scenario,strategy,50555,steps=250); chosen[(scenario,strategy.name)]=res
    # Find a stress path with at least one non-normal risk state.
    for seed in range(50600,50700):
        res=run_path("stress",DEFAULT_STRATEGIES[-1],seed,steps=250)
        if res.permanently_halted or res.forced_reduction_count > 0:
            chosen[("stress","full_risk")]=res; break
    else: chosen[("stress","full_risk")]=res

    for (scenario,strategy),res in chosen.items():
        res.intervals.to_csv(DATA/f"representative_{scenario}_{strategy}_intervals.csv",index=False)
        res.trades.to_csv(DATA/f"representative_{scenario}_{strategy}_trades.csv",index=False)
        if not res.risk_events.empty: res.risk_events.to_csv(DATA/f"representative_{scenario}_{strategy}_risk_events.csv",index=False)
        attribution_table(attribute_market_making_pnl(res)).to_csv(TAB/f"attribution_{scenario}_{strategy}.csv",index=False)
        validate_simulation_result(res,28 if strategy=="full_risk" else None).to_frame("value").to_csv(TAB/f"validation_{scenario}_{strategy}.csv")
    toxic=chosen[("toxic","fixed")]
    compute_markout_curve(toxic.trades,toxic.intervals,(1,5,20,50)).to_csv(TAB/"markout_curve_toxic_fixed.csv",index=False)
    return chosen

def figures(results,summary,attrib,chosen):
    # 1 mean and downside P&L
    order=["fixed","inventory","inventory_volatility","full_adaptive","full_risk"]
    toxic=summary[summary.scenario=="toxic"].set_index("strategy").loc[order].reset_index()
    x=np.arange(len(toxic)); w=.36
    plt.figure(figsize=(10,6)); plt.bar(x-w/2,toxic.mean_terminal_pnl,w,label="Mean P&L"); plt.bar(x+w/2,toxic.pnl_5_percentile,w,label="5th percentile")
    plt.axhline(0,linewidth=1); plt.xticks(x,toxic.strategy,rotation=30,ha="right"); plt.ylabel("Terminal P&L"); plt.title("Toxic Market: Mean and Downside P&L"); plt.legend(); save("01_toxic_mean_and_tail_pnl.png")

    # 2 distributions
    plt.figure(figsize=(10,6))
    for strategy in ("fixed","inventory_volatility","full_adaptive","full_risk"):
        vals=results[(results.scenario=="toxic")&(results.strategy==strategy)].terminal_pnl
        plt.hist(vals,bins=25,alpha=.45,label=strategy)
    plt.axvline(0,linewidth=1); plt.xlabel("Terminal P&L"); plt.ylabel("Path count"); plt.title("Toxic-Market P&L Distributions"); plt.legend(); save("02_toxic_pnl_distributions.png")

    # 3 inventory
    one=summary[summary.scenario=="one_sided"]
    plt.figure(figsize=(9,6)); plt.bar(one.strategy,one.mean_absolute_inventory); plt.xticks(rotation=30,ha="right"); plt.ylabel("Mean absolute inventory"); plt.title("Inventory Exposure under One-Sided Flow"); save("03_inventory_exposure.png")

    # 4 attribution
    selected=["fixed","inventory_volatility","full_adaptive","full_risk"]
    a=attrib[attrib.scenario=="toxic"].set_index("strategy").loc[selected]
    components=["total_spread_capture","maker_fee_pnl","information_price_pnl","noise_price_pnl","forced_execution_pnl","terminal_adjustment_pnl"]
    labels=["Spread","Maker fees","Information","Noise","Forced","Terminal"]
    x=np.arange(len(components)); width=.18
    plt.figure(figsize=(10,6))
    for index,strategy_name in enumerate(selected):
        plt.bar(x+(index-1.5)*width,a.loc[strategy_name,components].to_numpy(),width,label=strategy_name)
    plt.axhline(0,linewidth=1); plt.xticks(x,labels,rotation=20); plt.ylabel("Mean P&L contribution"); plt.title("Toxic-Market Mean P&L Attribution"); plt.legend(fontsize=8); save("04_pnl_attribution.png")

    # 5 markout curve
    curve=pd.read_csv(TAB/"markout_curve_toxic_fixed.csv")
    plt.figure(figsize=(8,5)); plt.plot(curve.horizon_steps,curve.markout_per_unit,marker="o",label="Total markout"); plt.plot(curve.horizon_steps,curve.price_component_per_unit,marker="o",label="Post-fill price component"); plt.axhline(0,linewidth=1); plt.xlabel("Horizon (steps)"); plt.ylabel("P&L per unit"); plt.title("Fixed-Strategy Markout Curve in Toxic Flow"); plt.legend(); save("05_markout_curve.png")

    # 6 volatility response
    r=chosen[("regime_switching","full_adaptive")].intervals
    plt.figure(figsize=(10,6)); plt.plot(r.time_start,r.process_volatility,label="True volatility"); plt.plot(r.time_start,r.estimated_volatility,label="EWMA estimate"); plt.plot(r.time_start,r.target_half_spread,label="Target half-spread"); plt.xlabel("Time"); plt.title("Volatility Estimation and Quote-Width Response"); plt.legend(); save("06_volatility_response.png")

    # 7 risk states
    r=chosen[("stress","full_risk")].intervals
    mapping={"normal":0,"reduce_only":1,"cooldown":2,"forced_reduction":3,"halted":4}
    plt.figure(figsize=(10,5)); plt.step(r.time_start,r.risk_state.map(mapping),where="post"); plt.yticks(list(mapping.values()),list(mapping.keys())); plt.xlabel("Time"); plt.title("Risk-State Timeline in Stress Scenario"); save("07_risk_state_timeline.png")

    # 8 robustness heatmap
    g=pd.read_csv(TAB/"robustness_interaction_grid.csv"); p=g.pivot(index="inventory_skew",columns="order_size",values="mean_terminal_pnl")
    plt.figure(figsize=(8,5)); im=plt.imshow(p.to_numpy(),aspect="auto",origin="lower"); plt.xticks(range(len(p.columns)),p.columns); plt.yticks(range(len(p.index)),p.index); plt.xlabel("Order size"); plt.ylabel("Inventory skew"); plt.title("One-Sided-Flow Mean P&L Robustness"); plt.colorbar(im,label="Mean terminal P&L"); save("08_robustness_heatmap.png")

    # 9 analytical fixed-spread trade-off
    h=np.linspace(.005,.16,120); intensity=np.array([fill_intensity(x,90,18) for x in h]); revenue=np.array([expected_spread_rate(x,90,18) for x in h])
    plt.figure(figsize=(8,5)); plt.plot(h,intensity,label="Per-side fill intensity"); plt.plot(h,revenue,label="Gross spread revenue rate"); plt.xlabel("Half-spread"); plt.title("Quote Width, Fill Intensity, and Gross Revenue"); plt.legend(); save("09_fixed_spread_tradeoff.png")

def validation_summary(chosen):
    rows=[]
    for (scenario,strategy),res in chosen.items():
        v=validate_simulation_result(res,28 if strategy=="full_risk" else None)
        rows.append({"scenario":scenario,"strategy":strategy,**v.to_dict()})
    pd.DataFrame(rows).to_csv(TAB/"validation_summary.csv",index=False)

def main():
    results,summary,attrib=core_experiments()
    robustness_experiments()
    chosen=representative_outputs()
    figures(results,summary,attrib,chosen)
    validation_summary(chosen)
    print(f"Generated {len(results):,} paired path-strategy records.")
    print(summary[["scenario","strategy","mean_terminal_pnl","pnl_5_percentile","mean_markout_per_unit"]].to_string(index=False))

if __name__=="__main__": main()
