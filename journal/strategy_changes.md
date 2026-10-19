# Strategy changes

Each approved change to `config.yaml` or the agents. `review.py` counts paper trades after the
latest date here before it allows a new proposal.

| Date | Change | Evidence | Approved by |
|---|---|---|---|
| 2026-10-18 | Baseline: both sides, 1% net target, no stop-loss, chart score >= 60, forecast chance >= 60% | 60-day backtest (journal/backtest_summary.md) | User |
| 2026-10-19 | Added News & Events, Macro and Forecast agents and the morning-brief day mode. Macro on; forecast shown only (not used to block or set the target) | Backtest in journal/backtest_summary.md: macro -0.35% -> +0.10%/trade; forecast filter/target made results worse | User asked for the agents; settings chosen from the backtest |
