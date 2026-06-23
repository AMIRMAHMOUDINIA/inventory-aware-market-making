"""Trade-level spread and markout calculations."""
from __future__ import annotations
from .market_primitives import Trade

def immediate_spread_capture(trade: Trade, current_mid_price: float) -> float:
    return trade.quantity * trade.direction * (current_mid_price - trade.price)

def post_trade_price_component(trade: Trade, current_mid_price: float, later_mid_price: float) -> float:
    return trade.quantity * trade.direction * (later_mid_price - current_mid_price)

def trade_markout(trade: Trade, later_mid_price: float) -> float:
    return trade.quantity * trade.direction * (later_mid_price - trade.price)
