# Where the simulator stops

I kept the model small enough that the source of each effect remains visible. As a result, it leaves out several features that would matter in live execution:

- a full limit-order book and queue-priority mechanics;
- latency, message throttling, and exchange-specific matching rules;
- hidden, iceberg, and pegged orders;
- empirical calibration to a particular asset or venue;
- production market-impact and slippage models;
- funding, borrowing, margin, and default constraints;
- cross-asset hedging and multi-venue routing;
- live data handling, order gateways, monitoring, and recovery infrastructure.

The latent toxic-flow model creates a controlled relationship between fill direction and subsequent price movement. It is not meant to reproduce the information structure of a real exchange.

The numerical results depend on the chosen parameters and the finite Monte Carlo sample. I read them as comparisons of mechanisms under stated assumptions, not as forecasts or evidence of deployable profitability.
