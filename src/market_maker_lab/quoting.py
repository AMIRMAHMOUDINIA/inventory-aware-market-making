"""Quote construction rules."""
from __future__ import annotations
from math import sqrt
import numpy as np
from .market_primitives import Quote, round_ask_to_tick, round_bid_to_tick, validate_quote


def volatility_adjusted_half_spread(
    base_half_spread: float,
    estimated_volatility: float,
    volatility_sensitivity: float,
    quote_horizon: float,
    minimum_half_spread: float,
    maximum_half_spread: float,
) -> float:
    if base_half_spread <= 0 or estimated_volatility < 0 or volatility_sensitivity < 0 or quote_horizon <= 0:
        raise ValueError("Invalid spread parameters.")
    if minimum_half_spread <= 0 or maximum_half_spread < minimum_half_spread:
        raise ValueError("Invalid spread bounds.")
    raw = base_half_spread + volatility_sensitivity * estimated_volatility * sqrt(quote_horizon)
    return float(np.clip(raw, minimum_half_spread, maximum_half_spread))


def construct_quote(
    mid_price: float,
    inventory: float,
    half_spread: float,
    inventory_skew: float,
    minimum_quote_distance: float,
    maximum_quote_distance: float,
    order_size: float,
    tick_size: float,
    inventory_limit: float,
    bid_adverse_loss: float = 0.0,
    ask_adverse_loss: float = 0.0,
    toxicity_sensitivity: float = 0.0,
) -> Quote:
    if mid_price <= 0 or half_spread <= 0 or inventory_skew < 0 or toxicity_sensitivity < 0:
        raise ValueError("Invalid quote inputs.")
    if minimum_quote_distance <= 0 or maximum_quote_distance < minimum_quote_distance:
        raise ValueError("Invalid quote-distance bounds.")
    if order_size <= 0 or tick_size <= 0 or inventory_limit <= 0:
        raise ValueError("Invalid size, tick, or limit.")
    if abs(inventory) > inventory_limit + 1e-12:
        raise ValueError("Inventory exceeds configured limit.")

    # Positive inventory shifts both quotes down: bid farther, ask closer.
    max_skew = max(half_spread - minimum_quote_distance, 0.0)
    skew = float(np.clip(inventory_skew * inventory, -max_skew, max_skew))
    bid_distance = float(np.clip(
        half_spread + skew + toxicity_sensitivity * max(bid_adverse_loss, 0.0),
        minimum_quote_distance,
        maximum_quote_distance,
    ))
    ask_distance = float(np.clip(
        half_spread - skew + toxicity_sensitivity * max(ask_adverse_loss, 0.0),
        minimum_quote_distance,
        maximum_quote_distance,
    ))
    bid = round_bid_to_tick(mid_price - bid_distance, tick_size)
    ask = round_ask_to_tick(mid_price + ask_distance, tick_size)
    bid_size = max(0.0, min(order_size, inventory_limit - inventory))
    ask_size = max(0.0, min(order_size, inventory_limit + inventory))
    quote = Quote(bid=bid, ask=ask, bid_size=float(bid_size), ask_size=float(ask_size))
    validate_quote(quote)
    return quote
