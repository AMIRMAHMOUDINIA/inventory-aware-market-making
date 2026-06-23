"""Analytical benchmarks for quote width and inventory feedback."""
from __future__ import annotations
from math import exp, log

def fill_intensity(distance: float, baseline_intensity: float, distance_sensitivity: float) -> float:
    return baseline_intensity*exp(-distance_sensitivity*distance)

def optimal_half_spread(distance_sensitivity: float, maker_fee_per_unit: float=0.0, adverse_loss_per_unit: float=0.0) -> float:
    if distance_sensitivity<=0: raise ValueError("Distance sensitivity must be positive.")
    return maker_fee_per_unit+adverse_loss_per_unit+1.0/distance_sensitivity

def expected_spread_rate(half_spread: float, baseline_intensity: float, distance_sensitivity: float, lot_size: float=1.0) -> float:
    return 2*fill_intensity(half_spread,baseline_intensity,distance_sensitivity)*lot_size*half_spread

def inventory_drift(inventory: float, half_spread: float, inventory_skew: float, baseline_intensity: float, distance_sensitivity: float, lot_size: float=1.0) -> float:
    bid=fill_intensity(half_spread+inventory_skew*inventory,baseline_intensity,distance_sensitivity)
    ask=fill_intensity(half_spread-inventory_skew*inventory,baseline_intensity,distance_sensitivity)
    return lot_size*(bid-ask)

def local_inventory_reversion_rate(half_spread: float, inventory_skew: float, baseline_intensity: float, distance_sensitivity: float, lot_size: float=1.0) -> float:
    return 2*baseline_intensity*lot_size*distance_sensitivity*inventory_skew*exp(-distance_sensitivity*half_spread)

def local_inventory_half_life(*args, **kwargs) -> float:
    k=local_inventory_reversion_rate(*args,**kwargs)
    return float("inf") if k==0 else log(2)/k
