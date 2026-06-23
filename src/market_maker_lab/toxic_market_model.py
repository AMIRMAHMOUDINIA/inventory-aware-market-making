"""Coupled price, order-flow, volatility-regime, and toxicity model."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import exp, floor, sqrt
import numpy as np
from .market_primitives import Quote, Trade

@dataclass(frozen=True)
class MarketOutcome:
    trades: tuple[Trade, ...]
    next_mid_price: float
    latent_signal: float
    drift_move: float
    information_move: float
    noise_move: float
    jump_move: float
    process_volatility: float
    bid_intensity: float
    ask_intensity: float
    toxic_bid_quantity: float
    toxic_ask_quantity: float

@dataclass
class RegimeToxicMarketModel:
    drift_schedule: tuple[float, ...]
    volatility_schedule: tuple[float, ...]
    information_flow_schedule: tuple[float, ...]
    information_correlation_schedule: tuple[float, ...]
    bid_multiplier_schedule: tuple[float, ...]
    ask_multiplier_schedule: tuple[float, ...]
    jump_schedule: tuple[float, ...]
    baseline_intensity: float
    distance_sensitivity: float
    lot_size: float = 1.0
    maker_fee_per_unit: float = 0.0
    signal_cap: float = 3.0
    minimum_price: float = 0.01
    _step: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        lengths = {len(self.drift_schedule), len(self.volatility_schedule), len(self.information_flow_schedule),
                   len(self.information_correlation_schedule), len(self.bid_multiplier_schedule),
                   len(self.ask_multiplier_schedule), len(self.jump_schedule)}
        if len(lengths) != 1 or 0 in lengths:
            raise ValueError("All schedules must have the same positive length.")
        if self.baseline_intensity < 0 or self.distance_sensitivity < 0 or self.lot_size <= 0:
            raise ValueError("Invalid market-model parameters.")
        if any(not 0 <= x <= 1 for x in self.information_correlation_schedule):
            raise ValueError("Information correlations must lie in [0,1].")

    def reset(self) -> None:
        self._step = 0

    @property
    def current_volatility(self) -> float:
        return float(self.volatility_schedule[min(self._step, len(self.volatility_schedule)-1)])

    def sample_interval(
        self, quote: Quote, current_mid_price: float, time: float, dt: float,
        market_rng: np.random.Generator, fill_rng: np.random.Generator,
    ) -> MarketOutcome:
        i = min(self._step, len(self.volatility_schedule)-1)
        drift = self.drift_schedule[i]
        vol = self.volatility_schedule[i]
        beta = self.information_flow_schedule[i]
        rho = self.information_correlation_schedule[i]
        bid_mult = self.bid_multiplier_schedule[i]
        ask_mult = self.ask_multiplier_schedule[i]
        jump = self.jump_schedule[i]
        signal = float(np.clip(market_rng.standard_normal(), -self.signal_cap, self.signal_cap))
        noise = float(market_rng.standard_normal())
        bid_distance = max(current_mid_price - quote.bid, 0.0)
        ask_distance = max(quote.ask - current_mid_price, 0.0)
        bid_intensity = self.baseline_intensity * bid_mult * exp(-self.distance_sensitivity * bid_distance - beta * signal)
        ask_intensity = self.baseline_intensity * ask_mult * exp(-self.distance_sensitivity * ask_distance + beta * signal)

        def lots(intensity: float, displayed: float) -> int:
            return min(int(fill_rng.poisson(intensity * dt)), floor(displayed / self.lot_size + 1e-12))
        bid_qty = lots(bid_intensity, quote.bid_size) * self.lot_size
        ask_qty = lots(ask_intensity, quote.ask_size) * self.lot_size
        toxic_bid = bid_qty if signal < 0 and rho > 0 and beta > 0 else 0.0
        toxic_ask = ask_qty if signal > 0 and rho > 0 and beta > 0 else 0.0
        trades: list[Trade] = []
        if bid_qty > 0:
            trades.append(Trade(time, "buy", quote.bid, bid_qty, self.maker_fee_per_unit * bid_qty, toxic_bid))
        if ask_qty > 0:
            trades.append(Trade(time, "sell", quote.ask, ask_qty, self.maker_fee_per_unit * ask_qty, toxic_ask))
        drift_move = drift * dt
        information_move = vol * sqrt(dt) * rho * signal
        noise_move = vol * sqrt(dt) * sqrt(max(1-rho**2, 0.0)) * noise
        next_price = max(current_mid_price + drift_move + information_move + noise_move + jump, self.minimum_price)
        self._step += 1
        return MarketOutcome(tuple(trades), float(next_price), signal, float(drift_move), float(information_move),
                             float(noise_move), float(jump), float(vol), float(bid_intensity), float(ask_intensity),
                             float(toxic_bid), float(toxic_ask))
