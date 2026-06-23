"""Independent stateful risk-management overlay."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .market_primitives import Quote

class RiskState(str, Enum):
    NORMAL = "normal"
    REDUCE_ONLY = "reduce_only"
    COOLDOWN = "cooldown"
    FORCED_REDUCTION = "forced_reduction"
    HALTED = "halted"

@dataclass(frozen=True)
class RiskLimits:
    soft_position_limit: float
    hard_position_limit: float
    recovery_position_limit: float
    maximum_inventory_notional: float | None = None
    maximum_loss: float | None = None
    maximum_drawdown: float | None = None
    minimum_cash: float | None = None
    maximum_estimated_volatility: float | None = None
    maximum_absolute_price_jump: float | None = None
    cooldown_steps: int = 0
    liquidate_on_halt: bool = True

@dataclass(frozen=True)
class RiskSnapshot:
    step: int
    time: float
    mid_price: float
    inventory: float
    cash: float
    marked_wealth: float
    liquidation_wealth: float
    estimated_volatility: float | None
    last_price_change: float | None

@dataclass(frozen=True)
class RiskDecision:
    state: RiskState
    reason_codes: tuple[str, ...]
    allow_bid: bool
    allow_ask: bool
    force_target_inventory: float | None
    permanent_halt: bool
    liquidation_pnl: float
    drawdown: float

class MarketMakerRiskManager:
    def __init__(self, limits: RiskLimits) -> None:
        if not 0 <= limits.recovery_position_limit < limits.soft_position_limit < limits.hard_position_limit:
            raise ValueError("Require recovery < soft < hard position limits.")
        self.limits = limits
        self.reset(0.0)

    def reset(self, initial_liquidation_wealth: float) -> None:
        self.initial = initial_liquidation_wealth
        self.peak = initial_liquidation_wealth
        self.cooldown_remaining = 0
        self.permanently_halted = False
        self.halt_reason: str | None = None

    def manual_halt(self, reason: str = "manual_kill_switch") -> None:
        self.permanently_halted = True
        self.halt_reason = reason

    def assess(self, s: RiskSnapshot) -> RiskDecision:
        self.peak = max(self.peak, s.liquidation_wealth)
        pnl = s.liquidation_wealth - self.initial
        drawdown = self.peak - s.liquidation_wealth
        if self.permanently_halted:
            target = 0.0 if self.limits.liquidate_on_halt and s.inventory != 0 else None
            return RiskDecision(RiskState.HALTED, (self.halt_reason or "previous_halt",), False, False, target, True, pnl, drawdown)
        reasons: list[str] = []
        if self.limits.maximum_loss is not None and pnl <= -self.limits.maximum_loss: reasons.append("maximum_loss")
        if self.limits.maximum_drawdown is not None and drawdown >= self.limits.maximum_drawdown: reasons.append("maximum_drawdown")
        if self.limits.minimum_cash is not None and s.cash <= self.limits.minimum_cash: reasons.append("minimum_cash")
        if reasons:
            self.permanently_halted, self.halt_reason = True, "+".join(reasons)
            target = 0.0 if self.limits.liquidate_on_halt and s.inventory != 0 else None
            return RiskDecision(RiskState.HALTED, tuple(reasons), False, False, target, True, pnl, drawdown)

        hard = abs(s.inventory) >= self.limits.hard_position_limit
        notional = self.limits.maximum_inventory_notional is not None and abs(s.inventory) * s.mid_price >= self.limits.maximum_inventory_notional
        if hard or notional:
            target = self.limits.recovery_position_limit if s.inventory > 0 else -self.limits.recovery_position_limit if s.inventory < 0 else 0.0
            rs = tuple(x for x, flag in (("hard_position_limit", hard), ("inventory_notional_limit", notional)) if flag)
            return RiskDecision(RiskState.FORCED_REDUCTION, rs, False, False, target, False, pnl, drawdown)

        trigger: list[str] = []
        if self.limits.maximum_estimated_volatility is not None and s.estimated_volatility is not None and s.estimated_volatility >= self.limits.maximum_estimated_volatility:
            trigger.append("volatility_limit")
        if self.limits.maximum_absolute_price_jump is not None and s.last_price_change is not None and abs(s.last_price_change) >= self.limits.maximum_absolute_price_jump:
            trigger.append("price_jump")
        if trigger:
            self.cooldown_remaining = max(self.cooldown_remaining, self.limits.cooldown_steps)
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return RiskDecision(RiskState.COOLDOWN, tuple(trigger or ["existing_cooldown"]), False, False, None, False, pnl, drawdown)

        if abs(s.inventory) >= self.limits.soft_position_limit:
            return RiskDecision(RiskState.REDUCE_ONLY, ("soft_position_limit",), s.inventory < 0, s.inventory > 0, None, False, pnl, drawdown)
        return RiskDecision(RiskState.NORMAL, (), True, True, None, False, pnl, drawdown)


def apply_risk_overlay(quote: Quote, inventory: float, decision: RiskDecision, hard_position_limit: float) -> Quote:
    bid_size = min(quote.bid_size, max(hard_position_limit - inventory, 0.0)) if decision.allow_bid else 0.0
    ask_size = min(quote.ask_size, max(hard_position_limit + inventory, 0.0)) if decision.allow_ask else 0.0
    return Quote(quote.bid, quote.ask, float(bid_size), float(ask_size))
