"""Observable side-specific adverse-selection estimator."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections.abc import Sequence
from .market_primitives import Trade

@dataclass
class EWMAAdverseSelectionEstimator:
    decay: float
    initial_bid_loss: float = 0.0
    initial_ask_loss: float = 0.0
    maximum_loss: float | None = None
    _bid_loss: float = field(init=False, repr=False)
    _ask_loss: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.decay < 1:
            raise ValueError("Decay must lie in [0, 1).")
        self.reset()

    def reset(self) -> None:
        self._bid_loss = self.initial_bid_loss
        self._ask_loss = self.initial_ask_loss

    @property
    def bid_loss(self) -> float: return self._bid_loss
    @property
    def ask_loss(self) -> float: return self._ask_loss

    def _bound(self, x: float) -> float:
        x = max(x, 0.0)
        return min(x, self.maximum_loss) if self.maximum_loss is not None else x

    def update(self, trades: Sequence[Trade], mid_price_start: float, mid_price_end: float) -> None:
        move = mid_price_end - mid_price_start
        if any(t.side == "buy" for t in trades):
            observed = self._bound(-move)
            self._bid_loss = self.decay * self._bid_loss + (1 - self.decay) * observed
        if any(t.side == "sell" for t in trades):
            observed = self._bound(move)
            self._ask_loss = self.decay * self._ask_loss + (1 - self.decay) * observed
