"""Online volatility estimators."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import isfinite, sqrt

@dataclass
class ConstantVolatilityEstimator:
    volatility: float
    def __post_init__(self) -> None:
        if not isfinite(self.volatility) or self.volatility < 0:
            raise ValueError("Volatility must be finite and non-negative.")
    def reset(self) -> None: pass
    def update(self, mid_price: float, time: float) -> float:
        return self.volatility
    @property
    def current_volatility(self) -> float:
        return self.volatility

@dataclass
class EWMAAbsoluteVolatilityEstimator:
    decay: float
    initial_volatility: float
    minimum_volatility: float = 0.0
    maximum_volatility: float | None = None
    _variance: float = field(init=False, repr=False)
    _last_price: float | None = field(init=False, default=None, repr=False)
    _last_time: float | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.decay < 1:
            raise ValueError("Decay must lie in [0, 1).")
        if self.initial_volatility < 0 or self.minimum_volatility < 0:
            raise ValueError("Volatilities cannot be negative.")
        if self.maximum_volatility is not None and self.maximum_volatility < self.minimum_volatility:
            raise ValueError("Maximum volatility is below minimum.")
        self.reset()

    def reset(self) -> None:
        initial = max(self.initial_volatility, self.minimum_volatility)
        if self.maximum_volatility is not None:
            initial = min(initial, self.maximum_volatility)
        self._variance = initial**2
        self._last_price = None
        self._last_time = None

    @property
    def current_volatility(self) -> float:
        return sqrt(max(self._variance, 0.0))

    def update(self, mid_price: float, time: float) -> float:
        if mid_price <= 0 or time < 0:
            raise ValueError("Invalid price or time.")
        if self._last_price is None:
            self._last_price, self._last_time = mid_price, time
            return self.current_volatility
        dt = time - float(self._last_time)
        if dt <= 0:
            raise ValueError("Observation times must increase.")
        inst_var = (mid_price - self._last_price)**2 / dt
        vol = sqrt(max(self.decay * self._variance + (1 - self.decay) * inst_var, 0.0))
        vol = max(vol, self.minimum_volatility)
        if self.maximum_volatility is not None:
            vol = min(vol, self.maximum_volatility)
        self._variance = vol**2
        self._last_price, self._last_time = mid_price, time
        return vol
