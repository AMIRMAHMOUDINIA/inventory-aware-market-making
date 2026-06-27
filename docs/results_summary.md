# Results Summary

This document summarizes the configured simulation outputs. The results describe the stylized market settings included in this repository; they are not claims about live-trading profitability.

## Experiment scale

The main saved run contains six market scenarios, five strategy variants, 40 paired paths per scenario-strategy combination, and 250 intervals per path. This gives 1,200 path-strategy records. The paired-path setup is used so that strategy differences are compared on the same exogenous market paths rather than unrelated random paths.

## Main findings

### Toxic-flow scenario

Fixed quoting performed poorly when fills carried adverse information. Mean terminal P&L was -2.86, with a 5th-percentile outcome of -21.86. The full adaptive strategy raised mean terminal P&L to 1.66 and improved the 5th percentile to -5.07. Mean absolute inventory fell from 6.40 to 1.72 units.

Interpretation: the adaptive quote did not simply chase more fills. It reduced the inventory held through adverse moves and used markout feedback to defend the side being selected against.

### Stress scenario

The stress setting combined difficult flow, volatility, and jump conditions. Fixed quoting averaged -62.12, with a 5th percentile of -284.97. The full adaptive strategy averaged -1.67. The risk-controlled version averaged -1.15, with a 5th percentile of -11.16 and a halt probability of 22.5%.

Interpretation: the risk overlay improved the left tail, but it did so by reducing trading opportunity and sometimes stopping the strategy. This is a risk-control result, not a pure alpha result.

### One-sided flow

One-sided order flow created persistent inventory pressure. Fixed quoting reached mean absolute inventory of 20.88 units. Inventory-aware quoting reduced this to 7.91, while the full adaptive strategy reduced it further to 6.03.

Interpretation: inventory skew acted as a stabilizer. It was most useful when symmetric quote placement would otherwise accumulate directional exposure.

### Regime-switching volatility

In the regime-switching scenario, inventory-only quoting had mean P&L of 0.33 and a 5th percentile of -8.85. Adding volatility-aware quote width increased mean P&L to 2.30 and improved the 5th percentile to -4.69.

Interpretation: quote width adaptation became valuable when the price process changed faster than a static quoting rule could handle.

## Validation checks

Representative paths passed quote-geometry, positive-mid-price, interval-accounting, terminal-accounting, markout-identity, and inventory-limit checks where applicable. The largest interval reconciliation error in the saved validation summary is 2.65e-13; the largest terminal reconciliation error is 3.09e-12.

## Practical interpretation

The strongest result is not that one strategy is always best. The strongest result is the trade-off: inventory and markout controls reduced exposure and improved downside outcomes, but the same controls could lower trading volume and reduce spread capture in easier regimes. That is the central market-making lesson tested by the simulator.

## Main limitations

The market model is stylized. It does not reconstruct a full limit order book, queue position, latency, exchange priority rules, or empirical order-flow calibration. The simulator is useful for controlled mechanism testing, not for live deployment.
