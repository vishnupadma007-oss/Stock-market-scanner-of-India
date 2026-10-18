# Backtest: mover-reversal options, 2026-08 to 2026-10 (60 trading days)

`python backtest_reversal.py` on Yahoo 5-minute data, 76 F&O stocks, scans every 15 min
09:45-14:30, max 2 trades/day, 1% net target after all charges, square-off 15:15, no stop-loss.
Option prices simulated (Black-Scholes, constant volatility, 0.8% bid-ask gap), so real results
will differ, especially from implied-volatility changes. Small sample: treat as a first read.

| Variant | Trades | Hit target | Avg net/trade | Worst | Net P&L |
|---|---|---|---|---|---|
| Base (no stop-loss) | 79 | 90% | -0.35% | -36.9% | -₹6,989 |
| Time exit 30 min | 79 | 70% | -0.99% | -17.0% | -₹19,623 |
| Time exit 60 min | 79 | 76% | -1.02% | -18.2% | -₹20,213 |
| Target 2% | 79 | 84% | -0.73% | -36.9% | -₹14,351 |
| Chart score >= 75 | 56 | 89% | -0.83% | -33.2% | -₹11,648 |
| Score >= 75 + time exit 45 | 56 | 64% | -1.74% | -27.1% | -₹24,404 |
| Target 2% + time exit 45 | 79 | 63% | -0.97% | -24.5% | -₹19,152 |
| Top losers only (buy CE) | 34 | 91% | +0.51% | -8.1% | +₹4,343 |

Findings
- Winners reach the target fast (median 10 minutes); 90% of trades hit it.
- With a small target and no stop-loss, the 10% of misses (trend continuations, e.g. COFORGE
  28 Aug -36.9%, BAJFINANCE 23 Sep -29.1%) outweigh all the wins: break-even needs ~92% hits.
- Time exits cut good trades that would have recovered: worse in every test.
- Buying PE on top gainers lost money (-1.01%/trade); buying CE on top losers made money
  (+0.51%/trade). The "losers only" row is the losers' trades from the base run, not a
  separate run with the daily trade limit given only to losers.
