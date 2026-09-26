import math

import pytest

from market_maker_lab.aggressive_execution import (
    AggressiveExecutionConfig,
    execute_to_target_inventory,
)
from market_maker_lab.ledger import MarketMakerLedger
from market_maker_lab.market_primitives import Quote
from market_maker_lab.risk_controls import (
    MarketMakerRiskManager,
    RiskDecision,
    RiskLimits,
    RiskSnapshot,
    RiskState,
    apply_risk_overlay,
)


def manager(**kwargs):
    limits = RiskLimits(
        10,
        20,
        5,
        maximum_loss=kwargs.get("maximum_loss", 50),
        maximum_drawdown=kwargs.get("maximum_drawdown", 30),
        maximum_absolute_price_jump=kwargs.get("jump"),
        cooldown_steps=3,
    )
    risk_manager = MarketMakerRiskManager(limits)
    risk_manager.reset(0)
    return risk_manager


def snap(inventory=0, wealth=0, jump=None):
    return RiskSnapshot(
        0,
        0,
        100,
        inventory,
        0,
        wealth,
        wealth,
        None,
        jump,
    )


@pytest.mark.parametrize(
    "inventory,state",
    [
        (0, RiskState.NORMAL),
        (9, RiskState.NORMAL),
        (12, RiskState.REDUCE_ONLY),
        (22, RiskState.FORCED_REDUCTION),
        (-12, RiskState.REDUCE_ONLY),
        (-22, RiskState.FORCED_REDUCTION),
    ],
)
def test_position_states(inventory, state):
    assert manager().assess(snap(inventory)).state == state


def test_reduce_only_sides():
    long_decision = manager().assess(snap(12))
    short_decision = manager().assess(snap(-12))

    assert (
        not long_decision.allow_bid
        and long_decision.allow_ask
        and short_decision.allow_bid
        and not short_decision.allow_ask
    )


def test_loss_halt_persistent():
    risk_manager = manager()
    decision = risk_manager.assess(snap(0, -55))

    assert decision.state == RiskState.HALTED
    assert risk_manager.assess(snap()).state == RiskState.HALTED


def test_drawdown_halt_while_profitable():
    risk_manager = manager()
    risk_manager.assess(snap(0, 40))
    decision = risk_manager.assess(snap(0, 5))

    assert decision.state == RiskState.HALTED


def test_jump_cooldown():
    decision = manager(jump=0.5).assess(snap(jump=0.8))

    assert decision.state == RiskState.COOLDOWN


def test_overlay_caps_capacity():
    decision = RiskDecision(
        RiskState.NORMAL,
        (),
        True,
        True,
        None,
        False,
        0,
        0,
    )

    quote = apply_risk_overlay(
        Quote(99.95, 100.05, 5, 5),
        9,
        decision,
        10,
    )

    assert quote.bid_size == 1


@pytest.mark.parametrize(
    "target,side",
    [
        (5, "sell"),
        (-5, "buy"),
    ],
)
def test_forced_execution(target, side):
    ledger = MarketMakerLedger(
        0,
        20 if target > 0 else -20,
    )

    execution_config = AggressiveExecutionConfig(
        0.05,
        0.01,
        0.001,
    )

    execution_result = execute_to_target_inventory(
        ledger,
        target,
        100,
        0,
        execution_config,
    )

    assert execution_result.trade.side == side
    assert math.isclose(
        ledger.inventory,
        target,
    )

    executed_quantity = 15

    expected_cost = (
        executed_quantity * 0.05
        + 0.001 * executed_quantity * executed_quantity
        + executed_quantity * 0.01
    )

    assert math.isclose(
        execution_result.total_execution_cost,
        expected_cost,
    )
