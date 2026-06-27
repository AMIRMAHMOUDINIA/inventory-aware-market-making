# Future Work

The current simulator is designed for mechanism testing. The natural next step is not to add model complexity for its own sake, but to connect the assumptions more directly to market data.

## 1. Empirical calibration

Estimate the simulator's key parameters from trade-and-quote data:

- mid-price volatility by time of day;
- quoted spread distribution;
- fill probability as a function of quote distance;
- side-specific short-horizon markouts after fills;
- order-flow imbalance and persistence;
- jump frequency and jump-size distribution.

The added calibration notebook shows the structure of this analysis using path-level data already produced by the simulator. A real extension would replace the simulated records with timestamped quotes and trades.

## 2. Queue and priority modelling

The current execution model treats fills probabilistically. A more realistic simulator would model queue position, displayed size ahead of the order, cancellations, and partial fills.

## 3. Latency and stale quotes

A useful stress test would delay quote updates after volatility or toxicity changes. This would show when a strategy loses money because it reacts correctly but too late.

## 4. Multi-asset or correlated hedging

The model currently handles one instrument. A natural extension is a related-instrument setting where inventory can be hedged in a correlated product, introducing basis risk and execution cost.

## 5. Out-of-sample parameter testing

The strategy parameters could be selected under one synthetic market environment and evaluated under a different one. This would test whether the apparent improvement is robust or dependent on the calibration regime.

## 6. More conservative reporting

Future reports should continue to separate gross spread capture, fees, inventory price P&L, markout, jumps, forced execution, and terminal liquidation. This avoids summarizing a strategy only by terminal P&L.
