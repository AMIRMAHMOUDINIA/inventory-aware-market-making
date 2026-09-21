"""Rebuild all reproducible tables, figures, and representative path data."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_maker_lab.aggressive_execution import (
    AggressiveExecutionConfig,
)
from market_maker_lab.analysis import (
    expected_spread_rate,
    fill_intensity,
)
from market_maker_lab.metrics import (
    summarize_simulation,
    summarize_strategy_results,
)
from market_maker_lab.monte_carlo import (
    run_path,
    run_strategy_comparison,
)
from market_maker_lab.pnl_attribution import (
    attribute_market_making_pnl,
    attribution_table,
    compute_markout_curve,
)
from market_maker_lab.risk_controls import (
    MarketMakerRiskManager,
    RiskLimits,
)
from market_maker_lab.scenarios import (
    SCENARIOS,
    build_scenario_model,
)
from market_maker_lab.simulator import (
    SimulationConfig,
    run_market_making_simulation,
)
from market_maker_lab.statistical_comparison import (
    paired_bootstrap_interval,
    paired_differences,
)
from market_maker_lab.strategy_factory import (
    DEFAULT_STRATEGIES,
    StrategySpec,
    build_strategy,
)
from market_maker_lab.validation import (
    validate_simulation_result,
)


FIG = ROOT / "outputs" / "figures"
TAB = ROOT / "outputs" / "tables"
DATA = ROOT / "outputs" / "data"

for directory in (FIG, TAB, DATA):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


AVELLANEDA_STOIKOV_SPEC = StrategySpec(
    "avellaneda_stoikov",
    risk_aversion=0.003,
    distance_sensitivity=18.0,
)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(
        FIG / name,
        dpi=180,
        bbox_inches="tight",
    )
    plt.close()


def core_experiments():
    """Run the original five-strategy canonical experiment."""

    scenarios = list(SCENARIOS)

    results = run_strategy_comparison(
        scenarios,
        DEFAULT_STRATEGIES,
        40,
        50000,
        steps=250,
    )

    results.to_csv(
        DATA / "path_results.csv.gz",
        index=False,
        compression="gzip",
    )

    summary = summarize_strategy_results(
        results
    )

    summary.to_csv(
        TAB / "strategy_summary.csv",
        index=False,
    )

    summary.to_csv(
        TAB / "scenario_summary.csv",
        index=False,
    )

    pairs = []

    for scenario in scenarios:
        for strategy_a, strategy_b in (
            (
                "inventory",
                "fixed",
            ),
            (
                "inventory_volatility",
                "inventory",
            ),
            (
                "full_adaptive",
                "inventory_volatility",
            ),
            (
                "full_risk",
                "full_adaptive",
            ),
        ):
            differences = paired_differences(
                results,
                scenario,
                strategy_a,
                strategy_b,
            )

            output = paired_bootstrap_interval(
                differences,
                2500,
                seed=81,
            )

            pairs.append(
                {
                    "scenario": scenario,
                    "strategy_a": strategy_a,
                    "strategy_b": strategy_b,
                    **output,
                }
            )

    pd.DataFrame(
        pairs
    ).to_csv(
        TAB / "paired_strategy_comparisons.csv",
        index=False,
    )

    attribution_columns = [
        "total_spread_capture",
        "maker_fee_pnl",
        "information_price_pnl",
        "noise_price_pnl",
        "jump_price_pnl",
        "forced_execution_pnl",
        "terminal_adjustment_pnl",
        "terminal_pnl",
    ]

    attribution = (
        results.groupby(
            [
                "scenario",
                "strategy",
            ]
        )[attribution_columns]
        .mean()
        .reset_index()
    )

    attribution.to_csv(
        TAB / "pnl_attribution_summary.csv",
        index=False,
    )

    stress = summary[
        summary.scenario == "stress"
    ].copy()

    stress.to_csv(
        TAB / "stress_test_summary.csv",
        index=False,
    )

    return (
        results,
        summary,
        attribution,
    )


def avellaneda_stoikov_benchmark(
    canonical_results: pd.DataFrame,
):
    """Run A-S on the same paired synthetic paths as the canonical study.

    Avellaneda-Stoikov is deliberately kept outside DEFAULT_STRATEGIES.
    This preserves the original five-strategy, 1,200-record experiment
    while adding a separate 240-path theoretical benchmark.
    """

    scenarios = list(SCENARIOS)

    as_results = run_strategy_comparison(
        scenarios,
        [AVELLANEDA_STOIKOV_SPEC],
        40,
        50000,
        steps=250,
    )

    as_results.to_csv(
        DATA
        / "avellaneda_stoikov_path_results.csv.gz",
        index=False,
        compression="gzip",
    )

    as_summary = summarize_strategy_results(
        as_results
    )

    as_summary.to_csv(
        TAB / "avellaneda_stoikov_summary.csv",
        index=False,
    )

    combined = pd.concat(
        [
            canonical_results,
            as_results,
        ],
        ignore_index=True,
    )

    combined_summary = (
        summarize_strategy_results(
            combined
        )
    )

    combined_summary.to_csv(
        TAB
        / "avellaneda_stoikov_benchmark_summary.csv",
        index=False,
    )

    paired_rows = []

    reference_strategies = (
        "fixed",
        "inventory",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
    )

    for scenario in scenarios:
        for reference in reference_strategies:
            differences = paired_differences(
                combined,
                scenario,
                "avellaneda_stoikov",
                reference,
            )

            interval = paired_bootstrap_interval(
                differences,
                2500,
                seed=91,
            )

            paired_rows.append(
                {
                    "scenario": scenario,
                    "strategy_a": (
                        "avellaneda_stoikov"
                    ),
                    "strategy_b": reference,
                    **interval,
                }
            )

    paired_table = pd.DataFrame(
        paired_rows
    )

    paired_table.to_csv(
        TAB
        / "avellaneda_stoikov_paired_comparisons.csv",
        index=False,
    )

    return (
        as_results,
        as_summary,
        combined_summary,
        paired_table,
    )


def robustness_experiments():
    rows = []

    for skew in (
        0.0,
        0.0015,
        0.003,
        0.006,
    ):
        spec = StrategySpec(
            "inventory",
            inventory_skew=skew,
        )

        result = run_strategy_comparison(
            ["one_sided"],
            [spec],
            18,
            70000,
            steps=140,
        )

        row = (
            summarize_strategy_results(
                result
            )
            .iloc[0]
            .to_dict()
        )

        row["inventory_skew"] = skew
        rows.append(row)

    pd.DataFrame(
        rows
    ).to_csv(
        TAB
        / "robustness_inventory_skew.csv",
        index=False,
    )

    rows = []

    for sensitivity in (
        0.0,
        0.25,
        0.55,
        1.0,
    ):
        spec = StrategySpec(
            "inventory_volatility",
            inventory_skew=0.003,
            volatility_sensitivity=sensitivity,
        )

        result = run_strategy_comparison(
            ["high_volatility"],
            [spec],
            18,
            71000,
            steps=140,
        )

        row = (
            summarize_strategy_results(
                result
            )
            .iloc[0]
            .to_dict()
        )

        row[
            "volatility_sensitivity"
        ] = sensitivity

        rows.append(row)

    pd.DataFrame(
        rows
    ).to_csv(
        TAB / "robustness_volatility.csv",
        index=False,
    )

    rows = []

    for sensitivity in (
        0.0,
        0.5,
        1.1,
        2.0,
    ):
        spec = StrategySpec(
            "full_adaptive",
            inventory_skew=0.003,
            volatility_sensitivity=0.55,
            toxicity_sensitivity=sensitivity,
        )

        result = run_strategy_comparison(
            ["toxic"],
            [spec],
            18,
            72000,
            steps=140,
        )

        row = (
            summarize_strategy_results(
                result
            )
            .iloc[0]
            .to_dict()
        )

        row[
            "toxicity_sensitivity"
        ] = sensitivity

        rows.append(row)

    pd.DataFrame(
        rows
    ).to_csv(
        TAB / "robustness_toxicity.csv",
        index=False,
    )

    grid = []

    for skew in (
        0.0,
        0.002,
        0.004,
        0.006,
    ):
        for size in (
            1.0,
            4.0,
            8.0,
        ):
            spec = StrategySpec(
                "inventory",
                inventory_skew=skew,
                order_size=size,
            )

            result = run_strategy_comparison(
                ["one_sided"],
                [spec],
                12,
                73000,
                steps=120,
            )

            grid.append(
                {
                    "inventory_skew": skew,
                    "order_size": size,
                    "mean_terminal_pnl": (
                        result.terminal_pnl.mean()
                    ),
                    "mean_absolute_inventory": (
                        result.mean_absolute_inventory.mean()
                    ),
                }
            )

    pd.DataFrame(
        grid
    ).to_csv(
        TAB
        / "robustness_interaction_grid.csv",
        index=False,
    )

    risk_rows = []

    for hard_limit in (
        18.0,
        28.0,
        40.0,
    ):
        for path_id in range(16):
            steps = 140
            seed = 74000 + path_id

            spec = StrategySpec(
                "full_risk",
                inventory_skew=0.003,
                volatility_sensitivity=0.55,
                toxicity_sensitivity=1.1,
                risk_controlled=True,
            )

            strategy = build_strategy(
                spec,
                1 / steps,
                SCENARIOS[
                    "stress"
                ].volatility,
            )

            limits = RiskLimits(
                soft_position_limit=(
                    0.65 * hard_limit
                ),
                hard_position_limit=hard_limit,
                recovery_position_limit=(
                    0.3 * hard_limit
                ),
                maximum_loss=18,
                maximum_drawdown=14,
                maximum_absolute_price_jump=0.65,
                maximum_estimated_volatility=4.5,
                cooldown_steps=8,
                liquidate_on_halt=True,
            )

            risk = MarketMakerRiskManager(
                limits
            )

            execution = (
                AggressiveExecutionConfig(
                    0.05,
                    0.002,
                    0.0008,
                )
            )

            result = (
                run_market_making_simulation(
                    SimulationConfig(
                        number_of_steps=steps,
                        seed=seed,
                    ),
                    strategy,
                    coupled_market_model=(
                        build_scenario_model(
                            "stress",
                            steps,
                        )
                    ),
                    risk_manager=risk,
                    aggressive_execution_config=(
                        execution
                    ),
                )
            )

            risk_rows.append(
                {
                    "hard_position_limit": (
                        hard_limit
                    ),
                    "path_id": path_id,
                    **summarize_simulation(
                        result
                    ),
                }
            )

    risk_results = pd.DataFrame(
        risk_rows
    )

    (
        risk_results.groupby(
            "hard_position_limit"
        )
        .agg(
            mean_terminal_pnl=(
                "terminal_pnl",
                "mean",
            ),
            pnl_5_percentile=(
                "terminal_pnl",
                lambda x: x.quantile(
                    0.05
                ),
            ),
            mean_maximum_inventory=(
                "maximum_absolute_inventory",
                "mean",
            ),
            mean_forced_reductions=(
                "forced_reduction_count",
                "mean",
            ),
            halt_probability=(
                "permanently_halted",
                "mean",
            ),
        )
        .reset_index()
        .to_csv(
            TAB
            / "robustness_risk_limits.csv",
            index=False,
        )
    )


def representative_outputs():
    chosen = {}

    for scenario, strategy in (
        (
            "toxic",
            DEFAULT_STRATEGIES[0],
        ),
        (
            "regime_switching",
            DEFAULT_STRATEGIES[3],
        ),
    ):
        result = run_path(
            scenario,
            strategy,
            50555,
            steps=250,
        )

        chosen[
            (
                scenario,
                strategy.name,
            )
        ] = result

    for seed in range(
        50600,
        50700,
    ):
        result = run_path(
            "stress",
            DEFAULT_STRATEGIES[-1],
            seed,
            steps=250,
        )

        if (
            result.permanently_halted
            or result.forced_reduction_count
            > 0
        ):
            chosen[
                (
                    "stress",
                    "full_risk",
                )
            ] = result
            break

    else:
        chosen[
            (
                "stress",
                "full_risk",
            )
        ] = result

    for (
        scenario,
        strategy,
    ), result in chosen.items():
        result.intervals.to_csv(
            DATA
            / (
                f"representative_"
                f"{scenario}_"
                f"{strategy}_"
                f"intervals.csv"
            ),
            index=False,
        )

        result.trades.to_csv(
            DATA
            / (
                f"representative_"
                f"{scenario}_"
                f"{strategy}_"
                f"trades.csv"
            ),
            index=False,
        )

        if not result.risk_events.empty:
            result.risk_events.to_csv(
                DATA
                / (
                    f"representative_"
                    f"{scenario}_"
                    f"{strategy}_"
                    f"risk_events.csv"
                ),
                index=False,
            )

        attribution_table(
            attribute_market_making_pnl(
                result
            )
        ).to_csv(
            TAB
            / (
                f"attribution_"
                f"{scenario}_"
                f"{strategy}.csv"
            ),
            index=False,
        )

        validate_simulation_result(
            result,
            (
                28
                if strategy == "full_risk"
                else None
            ),
        ).to_frame(
            "value"
        ).to_csv(
            TAB
            / (
                f"validation_"
                f"{scenario}_"
                f"{strategy}.csv"
            )
        )

    toxic = chosen[
        (
            "toxic",
            "fixed",
        )
    ]

    compute_markout_curve(
        toxic.trades,
        toxic.intervals,
        (
            1,
            5,
            20,
            50,
        ),
    ).to_csv(
        TAB
        / "markout_curve_toxic_fixed.csv",
        index=False,
    )

    return chosen


def figures(
    results,
    summary,
    attribution,
    chosen,
):
    """Generate canonical figures 1-9."""

    order = [
        "fixed",
        "inventory",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
    ]

    toxic = (
        summary[
            summary.scenario == "toxic"
        ]
        .set_index("strategy")
        .loc[order]
        .reset_index()
    )

    x = np.arange(
        len(toxic)
    )

    width = 0.36

    plt.figure(
        figsize=(10, 6)
    )

    plt.bar(
        x - width / 2,
        toxic.mean_terminal_pnl,
        width,
        label="Mean P&L",
    )

    plt.bar(
        x + width / 2,
        toxic.pnl_5_percentile,
        width,
        label="5th percentile",
    )

    plt.axhline(
        0,
        linewidth=1,
    )

    plt.xticks(
        x,
        toxic.strategy,
        rotation=30,
        ha="right",
    )

    plt.ylabel(
        "Terminal P&L"
    )

    plt.title(
        "Toxic Market: Mean and Downside P&L"
    )

    plt.legend()

    save(
        "01_toxic_mean_and_tail_pnl.png"
    )

    plt.figure(
        figsize=(10, 6)
    )

    for strategy in (
        "fixed",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
    ):
        values = results[
            (
                results.scenario
                == "toxic"
            )
            & (
                results.strategy
                == strategy
            )
        ].terminal_pnl

        plt.hist(
            values,
            bins=25,
            alpha=0.45,
            label=strategy,
        )

    plt.axvline(
        0,
        linewidth=1,
    )

    plt.xlabel(
        "Terminal P&L"
    )

    plt.ylabel(
        "Path count"
    )

    plt.title(
        "Toxic-Market P&L Distributions"
    )

    plt.legend()

    save(
        "02_toxic_pnl_distributions.png"
    )

    one_sided = summary[
        summary.scenario
        == "one_sided"
    ]

    plt.figure(
        figsize=(9, 6)
    )

    plt.bar(
        one_sided.strategy,
        one_sided.mean_absolute_inventory,
    )

    plt.xticks(
        rotation=30,
        ha="right",
    )

    plt.ylabel(
        "Mean absolute inventory"
    )

    plt.title(
        "Inventory Exposure under One-Sided Flow"
    )

    save(
        "03_inventory_exposure.png"
    )

    selected = [
        "fixed",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
    ]

    selected_attribution = (
        attribution[
            attribution.scenario
            == "toxic"
        ]
        .set_index("strategy")
        .loc[selected]
    )

    components = [
        "total_spread_capture",
        "maker_fee_pnl",
        "information_price_pnl",
        "noise_price_pnl",
        "forced_execution_pnl",
        "terminal_adjustment_pnl",
    ]

    labels = [
        "Spread",
        "Maker fees",
        "Information",
        "Noise",
        "Forced",
        "Terminal",
    ]

    x = np.arange(
        len(components)
    )

    width = 0.18

    plt.figure(
        figsize=(10, 6)
    )

    for index, strategy_name in enumerate(
        selected
    ):
        plt.bar(
            x
            + (
                index - 1.5
            )
            * width,
            selected_attribution.loc[
                strategy_name,
                components,
            ].to_numpy(),
            width,
            label=strategy_name,
        )

    plt.axhline(
        0,
        linewidth=1,
    )

    plt.xticks(
        x,
        labels,
        rotation=20,
    )

    plt.ylabel(
        "Mean P&L contribution"
    )

    plt.title(
        "Toxic-Market Mean P&L Attribution"
    )

    plt.legend(
        fontsize=8
    )

    save(
        "04_pnl_attribution.png"
    )

    curve = pd.read_csv(
        TAB
        / "markout_curve_toxic_fixed.csv"
    )

    plt.figure(
        figsize=(8, 5)
    )

    plt.plot(
        curve.horizon_steps,
        curve.markout_per_unit,
        marker="o",
        label="Total markout",
    )

    plt.plot(
        curve.horizon_steps,
        curve.price_component_per_unit,
        marker="o",
        label="Post-fill price component",
    )

    plt.axhline(
        0,
        linewidth=1,
    )

    plt.xlabel(
        "Horizon (steps)"
    )

    plt.ylabel(
        "P&L per unit"
    )

    plt.title(
        "Fixed-Strategy Markout Curve in Toxic Flow"
    )

    plt.legend()

    save(
        "05_markout_curve.png"
    )

    regime = chosen[
        (
            "regime_switching",
            "full_adaptive",
        )
    ].intervals

    plt.figure(
        figsize=(10, 6)
    )

    plt.plot(
        regime.time_start,
        regime.process_volatility,
        label="True volatility",
    )

    plt.plot(
        regime.time_start,
        regime.estimated_volatility,
        label="EWMA estimate",
    )

    plt.plot(
        regime.time_start,
        regime.target_half_spread,
        label="Target half-spread",
    )

    plt.xlabel(
        "Time"
    )

    plt.title(
        "Volatility Estimation and Quote-Width Response"
    )

    plt.legend()

    save(
        "06_volatility_response.png"
    )

    stress = chosen[
        (
            "stress",
            "full_risk",
        )
    ].intervals

    mapping = {
        "normal": 0,
        "reduce_only": 1,
        "cooldown": 2,
        "forced_reduction": 3,
        "halted": 4,
    }

    plt.figure(
        figsize=(10, 5)
    )

    plt.step(
        stress.time_start,
        stress.risk_state.map(
            mapping
        ),
        where="post",
    )

    plt.yticks(
        list(
            mapping.values()
        ),
        list(
            mapping.keys()
        ),
    )

    plt.xlabel(
        "Time"
    )

    plt.title(
        "Risk-State Timeline in Stress Scenario"
    )

    save(
        "07_risk_state_timeline.png"
    )

    grid = pd.read_csv(
        TAB
        / "robustness_interaction_grid.csv"
    )

    pivot = grid.pivot(
        index="inventory_skew",
        columns="order_size",
        values="mean_terminal_pnl",
    )

    plt.figure(
        figsize=(8, 5)
    )

    image = plt.imshow(
        pivot.to_numpy(),
        aspect="auto",
        origin="lower",
    )

    plt.xticks(
        range(
            len(
                pivot.columns
            )
        ),
        pivot.columns,
    )

    plt.yticks(
        range(
            len(
                pivot.index
            )
        ),
        pivot.index,
    )

    plt.xlabel(
        "Order size"
    )

    plt.ylabel(
        "Inventory skew"
    )

    plt.title(
        "One-Sided-Flow Mean P&L Robustness"
    )

    plt.colorbar(
        image,
        label="Mean terminal P&L",
    )

    save(
        "08_robustness_heatmap.png"
    )

    half_spreads = np.linspace(
        0.005,
        0.16,
        120,
    )

    intensity = np.array(
        [
            fill_intensity(
                value,
                90,
                18,
            )
            for value
            in half_spreads
        ]
    )

    revenue = np.array(
        [
            expected_spread_rate(
                value,
                90,
                18,
            )
            for value
            in half_spreads
        ]
    )

    plt.figure(
        figsize=(8, 5)
    )

    plt.plot(
        half_spreads,
        intensity,
        label="Per-side fill intensity",
    )

    plt.plot(
        half_spreads,
        revenue,
        label="Gross spread revenue rate",
    )

    plt.xlabel(
        "Half-spread"
    )

    plt.title(
        "Quote Width, Fill Intensity, and Gross Revenue"
    )

    plt.legend()

    save(
        "09_fixed_spread_tradeoff.png"
    )


def avellaneda_stoikov_figure(
    benchmark_summary: pd.DataFrame,
) -> None:
    """Plot the A-S benchmark separately from the canonical figures."""

    strategy_labels = {
        "fixed": "Fixed",
        "inventory": "Inventory",
        "inventory_volatility": "Inventory + Volatility",
        "full_adaptive": "Full Adaptive",
        "full_risk": "Full Risk",
        "avellaneda_stoikov": "Avellaneda-Stoikov",
    }

    scenario_labels = {
        "clean": "Clean",
        "high_volatility": "High volatility",
        "toxic": "Toxic flow",
        "one_sided": "One-sided flow",
        "regime_switching": "Regime switching",
        "stress": "Stress",
    }

    regular_strategies = [
        "fixed",
        "inventory",
        "full_adaptive",
        "avellaneda_stoikov",
    ]

    regular_scenarios = [
        "clean",
        "high_volatility",
        "toxic",
        "one_sided",
        "regime_switching",
    ]

    regular_table = (
        benchmark_summary[
            benchmark_summary.strategy.isin(
                regular_strategies
            )
        ]
        .pivot(
            index="scenario",
            columns="strategy",
            values="mean_terminal_pnl",
        )
        .reindex(
            index=regular_scenarios,
            columns=regular_strategies,
        )
    )

    x = np.arange(
        len(regular_scenarios)
    )

    width = 0.20

    plt.figure(
        figsize=(11, 6)
    )

    for index, strategy in enumerate(
        regular_strategies
    ):
        offset = (
            index
            - (
                len(
                    regular_strategies
                )
                - 1
            )
            / 2
        ) * width

        plt.bar(
            x + offset,
            regular_table[
                strategy
            ].to_numpy(),
            width,
            label=strategy_labels[
                strategy
            ],
        )

    plt.axhline(
        0,
        linewidth=1,
    )

    plt.xticks(
        x,
        [
            scenario_labels[
                scenario
            ]
            for scenario
            in regular_scenarios
        ],
        rotation=20,
        ha="right",
    )

    plt.ylabel(
        "Mean terminal P&L"
    )

    plt.title(
        "Avellaneda-Stoikov Benchmark on Paired Synthetic Paths"
    )

    plt.legend(
        fontsize=8
    )

    save(
        "11_avellaneda_stoikov_benchmark.png"
    )

    stress_strategies = [
        "fixed",
        "inventory",
        "inventory_volatility",
        "full_adaptive",
        "full_risk",
        "avellaneda_stoikov",
    ]

    stress_table = (
        benchmark_summary[
            (
                benchmark_summary.scenario
                == "stress"
            )
            & (
                benchmark_summary.strategy.isin(
                    stress_strategies
                )
            )
        ]
        .set_index(
            "strategy"
        )
        .reindex(
            stress_strategies
        )
    )

    x = np.arange(
        len(
            stress_strategies
        )
    )

    plt.figure(
        figsize=(11, 6)
    )

    plt.bar(
        x,
        stress_table[
            "mean_terminal_pnl"
        ].to_numpy(),
    )

    plt.axhline(
        0,
        linewidth=1,
    )

    plt.xticks(
        x,
        [
            strategy_labels[
                strategy
            ]
            for strategy
            in stress_strategies
        ],
        rotation=25,
        ha="right",
    )

    plt.ylabel(
        "Mean terminal P&L"
    )

    plt.title(
        "Strategy Comparison under the Stress Scenario"
    )

    save(
        "12_avellaneda_stoikov_stress.png"
    )


def validation_summary(
    chosen,
):
    rows = []

    for (
        scenario,
        strategy,
    ), result in chosen.items():
        validation = (
            validate_simulation_result(
                result,
                (
                    28
                    if strategy
                    == "full_risk"
                    else None
                ),
            )
        )

        rows.append(
            {
                "scenario": scenario,
                "strategy": strategy,
                **validation.to_dict(),
            }
        )

    pd.DataFrame(
        rows
    ).to_csv(
        TAB
        / "validation_summary.csv",
        index=False,
    )


def main():
    (
        results,
        summary,
        attribution,
    ) = core_experiments()

    (
        as_results,
        as_summary,
        benchmark_summary,
        paired_table,
    ) = avellaneda_stoikov_benchmark(
        results
    )

    robustness_experiments()

    chosen = (
        representative_outputs()
    )

    figures(
        results,
        summary,
        attribution,
        chosen,
    )

    avellaneda_stoikov_figure(
        benchmark_summary
    )

    validation_summary(
        chosen
    )

    print(
        f"Generated {len(results):,} "
        "canonical paired path-strategy records."
    )

    print(
        f"Generated {len(as_results):,} "
        "Avellaneda-Stoikov benchmark records."
    )

    print(
        "\nCanonical five-strategy summary:"
    )

    print(
        summary[
            [
                "scenario",
                "strategy",
                "mean_terminal_pnl",
                "pnl_5_percentile",
                "mean_markout_per_unit",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nAvellaneda-Stoikov summary:"
    )

    print(
        as_summary[
            [
                "scenario",
                "strategy",
                "mean_terminal_pnl",
                "pnl_5_percentile",
                "mean_absolute_inventory",
                "mean_maximum_inventory",
                "mean_markout_per_unit",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nA-S paired comparisons generated:"
        f" {len(paired_table)}"
    )


if __name__ == "__main__":
    main()