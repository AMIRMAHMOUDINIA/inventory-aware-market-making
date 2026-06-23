"""Cash and inventory accounting."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from .market_primitives import Trade

@dataclass
class MarketMakerLedger:
    cash: float = 0.0
    inventory: float = 0.0
    cumulative_fees: float = 0.0
    traded_volume: float = 0.0

    def apply_trade(self, trade: Trade) -> None:
        self.inventory += trade.signed_quantity
        self.cash -= trade.price * trade.signed_quantity
        self.cash -= trade.fee
        self.cumulative_fees += trade.fee
        self.traded_volume += trade.quantity

    def marked_wealth(self, mid_price: float) -> float:
        if not isfinite(mid_price) or mid_price <= 0:
            raise ValueError("Mid-price must be finite and positive.")
        return self.cash + self.inventory * mid_price
