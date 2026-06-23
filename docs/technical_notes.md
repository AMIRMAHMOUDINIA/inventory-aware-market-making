# Notes for reading the simulation

These are the questions I found most useful when checking whether an apparently profitable quote was actually profitable after price movement and inventory risk.

## Spread capture is only the first line of the P&L

A passive fill earns edge relative to the current mid-price. That does not mean the position has earned a profit after the next price move. The markout and the inventory-price component show how much of the initial edge survives.

## Symmetric flow does not keep inventory near zero on every path

Even when bid and ask arrivals are symmetric in expectation, the finite-path difference between buys and sells can become large. Inventory skew is therefore a feedback mechanism, not a correction for a biased flow assumption.

## Stronger skew has a cost

Moving the quote asymmetrically can reduce inventory, but the reducing side may become too aggressive while the accumulating side loses fills. The useful range is a balance between position control and execution quality.

## Volatility estimation can lag the regime

An EWMA estimator reacts after returns arrive. In a sudden regime change, the quote can remain too narrow before the estimate catches up, then remain too wide after conditions calm down.

## A poor markout is not automatically toxicity

Negative post-fill movement can come from broad volatility, a temporary jump, or persistent side-specific selection. I look at the side, horizon, and repetition of the loss before treating it as adverse-selection feedback.

## Hard limits improve one risk measure by paying another cost

Forced reduction and halts can improve the left tail, but they may cross the spread, pay fees, incur impact, and miss a subsequent recovery. Their value should be read from both the tail outcomes and the execution-cost attribution.

## Latent decomposition is not directly observable

Spread, fees, cash, inventory, and realized price changes are observable inside the simulation. The split of price movement into information and independent noise depends on the way the synthetic market was constructed.

## Questions I would examine next

- How sensitive are the conclusions to slower or faster estimator decay?
- What changes when queue position and cancellations are added?
- How does the risk layer behave when liquidity falls exactly when inventory must be reduced?
- Can the adverse-selection estimator distinguish a one-off jump from persistent toxic flow?
- How do the results change when hedging in a correlated instrument is allowed?
