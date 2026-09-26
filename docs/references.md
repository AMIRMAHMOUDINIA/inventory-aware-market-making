# References and Model Lineage

This project is a stylized market-making simulator rather than a direct replication of one theoretical model. The references below are the main papers that motivate the inventory-risk, adverse-selection, and informed-flow mechanisms used in the code.

## Glosten and Milgrom (1985)

Lawrence R. Glosten and Paul R. Milgrom.
**“Bid, Ask and Transaction Prices in a Specialist Market with Heterogeneously Informed Traders.”**
*Journal of Financial Economics*, 14(1), 71–100, 1985.
DOI: 10.1016/0304-405X(85)90044-3.

**Relationship to this project:**
The toxic-flow process in `toxic_market_model.py` is Glosten–Milgrom in structure: informed order flow is more likely to arrive on the side associated with subsequent adverse price movement, so passive liquidity provision can lose money after a fill. The implementation is deliberately stylized and is not intended as a calibrated reproduction of the original equilibrium model.

## Ho and Stoll (1981)

Thomas Ho and Hans R. Stoll.
**“Optimal Dealer Pricing under Transactions and Return Uncertainty.”**
*Journal of Financial Economics*, 9(1), 47–73, 1981.
DOI: 10.1016/0304-405X(81)90020-9.

**Relationship to this project:**
Ho and Stoll provide the foundational inventory-risk view of dealer quoting. The inventory-aware strategies in this simulator follow the same economic intuition: quote placement changes with inventory because carrying an unbalanced position exposes the market maker to price risk.

## Avellaneda and Stoikov (2008)

Marco Avellaneda and Sasha Stoikov.
**“High-Frequency Trading in a Limit Order Book.”**
*Quantitative Finance*, 8(3), 217–224, 2008.
DOI: 10.1080/14697680701381228.

**Relationship to this project:**
The repository directly implements the finite-horizon Avellaneda–Stoikov reservation price and optimal spread as a separate theoretical benchmark. The benchmark uses the simulator’s exponential distance-dependent fill model, maps `k` to the existing `distance_sensitivity`, and exposes passive-quote clipping when the analytical quote would otherwise cross the mid-price.

## Guéant, Lehalle, and Fernandez-Tapia (2013)

Olivier Guéant, Charles-Albert Lehalle, and Joaquin Fernandez-Tapia.
**“Dealing with the Inventory Risk: A Solution to the Market Making Problem.”**
*Mathematics and Financial Economics*, 7(4), 477–507, 2013.
DOI: 10.1007/s11579-012-0087-0.

**Relationship to this project:**
This paper extends the same stochastic-control market-making family with explicit inventory constraints and tractable approximations to optimal quotes. It is useful context for interpreting the Avellaneda–Stoikov benchmark and the simulator’s separate inventory and risk-control mechanisms, although its solution is not implemented here as an additional strategy.

## Kyle (1985)

Albert S. Kyle.
**“Continuous Auctions and Insider Trading.”**
*Econometrica*, 53(6), 1315–1335, 1985.
DOI: 10.2307/1913210.

**Relationship to this project:**
Kyle provides the classic informed-trader, noise-trader, liquidity-provider framework for thinking about information-driven order flow and price impact. The simulator’s latent information signal and toxic-flow diagnostics use that broader microstructure framing, but the simulator is not a Kyle equilibrium model.

## Scope

These papers motivate different pieces of the simulator rather than defining a single unified model:

- Ho–Stoll motivates inventory-sensitive dealer behavior.
- Glosten–Milgrom motivates adverse selection from informed order flow.
- Kyle provides a broader informed-trading and price-impact framework.
- Avellaneda–Stoikov supplies the analytical benchmark implemented directly in the repository.
- Guéant–Lehalle–Fernandez-Tapia provides a tractable extension of the stochastic-control market-making framework with explicit inventory constraints.

The synthetic scenarios, markout feedback, risk-state machine, forced inventory reduction, P&L attribution, and stress tests are project-specific components built around those ideas.