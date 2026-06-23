# How I checked the simulator

The main failure modes I wanted to rule out were sign mistakes, look-ahead in the event order, accidental differences in paired price paths, and P&L components that did not reconcile to wealth.

## Unit checks

The automated suite checks quote geometry, tick rounding, trade signs, ledger updates, analytical benchmarks, estimator behavior, toxic-flow direction, risk-state transitions, aggressive execution, and statistical utilities.

## Path-level checks

Integration tests verify:

- identical exogenous price paths for paired strategies;
- hard inventory-limit enforcement;
- markout identities;
- drift, information, noise, and jump decomposition;
- exact interval and terminal accounting.

## Saved validation records

`outputs/tables/validation_summary.csv` contains checks for representative toxic, regime-switching, and stress paths. The records show:

- positive mid-prices;
- non-crossed quotes;
- passing interval reconciliation;
- passing terminal reconciliation;
- passing trade-markout identities;
- passing hard-inventory enforcement in the stress path.

The largest interval residual in those paths is below `3e-13`, and the terminal residuals are below `4e-12`.
