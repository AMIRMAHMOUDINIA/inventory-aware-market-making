# Model choices and accounting

This note records the choices I made to keep execution, price movement, risk actions, and P&L attribution separate enough to inspect.

## Market state and event order

The simulator uses a fixed clock. At each interval, the strategy observes the current mid-price and inventory, updates its online estimators, proposes a quote, and then passes that quote through an independent risk layer. Any forced reduction occurs before passive fills. The market model then samples quote-dependent order arrivals and the next price movement.

I keep this order explicit because letting the strategy use the next price move, or applying a risk action after fills when it was meant to act before them, changes the economics of the path.

## Fill model

For quote distance \(\delta\), baseline arrival intensity is

\[
\lambda(\delta)=A e^{-k\delta}.
\]

Bid and ask intensities can also depend on a latent signal, side-specific flow multipliers, and the quote distances chosen by the strategy. Displayed size caps execution quantity.

The exponential form gives a controllable trade-off: moving away from the mid increases edge per fill but lowers the expected number of fills.

## Toxic-flow construction

A latent signal \(I_t\) affects both order-flow direction and the next price movement. Negative signals increase bid-side executions and predict negative information moves; positive signals increase ask-side executions and predict positive information moves.

I separate the price and fill random streams. This allows different quoting rules to receive the same exogenous price path while still producing different executions.

## Quoting controls

Inventory changes quote asymmetry. Volatility changes total width through

\[
h_t=\operatorname{clip}(h_0+\alpha_\sigma\hat\sigma_t\sqrt{\tau},h_{\min},h_{\max}).
\]

Side-specific EWMA adverse-loss estimates widen the side with persistently poor post-fill movement. The markout feedback is deliberately backward-looking; it does not observe the latent signal directly.

## Risk controls

The risk manager supports normal, reduce-only, cooldown, forced-reduction, and halted states. Forced execution crosses an external spread and includes linear per-unit impact, producing quadratic total impact cost.

I keep this layer separate from the quoting rule so that a strategy can be compared with and without the same hard controls.

## P&L attribution

Every interval is reconciled through

\[
\Delta W=\Pi^{forced}+\Pi^{spread}-C^{maker}+q^+\Delta m.
\]

Price P&L is decomposed into new-fill and carried-inventory exposure. In coupled scenarios it is further divided into drift, information, independent noise, and jump components.

The decomposition is useful only if it sums back to the exact wealth change, so the residual is checked at both interval and terminal levels.

## Paired Monte Carlo design

For each scenario and path identifier, every strategy receives the same market seed. The price stream is independent of the fill stream, preserving identical exogenous price paths while allowing quotes to change execution outcomes.

This pairing is important: without it, part of a strategy difference could simply come from one strategy receiving an easier random path.

## Saved experiment size

The core output uses 40 paired paths per strategy and scenario, five strategies, six scenarios, and 250 intervals per path. The robustness grids use smaller fixed-seed samples so the full run remains practical on a laptop.
