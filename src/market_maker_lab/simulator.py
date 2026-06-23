"""Discrete-clock event-driven market-making simulator."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
import numpy as np
import pandas as pd
from .ledger import MarketMakerLedger
from .market_primitives import Quote, Trade
from .markouts import immediate_spread_capture, post_trade_price_component, trade_markout
from .risk_controls import MarketMakerRiskManager, RiskSnapshot, RiskDecision, RiskState, apply_risk_overlay
from .aggressive_execution import AggressiveExecutionConfig, execute_to_target_inventory, conservative_liquidation_wealth

@dataclass(frozen=True)
class SimulationConfig:
    initial_mid_price: float = 100.0
    time_horizon: float = 1.0
    number_of_steps: int = 400
    initial_cash: float = 0.0
    initial_inventory: float = 0.0
    liquidate_at_end: bool = True
    seed: int = 42

@dataclass(frozen=True)
class SimulationResult:
    intervals: pd.DataFrame
    trades: pd.DataFrame
    events: pd.DataFrame
    risk_events: pd.DataFrame
    initial_wealth: float
    terminal_pnl: float
    final_cash: float
    final_inventory: float
    final_marked_wealth: float
    total_spread_capture: float
    total_price_move_pnl: float
    total_maker_fees: float
    total_forced_execution_pnl: float
    total_forced_execution_cost: float
    total_forced_trade_quantity: float
    forced_reduction_count: int
    terminal_liquidation_pnl: float
    permanently_halted: bool
    halt_reason: str | None


def _diagnostics(strategy: object) -> dict[str, float]:
    fn = getattr(strategy, "diagnostics", None)
    return {str(k): float(v) for k, v in fn().items()} if callable(fn) else {}


def _reset(component: object | None) -> None:
    fn = getattr(component, "reset", None)
    if callable(fn): fn()


def _zero_quote(mid: float) -> Quote:
    return Quote(mid, mid, 0.0, 0.0)


def run_market_making_simulation(
    config: SimulationConfig,
    strategy: object,
    coupled_market_model: object | None = None,
    price_process: object | None = None,
    fill_model: object | None = None,
    risk_manager: MarketMakerRiskManager | None = None,
    aggressive_execution_config: AggressiveExecutionConfig | None = None,
) -> SimulationResult:
    if config.initial_mid_price <= 0 or config.time_horizon <= 0 or config.number_of_steps <= 0:
        raise ValueError("Invalid simulation configuration.")
    coupled = coupled_market_model is not None and price_process is None and fill_model is None
    independent = coupled_market_model is None and price_process is not None and fill_model is not None
    if not (coupled or independent):
        raise ValueError("Use either a coupled market model or both independent price and fill models.")
    if risk_manager is not None and aggressive_execution_config is None:
        raise ValueError("Risk manager requires aggressive execution configuration.")

    _reset(strategy); _reset(coupled_market_model); _reset(price_process); _reset(fill_model)
    seeds = np.random.SeedSequence(config.seed).spawn(2)
    market_rng = np.random.default_rng(seeds[0])
    fill_rng = np.random.default_rng(seeds[1])
    times = np.linspace(0.0, config.time_horizon, config.number_of_steps + 1)
    ledger = MarketMakerLedger(config.initial_cash, config.initial_inventory)
    mid = config.initial_mid_price
    initial_wealth = ledger.marked_wealth(mid)
    if risk_manager is not None:
        assert aggressive_execution_config is not None
        risk_manager.reset(conservative_liquidation_wealth(ledger.cash, ledger.inventory, mid, aggressive_execution_config))

    interval_records: list[dict] = []
    trade_records: list[dict] = []
    event_records: list[dict] = []
    risk_records: list[dict] = []
    total_spread = total_price_pnl = total_maker_fees = 0.0
    total_forced_pnl = total_forced_cost = total_forced_qty = 0.0
    forced_count = 0
    last_price_change: float | None = None

    for step in range(config.number_of_steps):
        t0, t1 = float(times[step]), float(times[step+1])
        dt = t1 - t0
        inventory_start, cash_start = ledger.inventory, ledger.cash
        wealth_start = ledger.marked_wealth(mid)

        observe = getattr(strategy, "observe_market", None)
        if callable(observe): observe(mid, t0)
        raw_quote = strategy.generate_quote(mid, ledger.inventory, t0)
        diag = _diagnostics(strategy)

        if risk_manager is not None:
            assert aggressive_execution_config is not None
            snapshot = RiskSnapshot(
                step, t0, mid, ledger.inventory, ledger.cash, ledger.marked_wealth(mid),
                conservative_liquidation_wealth(ledger.cash, ledger.inventory, mid, aggressive_execution_config),
                diag.get("estimated_volatility"), last_price_change,
            )
            decision = risk_manager.assess(snapshot)
        else:
            decision = RiskDecision(RiskState.NORMAL, (), True, True, None, False, 0.0, 0.0)

        wealth_before_risk = ledger.marked_wealth(mid)
        forced_result = None
        if decision.force_target_inventory is not None:
            assert aggressive_execution_config is not None
            forced_result = execute_to_target_inventory(
                ledger, decision.force_target_inventory, mid, t0, aggressive_execution_config
            )
            if forced_result.traded_quantity > 0:
                forced_count += 1
                total_forced_qty += forced_result.traded_quantity
                total_forced_cost += forced_result.total_execution_cost
                event_records.append({"event_type": "forced_execution", "step": step, "time": t0,
                                      "mid_price": mid, "side": forced_result.trade.side if forced_result.trade else None,
                                      "price": forced_result.trade.price if forced_result.trade else None,
                                      "quantity": forced_result.traded_quantity, "inventory": ledger.inventory, "cash": ledger.cash})
        forced_pnl = ledger.marked_wealth(mid) - wealth_before_risk
        total_forced_pnl += forced_pnl
        inventory_after_risk, cash_after_risk = ledger.inventory, ledger.cash
        quote = apply_risk_overlay(raw_quote, ledger.inventory, decision,
                                   risk_manager.limits.hard_position_limit if risk_manager else strategy.inventory_limit)
        event_records.append({"event_type": "quote", "step": step, "time": t0, "mid_price": mid,
                              "bid": quote.bid, "ask": quote.ask, "bid_size": quote.bid_size, "ask_size": quote.ask_size,
                              "inventory": ledger.inventory, "cash": ledger.cash, "risk_state": decision.state.value})

        if coupled:
            outcome = coupled_market_model.sample_interval(quote, mid, t0, dt, market_rng, fill_rng)
            trades = list(outcome.trades)
            next_mid = outcome.next_mid_price
            latent_signal = outcome.latent_signal
            drift_move, info_move, noise_move, jump_move = outcome.drift_move, outcome.information_move, outcome.noise_move, outcome.jump_move
            process_vol = outcome.process_volatility
            bid_intensity, ask_intensity = outcome.bid_intensity, outcome.ask_intensity
            toxic_bid, toxic_ask = outcome.toxic_bid_quantity, outcome.toxic_ask_quantity
        else:
            trades = fill_model.sample_trades(quote, mid, t0, dt, fill_rng)
            next_mid = price_process.next_price(mid, dt, market_rng)
            latent_signal = drift_move = info_move = noise_move = jump_move = np.nan
            process_vol = float(getattr(price_process, "current_volatility", np.nan))
            bid_intensity = ask_intensity = np.nan
            toxic_bid = toxic_ask = 0.0

        spread_capture = maker_fees = bid_fill = ask_fill = 0.0
        pending: list[tuple[dict, Trade]] = []
        for trade in trades:
            spread = immediate_spread_capture(trade, mid)
            spread_capture += spread
            maker_fees += trade.fee
            if trade.side == "buy": bid_fill += trade.quantity
            else: ask_fill += trade.quantity
            ledger.apply_trade(trade)
            pending.append(({
                "step": step, "time": t0, "side": trade.side, "price": trade.price, "quantity": trade.quantity,
                "fee": trade.fee, "liquidity": trade.liquidity, "quote_mid": mid, "quote_bid": quote.bid,
                "quote_ask": quote.ask, "immediate_spread_capture": spread, "toxic_quantity": trade.toxic_quantity,
                "toxic_fraction": trade.toxic_fraction, "is_toxic": trade.toxic_quantity > 0,
                "inventory_after_trade": ledger.inventory, "cash_after_trade": ledger.cash,
            }, trade))
            event_records.append({"event_type": "fill", "step": step, "time": t0, "mid_price": mid,
                                  "side": trade.side, "price": trade.price, "quantity": trade.quantity,
                                  "inventory": ledger.inventory, "cash": ledger.cash})

        net_inventory_change = bid_fill - ask_fill
        inventory_after_fills, cash_after_fills = ledger.inventory, ledger.cash
        price_change = next_mid - mid
        price_pnl = inventory_after_fills * price_change
        new_fill_price_pnl = net_inventory_change * price_change
        carried_price_pnl = inventory_after_risk * price_change
        wealth_end = ledger.marked_wealth(next_mid)
        exact_interval_pnl = wealth_end - wealth_start
        attributed_interval_pnl = forced_pnl + spread_capture - maker_fees + price_pnl
        reconciliation_error = exact_interval_pnl - attributed_interval_pnl

        for record, trade in pending:
            record["next_mid_price"] = next_mid
            record["post_trade_price_component"] = post_trade_price_component(trade, mid, next_mid)
            record["one_step_markout"] = trade_markout(trade, next_mid)
            trade_records.append(record)

        observe_interval = getattr(strategy, "observe_interval", None)
        if callable(observe_interval): observe_interval(mid, next_mid, trades)

        info_pnl = inventory_after_fills * info_move if np.isfinite(info_move) else np.nan
        noise_pnl = inventory_after_fills * noise_move if np.isfinite(noise_move) else np.nan
        drift_pnl = inventory_after_fills * drift_move if np.isfinite(drift_move) else np.nan
        jump_pnl = inventory_after_fills * jump_move if np.isfinite(jump_move) else np.nan
        record = {
            "step": step, "time_start": t0, "time_end": t1, "mid_start": mid, "mid_end": next_mid,
            "price_change": price_change, "process_volatility": process_vol, "latent_signal": latent_signal,
            "drift_price_move": drift_move, "information_price_move": info_move, "noise_price_move": noise_move,
            "jump_price_move": jump_move, "quote_bid": quote.bid, "quote_ask": quote.ask,
            "bid_size": quote.bid_size, "ask_size": quote.ask_size,
            "bid_distance": mid - quote.bid, "ask_distance": quote.ask - mid,
            "quote_center_shift": 0.5*(quote.bid+quote.ask)-mid,
            "effective_half_spread": 0.5*(quote.ask-quote.bid),
            "bid_intensity": bid_intensity, "ask_intensity": ask_intensity,
            "bid_fill_quantity": bid_fill, "ask_fill_quantity": ask_fill,
            "net_inventory_change": net_inventory_change,
            "toxic_bid_quantity": toxic_bid, "toxic_ask_quantity": toxic_ask,
            "total_toxic_quantity": toxic_bid + toxic_ask,
            "inventory_start": inventory_start, "inventory_after_risk_action": inventory_after_risk,
            "inventory_after_fills": inventory_after_fills, "cash_start": cash_start,
            "cash_after_risk_action": cash_after_risk, "cash_after_fills": cash_after_fills,
            "wealth_start": wealth_start, "wealth_end": wealth_end,
            "forced_execution_pnl": forced_pnl,
            "forced_execution_cost": forced_result.total_execution_cost if forced_result else 0.0,
            "forced_trade_quantity": forced_result.traded_quantity if forced_result else 0.0,
            "spread_capture": spread_capture, "maker_fees": maker_fees,
            "price_move_pnl": price_pnl, "new_fill_price_pnl": new_fill_price_pnl,
            "carried_inventory_price_pnl": carried_price_pnl,
            "passive_markout_pnl": spread_capture + new_fill_price_pnl,
            "drift_price_pnl": drift_pnl, "information_price_pnl": info_pnl,
            "noise_price_pnl": noise_pnl, "jump_price_pnl": jump_pnl,
            "new_fill_information_pnl": net_inventory_change * info_move if np.isfinite(info_move) else np.nan,
            "carried_information_pnl": inventory_after_risk * info_move if np.isfinite(info_move) else np.nan,
            "exact_interval_pnl": exact_interval_pnl, "attributed_interval_pnl": attributed_interval_pnl,
            "reconciliation_error": reconciliation_error,
            "risk_state": decision.state.value, "risk_reason_codes": "|".join(decision.reason_codes),
            "risk_liquidation_pnl": decision.liquidation_pnl, "risk_drawdown": decision.drawdown,
            **diag,
        }
        interval_records.append(record)
        if decision.state != RiskState.NORMAL:
            risk_records.append({"step": step, "time": t0, "state": decision.state.value,
                                 "reason_codes": "|".join(decision.reason_codes), "inventory_before": inventory_start,
                                 "inventory_after_risk_action": inventory_after_risk,
                                 "forced_trade_quantity": record["forced_trade_quantity"],
                                 "forced_execution_cost": record["forced_execution_cost"],
                                 "liquidation_pnl": decision.liquidation_pnl, "drawdown": decision.drawdown})
        event_records.append({"event_type": "price_update", "step": step, "time": t1, "mid_price": next_mid,
                              "inventory": ledger.inventory, "cash": ledger.cash})
        total_spread += spread_capture
        total_price_pnl += price_pnl
        total_maker_fees += maker_fees
        last_price_change = price_change
        mid = next_mid

    terminal_liquidation_pnl = 0.0
    if config.liquidate_at_end and ledger.inventory != 0:
        if aggressive_execution_config is None:
            aggressive_execution_config = AggressiveExecutionConfig(0.05, 0.0, 0.0)
        before = ledger.marked_wealth(mid)
        terminal = execute_to_target_inventory(ledger, 0.0, mid, config.time_horizon, aggressive_execution_config)
        terminal_liquidation_pnl = ledger.marked_wealth(mid) - before
        event_records.append({"event_type": "terminal_liquidation", "step": config.number_of_steps,
                              "time": config.time_horizon, "mid_price": mid,
                              "side": terminal.trade.side if terminal.trade else None,
                              "price": terminal.trade.price if terminal.trade else None,
                              "quantity": terminal.traded_quantity, "inventory": ledger.inventory, "cash": ledger.cash})

    final_marked = ledger.marked_wealth(mid)
    terminal_pnl = final_marked - initial_wealth
    return SimulationResult(
        pd.DataFrame(interval_records), pd.DataFrame(trade_records), pd.DataFrame(event_records), pd.DataFrame(risk_records),
        initial_wealth, terminal_pnl, ledger.cash, ledger.inventory, final_marked,
        total_spread, total_price_pnl, total_maker_fees, total_forced_pnl, total_forced_cost,
        total_forced_qty, forced_count, terminal_liquidation_pnl,
        risk_manager.permanently_halted if risk_manager else False,
        risk_manager.halt_reason if risk_manager else None,
    )
