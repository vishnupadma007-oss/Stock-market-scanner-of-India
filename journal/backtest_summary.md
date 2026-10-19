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

## QuantForge validation (metrics.py on the backtest trades, P&L as a fraction of ₹1 lakh)

| | Trades | Win rate | Profit factor | Chance the edge is zero or negative | Edge if charges double |
|---|---|---|---|---|---|
| Both sides | 79 | 89% | 0.50 | 90% | negative |
| Losers only | 34 | 91% | 1.29 | 56% | negative |

Verdict under QuantForge's gates: **not ready for real money**. Both fail the
"backtest -> out-of-sample" gate (needs about 100+ trades and a clearly positive result after
costs). Losers-only is promising but not yet distinguishable from luck, and its small edge
disappears if real charges/slippage are about twice the model. Next stage: paper trading,
mainly to measure real bid-ask fills.

## New agents (2026-10-19): Macro and Forecast

Same 60 days, with Yahoo history for sector indices, crude oil (CL=F) and USD/INR. The News &
Events agent cannot be backtested (no free intraday news history); it is judged in paper trading.

| Variant | Trades | Hit target | Avg net/trade | Worst | Net P&L |
|---|---|---|---|---|---|
| Base | 79 | 90% | -0.35% | -36.9% | -₹6,989 |
| + Forecast filter (skip if reversal level is closer than needed) | 71 | 87% | -0.74% | -36.9% | -₹13,076 |
| + Forecast target (aim for 70% of the forecast move) | 70 | 63% | -3.16% | -36.9% | -₹55,362 |
| **+ Macro (sector, crude, rupee)** | 76 | 91% | **+0.10%** | **-29.1%** | **+₹1,808** |
| + Macro + forecast filter | 66 | 88% | -0.27% | -29.1% | -₹4,500 |
| All + forecast target | 62 | 61% | -3.45% | -36.5% | -₹53,521 |
| Losers only | 37 | 89% | +0.49% | -8.1% | +₹4,568 |
| Losers + macro | 35 | 89% | +0.48% | -8.1% | +₹4,161 |
| Losers + macro + forecast filter | 28 | 86% | +0.33% | -8.1% | +₹2,326 |

Decision: Macro agent on (it filters bad gainer trades); forecast shown on every signal but
not used to block or set the target. Aiming for bigger reversals loses the quick 1% that makes
this strategy work: winners take a median of 10 minutes, and waiting for more lets them turn.

## ATM vs one-strike-ITM (2026-10-19, macro on, same 60 days)

| Strike | Trades | Hit target | Avg net/trade | Winners | Misses | Worst | Losers side | Net P&L |
|---|---|---|---|---|---|---|---|---|
| ITM1 | 76 | 91% | +0.10% | +1.15% | -10.26% | -29.1% | +0.49% | +₹1,808 |
| ATM | 76 | 91% | +0.03% | +1.25% | -12.01% | -38.0% | +0.60% | +₹482 |

Same trades and hit rate. ATM options move more in % terms both ways: slightly bigger wins,
bigger misses. Switched to ATM anyway because with a ₹10,000 account most ITM lots do not fit.
