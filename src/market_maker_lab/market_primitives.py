"""Core quote and trade objects."""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil, floor, isfinite
from typing import Literal

TradeSide = Literal["buy", "sell"]

@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    bid_size: float
    ask_size: float

    @property
    def mid(self) -> float:
        return 0.5 * (self.bid + self.ask)

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def half_spread(self) -> float:
        return 0.5 * self.spread

@dataclass(frozen=True)
class Trade:
    """Trade from the market maker's perspective."""
    time: float
    side: TradeSide
    price: float
    quantity: float
    fee: float = 0.0
    toxic_quantity: float = 0.0
    liquidity: Literal["maker", "taker"] = "maker"

    def __post_init__(self) -> None:
        values = (self.time, self.price, self.quantity, self.fee, self.toxic_quantity)
        if not all(isfinite(v) for v in values):
            raise ValueError("Trade values must be finite.")
        if self.time < 0 or self.price <= 0 or self.quantity <= 0 or self.fee < 0:
            raise ValueError("Invalid trade time, price, quantity, or fee.")
        if self.side not in {"buy", "sell"}:
            raise ValueError("Trade side must be 'buy' or 'sell'.")
        if self.toxic_quantity < 0 or self.toxic_quantity > self.quantity:
            raise ValueError("Toxic quantity must lie in [0, quantity].")

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == "buy" else -self.quantity

    @property
    def direction(self) -> float:
        return 1.0 if self.side == "buy" else -1.0

    @property
    def toxic_fraction(self) -> float:
        return self.toxic_quantity / self.quantity


def validate_quote(quote: Quote) -> None:
    values = (quote.bid, quote.ask, quote.bid_size, quote.ask_size)
    if not all(isfinite(v) for v in values):
        raise ValueError("Quote values must be finite.")
    if quote.bid <= 0 or quote.ask <= 0:
        raise ValueError("Bid and ask must be positive.")
    if quote.ask < quote.bid:
        raise ValueError("Crossed quote.")
    if quote.bid_size < 0 or quote.ask_size < 0:
        raise ValueError("Quote sizes cannot be negative.")


def round_bid_to_tick(price: float, tick_size: float) -> float:
    if price <= 0 or tick_size <= 0 or not isfinite(price) or not isfinite(tick_size):
        raise ValueError("Price and tick size must be finite and positive.")
    return floor((price + 1e-12) / tick_size) * tick_size


def round_ask_to_tick(price: float, tick_size: float) -> float:
    if price <= 0 or tick_size <= 0 or not isfinite(price) or not isfinite(tick_size):
        raise ValueError("Price and tick size must be finite and positive.")
    return ceil((price - 1e-12) / tick_size) * tick_size
