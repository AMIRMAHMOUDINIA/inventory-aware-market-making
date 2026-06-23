"""Rebuild the eight fixed-seed notebooks from the saved experiment outputs."""
from __future__ import annotations
import sys
from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
NB=ROOT/"notebooks"; NB.mkdir(exist_ok=True)

SETUP='''from pathlib import Path\nimport sys\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nROOT = Path.cwd() if (Path.cwd()/"src").exists() else Path.cwd().parent\nsys.path.insert(0, str(ROOT/"src"))\npd.set_option("display.max_columns", 30)'''

notebooks=[
("01_market_microstructure.ipynb","Market microstructure and trade accounting",[
("I start with the difference between execution edge and later markout. The representative toxic-flow path makes it possible to see a fill earn spread immediately and then lose that edge after the mid-price moves.",),
'''from market_maker_lab.analysis import fill_intensity, expected_spread_rate\nh=np.linspace(0.005,0.16,80)\nframe=pd.DataFrame({"half_spread":h,"fill_intensity":[fill_intensity(x,90,18) for x in h],"gross_revenue_rate":[expected_spread_rate(x,90,18) for x in h]})\nframe.loc[frame.gross_revenue_rate.idxmax()]''',
'''trades=pd.read_csv(ROOT/"outputs/data/representative_toxic_fixed_trades.csv")\ntrades[["side","price","quantity","quote_mid","immediate_spread_capture","post_trade_price_component","one_step_markout"]].head(10)''',
'''plt.figure(figsize=(8,5)); plt.plot(frame.half_spread,frame.fill_intensity,label="Fill intensity"); plt.plot(frame.half_spread,frame.gross_revenue_rate,label="Gross revenue rate"); plt.xlabel("Half-spread"); plt.legend(); plt.title("Execution probability versus edge per fill"); plt.show()'''
]),
("02_event_driven_simulator.ipynb","Event-driven simulation and exact accounting",[
("I use this notebook to inspect the event order directly. Risk actions, passive fills, and the price update are recorded in separate columns so the interval P&L can be rebuilt without hidden steps.",),
'''from market_maker_lab.monte_carlo import run_path\nfrom market_maker_lab.strategy_factory import DEFAULT_STRATEGIES\nresult=run_path("clean",DEFAULT_STRATEGIES[0],50123,steps=40)\nresult.intervals[["step","mid_start","quote_bid","quote_ask","bid_fill_quantity","ask_fill_quantity","inventory_after_fills","wealth_end"]].head(12)''',
'''result.intervals[["exact_interval_pnl","attributed_interval_pnl","reconciliation_error"]].describe()''',
'''assert result.intervals.reconciliation_error.abs().max() < 1e-9\nprint("Maximum interval error:",result.intervals.reconciliation_error.abs().max())'''
]),
("03_fixed_spread_baseline.ipynb","Fixed-spread baseline",[
("I use fixed quoting as the reference case because it exposes the basic trade-off between earning more per fill and receiving fewer fills.",),
'''from market_maker_lab.analysis import expected_spread_rate, optimal_half_spread\nh=np.linspace(.005,.15,120)\nr=np.array([expected_spread_rate(x,90,18) for x in h])\nprint("Analytical gross-revenue optimum:",optimal_half_spread(18))\nprint("Grid optimum:",h[r.argmax()])''',
'''plt.figure(figsize=(8,5)); plt.plot(h,r); plt.axvline(optimal_half_spread(18),linestyle="--"); plt.xlabel("Half-spread"); plt.ylabel("Expected gross spread rate"); plt.title("Fixed-spread analytical benchmark"); plt.show()''',
'''summary=pd.read_csv(ROOT/"outputs/tables/strategy_summary.csv")\nsummary[summary.strategy=="fixed"][["scenario","mean_terminal_pnl","pnl_5_percentile","mean_absolute_inventory","mean_traded_quantity"]]'''
]),
("04_inventory_aware_quoting.ipynb","Inventory-aware quote skew",[
("I check whether inventory skew actually changes the direction of expected fills: positive inventory should move the bid away and the ask closer, encouraging inventory reduction.",),
'''from market_maker_lab.quoting import construct_quote\nrows=[]\nfor q in range(-20,21,2):\n    quote=construct_quote(100,q,.05,.003,.005,.4,4,.001,40)\n    rows.append({"inventory":q,"bid":quote.bid,"ask":quote.ask,"bid_distance":100-quote.bid,"ask_distance":quote.ask-100})\nquotes=pd.DataFrame(rows); quotes.head()''',
'''plt.figure(figsize=(8,5)); plt.plot(quotes.inventory,quotes.bid_distance,label="Bid distance"); plt.plot(quotes.inventory,quotes.ask_distance,label="Ask distance"); plt.axvline(0,linewidth=1); plt.xlabel("Inventory"); plt.ylabel("Distance from mid"); plt.legend(); plt.title("Inventory changes quote asymmetry"); plt.show()''',
'''robust=pd.read_csv(ROOT/"outputs/tables/robustness_inventory_skew.csv")\nrobust[["inventory_skew","mean_terminal_pnl","pnl_5_percentile","mean_absolute_inventory","mean_maximum_inventory"]]'''
]),
("05_volatility_aware_spreads.ipynb","Volatility-aware spread width",[
("I separate two controls here: estimated volatility changes total width, while inventory continues to change asymmetry. The regime-switching path shows the lag in the EWMA response.",),
'''path=pd.read_csv(ROOT/"outputs/data/representative_regime_switching_full_adaptive_intervals.csv")\npath[["time_start","process_volatility","estimated_volatility","target_half_spread","effective_half_spread"]].head()''',
'''plt.figure(figsize=(9,5)); plt.plot(path.time_start,path.process_volatility,label="True volatility"); plt.plot(path.time_start,path.estimated_volatility,label="EWMA estimate"); plt.plot(path.time_start,path.target_half_spread,label="Target half-spread"); plt.xlabel("Time"); plt.legend(); plt.title("Regime detection and quote-width response"); plt.show()''',
'''pd.read_csv(ROOT/"outputs/tables/robustness_volatility.csv")[["volatility_sensitivity","mean_terminal_pnl","pnl_5_percentile","mean_traded_quantity","mean_absolute_inventory"]]'''
]),
("06_adverse_selection.ipynb","Adverse selection and markouts",[
("I use a latent signal to create adverse selection in a controlled way, then examine markouts at several horizons to see whether the initial execution edge survives.",),
'''curve=pd.read_csv(ROOT/"outputs/tables/markout_curve_toxic_fixed.csv")\ncurve''',
'''plt.figure(figsize=(8,5)); plt.plot(curve.horizon_steps,curve.markout_per_unit,marker="o",label="Markout"); plt.plot(curve.horizon_steps,curve.price_component_per_unit,marker="o",label="Post-fill price component"); plt.axhline(0,linewidth=1); plt.xlabel("Horizon (steps)"); plt.ylabel("P&L per unit"); plt.legend(); plt.title("Toxic-flow markout curve"); plt.show()''',
'''summary=pd.read_csv(ROOT/"outputs/tables/strategy_summary.csv")\nsummary[summary.scenario=="toxic"][["strategy","mean_terminal_pnl","pnl_5_percentile","mean_markout_per_unit","mean_toxic_fraction"]]'''
]),
("07_risk_controls.ipynb","Risk states and forced execution",[
("I trace one stress path through reduce-only, cooldown, forced-reduction, and halted states to see exactly when the risk layer overrides the quote logic and what that intervention costs.",),
'''risk=pd.read_csv(ROOT/"outputs/data/representative_stress_full_risk_risk_events.csv")\nrisk''',
'''intervals=pd.read_csv(ROOT/"outputs/data/representative_stress_full_risk_intervals.csv")\nmapping={"normal":0,"reduce_only":1,"cooldown":2,"forced_reduction":3,"halted":4}\nplt.figure(figsize=(9,4)); plt.step(intervals.time_start,intervals.risk_state.map(mapping),where="post"); plt.yticks(list(mapping.values()),list(mapping.keys())); plt.xlabel("Time"); plt.title("Stress-path risk states"); plt.show()''',
'''pd.read_csv(ROOT/"outputs/tables/robustness_risk_limits.csv")'''
]),
("08_full_evaluation_and_pnl_attribution.ipynb","Full strategy evaluation and P&L attribution",[
("I bring the separate pieces together here: paired strategy comparisons, exact P&L components, bootstrap intervals, and the validation residuals.",),
'''summary=pd.read_csv(ROOT/"outputs/tables/strategy_summary.csv")\nsummary[["scenario","strategy","mean_terminal_pnl","pnl_5_percentile","mean_absolute_inventory","mean_markout_per_unit"]].head(15)''',
'''attrib=pd.read_csv(ROOT/"outputs/tables/pnl_attribution_summary.csv")\nattrib[attrib.scenario=="stress"]''',
'''pairs=pd.read_csv(ROOT/"outputs/tables/paired_strategy_comparisons.csv")\npairs[(pairs.scenario.isin(["toxic","stress"])) & (pairs.strategy_a.isin(["inventory_volatility","full_adaptive","full_risk"]))]''',
'''validation=pd.read_csv(ROOT/"outputs/tables/validation_summary.csv")\nvalidation'''
]),
]

for filename,title,cellspec in notebooks:
    nb=nbf.v4.new_notebook()
    cells=[nbf.v4.new_markdown_cell(f"# {title}\n\nI use fixed seeds here so the numerical examples remain comparable when the implementation changes."),nbf.v4.new_code_cell(SETUP)]
    for item in cellspec:
        if isinstance(item,tuple): cells.append(nbf.v4.new_markdown_cell(item[0]))
        else: cells.append(nbf.v4.new_code_cell(item))
    nb["cells"]=cells
    nb["metadata"]["kernelspec"]={"display_name":"Python 3","language":"python","name":"python3"}
    nb["metadata"]["language_info"]={"name":"python","version":sys.version.split()[0]}
    path=NB/filename
    client=NotebookClient(nb,timeout=180,kernel_name="python3",resources={"metadata":{"path":str(ROOT)}})
    executed=client.execute()
    nbf.write(executed,path)
    print("Executed",filename)
