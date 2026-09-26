import math

import pytest

from market_maker_lab.analysis import (
    expected_spread_rate,
    fill_intensity,
    inventory_drift,
    local_inventory_half_life,
    local_inventory_reversion_rate,
    optimal_half_spread,
)


@pytest.mark.parametrize("distance", [0, 0.01, 0.05, 0.1])
def test_fill_intensity_nonnegative(distance):
    assert fill_intensity(distance, 100, 20) >= 0


def test_intensity_decreases():
    assert fill_intensity(0.01, 100, 20) > fill_intensity(0.1, 100, 20)


@pytest.mark.parametrize(
    "fee,loss,expected", [(0, 0, 0.05), (0.005, 0, 0.055), (0.005, 0.02, 0.075)]
)
def test_optimal_spread(fee, loss, expected):
    assert math.isclose(optimal_half_spread(20, fee, loss), expected)


def test_revenue_peak_near_inverse_k():
    values = [expected_spread_rate(x, 100, 20) for x in (0.02, 0.05, 0.1)]
    assert values[1] > values[0] and values[1] > values[2]


@pytest.mark.parametrize("q,sign", [(5, -1), (-5, 1), (0, 0)])
def test_inventory_drift_direction(q, sign):
    d = inventory_drift(q, 0.05, 0.003, 100, 20)
    assert d < 0 if sign < 0 else d > 0 if sign > 0 else abs(d) < 1e-12


def test_reversion_strength():
    weak = local_inventory_reversion_rate(0.05, 0.001, 100, 20)
    strong = local_inventory_reversion_rate(0.05, 0.005, 100, 20)
    assert strong > weak > 0 and local_inventory_half_life(
        0.05, 0.005, 100, 20
    ) < local_inventory_half_life(0.05, 0.001, 100, 20)
