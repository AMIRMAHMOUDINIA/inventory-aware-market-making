"""Reproducible market scenario factories."""
from __future__ import annotations
from dataclasses import dataclass
from .toxic_market_model import RegimeToxicMarketModel

@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    volatility: float
    information_flow: float
    information_correlation: float
    bid_multiplier: float = 1.0
    ask_multiplier: float = 1.0
    jump_fraction: float = 0.0
    regime: bool = False

SCENARIOS = {
    "clean": Scenario("clean", "Symmetric non-toxic flow with moderate volatility.", 0.8, 0.0, 0.0),
    "high_volatility": Scenario("high_volatility", "Symmetric clean flow with high price volatility.", 2.4, 0.0, 0.0),
    "toxic": Scenario("toxic", "Signal-dependent flow followed by adverse price movement.", 1.5, 0.9, 0.7),
    "one_sided": Scenario("one_sided", "Persistent sell pressure hitting the market maker's bid.", 1.0, 0.0, 0.0, 1.9, 0.55),
    "regime_switching": Scenario("regime_switching", "Low/high/moderate volatility and toxicity regimes.", 1.0, 0.5, 0.4, regime=True),
    "stress": Scenario("stress", "High volatility, toxic one-sided flow, and a discrete jump.", 3.2, 1.2, 0.85, 2.0, 0.65, -0.9),
}

def build_scenario_model(name: str, steps: int, baseline_intensity: float = 90.0, distance_sensitivity: float = 18.0,
                         maker_fee_per_unit: float = 0.001) -> RegimeToxicMarketModel:
    s = SCENARIOS[name]
    if not s.regime:
        vol = [s.volatility] * steps
        beta = [s.information_flow] * steps
        rho = [s.information_correlation] * steps
        bid = [s.bid_multiplier] * steps
        ask = [s.ask_multiplier] * steps
    else:
        n1, n2 = int(0.35*steps), int(0.65*steps)
        vol = [0.55 if i < n1 else 2.5 if i < n2 else 0.9 for i in range(steps)]
        beta = [0.0 if i < n1 else 1.0 if i < n2 else 0.35 for i in range(steps)]
        rho = [0.0 if i < n1 else 0.75 if i < n2 else 0.3 for i in range(steps)]
        bid = [1.0 if i < n2 else 1.35 for i in range(steps)]
        ask = [1.0 if i < n2 else 0.8 for i in range(steps)]
    jumps = [0.0] * steps
    if s.jump_fraction != 0:
        jumps[steps//2] = s.jump_fraction
    return RegimeToxicMarketModel(
        drift_schedule=tuple([0.0]*steps), volatility_schedule=tuple(vol),
        information_flow_schedule=tuple(beta), information_correlation_schedule=tuple(rho),
        bid_multiplier_schedule=tuple(bid), ask_multiplier_schedule=tuple(ask), jump_schedule=tuple(jumps),
        baseline_intensity=baseline_intensity, distance_sensitivity=distance_sensitivity,
        lot_size=1.0, maker_fee_per_unit=maker_fee_per_unit,
    )
