"""Independent passive fill and price models used for controls."""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, sqrt
import numpy as np
from .market_primitives import Quote, Trade

@dataclass(frozen=True)
class ArithmeticBrownianProcess:
    drift: float
    volatility: float
    minimum_price: float = 0.01
    @property
    def current_volatility(self) -> float: return self.volatility
    def reset(self) -> None: pass
    def next_price(self, current_price: float, dt: float, rng: np.random.Generator) -> float:
        return float(max(current_price + self.drift * dt + self.volatility * sqrt(dt) * rng.standard_normal(), self.minimum_price))

@dataclass(frozen=True)
class PoissonFillModel:
    baseline_intensity: float
    distance_sensitivity: float
    lot_size: float = 1.0
    maker_fee_per_unit: float = 0.0

    def reset(self) -> None: pass

    def sample_trades(self, quote: Quote, mid_price: float, time: float, dt: float, rng: np.random.Generator) -> list[Trade]:
        trades: list[Trade] = []
        for side, distance, price, displayed in (
            ("buy", max(mid_price - quote.bid, 0.0), quote.bid, quote.bid_size),
            ("sell", max(quote.ask - mid_price, 0.0), quote.ask, quote.ask_size),
        ):
            intensity = self.baseline_intensity * exp(-self.distance_sensitivity * distance)
            lots = min(int(rng.poisson(intensity * dt)), int(displayed // self.lot_size + 1e-12))
            quantity = lots * self.lot_size
            if quantity > 0:
                trades.append(Trade(time, side, price, quantity, self.maker_fee_per_unit * quantity))
        return trades
