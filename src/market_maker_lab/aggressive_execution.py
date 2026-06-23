"""Forced inventory reduction and conservative liquidation valuation."""
from __future__ import annotations
from dataclasses import dataclass
from .ledger import MarketMakerLedger
from .market_primitives import Trade

@dataclass(frozen=True)
class AggressiveExecutionConfig:
    external_half_spread: float
    taker_fee_per_unit: float
    linear_impact_per_unit: float = 0.0

@dataclass(frozen=True)
class AggressiveExecutionResult:
    trade: Trade | None
    inventory_before: float
    inventory_after: float
    target_inventory: float
    traded_quantity: float
    spread_crossing_cost: float
    market_impact_cost: float
    taker_fee: float
    total_execution_cost: float


def conservative_liquidation_wealth(cash: float, inventory: float, mid_price: float, config: AggressiveExecutionConfig) -> float:
    q = abs(inventory)
    cost = q * config.external_half_spread + config.linear_impact_per_unit * q**2 + config.taker_fee_per_unit * q
    return cash + inventory * mid_price - cost


def execute_to_target_inventory(
    ledger: MarketMakerLedger, target_inventory: float, mid_price: float, time: float,
    config: AggressiveExecutionConfig,
) -> AggressiveExecutionResult:
    before = ledger.inventory
    signed = target_inventory - before
    q = abs(signed)
    if q == 0:
        return AggressiveExecutionResult(None, before, before, target_inventory, 0, 0, 0, 0, 0)
    impact = config.linear_impact_per_unit * q
    if signed > 0:
        side, price = "buy", mid_price + config.external_half_spread + impact
    else:
        side, price = "sell", mid_price - config.external_half_spread - impact
    fee = config.taker_fee_per_unit * q
    trade = Trade(time, side, price, q, fee, liquidity="taker")
    ledger.apply_trade(trade)
    spread_cost = q * config.external_half_spread
    impact_cost = config.linear_impact_per_unit * q**2
    total = spread_cost + impact_cost + fee
    return AggressiveExecutionResult(trade, before, ledger.inventory, target_inventory, q, spread_cost, impact_cost, fee, total)
