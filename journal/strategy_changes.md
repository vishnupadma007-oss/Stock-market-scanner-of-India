# Strategy changes

Each approved change to `config.yaml` or the agents. `review.py` counts paper trades after the
latest date here before it allows a new proposal.

| Date | Change | Evidence | Approved by |
|---|---|---|---|
| 2026-10-18 | Baseline: both sides, 1% net target, no stop-loss, chart score >= 60, forecast chance >= 60% | 60-day backtest (journal/backtest_summary.md) | User |
| 2026-10-19 | Added News & Events, Macro and Forecast agents and the morning-brief day mode. Macro on; forecast shown only (not used to block or set the target) | Backtest in journal/backtest_summary.md: macro -0.35% -> +0.10%/trade; forecast filter/target made results worse | User asked for the agents; settings chosen from the backtest |
| 2026-10-19 | Paper account ₹10,000, whole free amount per trade (one at a time), realised P&L reinvested, no daily trade cap (careful mode only raises the chart score) | User decision: trade every qualifying setup for 1%+ net each | User |
| 2026-10-19 | Strike choice ITM1 -> ATM | Lot survey: with ₹10,000 only 3 of 16 ITM1 contracts fit vs 12 of 16 ATM (median ATM lot ≈ ₹8,000). Needed for the user's ₹10,000 account | User (₹10,000 capital) |
| 2026-10-19 | Capital ₹10,000 -> ₹30,000; strike ATM -> ITM1 | User decision on capital. With ₹30,000 all surveyed ITM1 lots fit (max ≈ ₹22,700), and ITM1 backtested better (+0.10% vs +0.03%/trade, worst -29% vs -38%) | User (capital) |
| 2026-10-20 | Watcher timing: INDmoney calls paced evenly at 450/hour (one every 8 s); entry scans back to back (~every 2 min) when no trade is open; exit checks every 15 s with a trade open | INDmoney limit 500/hour; user asked for regular, evenly spaced checks | User |
