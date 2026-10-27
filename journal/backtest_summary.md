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

## Order-flow / early-movement detectors (user's whitepaper), 24 Oct 2026

`python backtest_orderflow.py` on ~60 days x 76 stocks, 5-min candles, same option model, charges and
exits as the reversal backtest (ITM1, 1% net target, square-off 15:20, no stop-loss). Control: the same
entries traded in the opposite direction.

| Detector | Trades | Hit % | Avg per trade | Opposite direction (control) |
|---|---|---|---|---|
| Squeeze breakout (BB inside Keltner, RVOL >= 2x, VWAP side) | 751 | 79% | -1.83% | -1.40% |
| Wyckoff spring / upthrust | 3,947 | 81% | -1.53% | -1.38% |
| VWAP reclaim / loss (RVOL >= 1.8x) | 2,975 | 84% | -2.00% | -1.94% |
| CVD absorption (candle-estimated delta) | 4,472 | 84% | -1.73% | -1.40% |

No detector beat its mirror image: no directional information after costs. PUTs did better than CALLs
for every detector, which is the falling market of these 60 days, not the signals.
Also: random-looking entries reach the 1% target 80-85% of the time, about the reversal strategy's 83%,
so the high hit rate comes from the small target, not from skill; the loss per trade (-1.4 to -2%)
comes from the misses held to 15:20 without a stop-loss.
Not backtestable (no history): intraday option-OI velocity, gamma exposure, order book.

## Gap-recovery idea and results-gap, 26 Oct 2026

Buying the recovery of a 1.5%+ opening gap at 09:20 (CALL after a gap-down, PUT after a gap-up), 60 days:
ordinary days 147 trades, 89% / 84% / 78% at a 1% / 3% / 5% target, average -2.5% / -1.7% / -1.2%,
worst -100%; following the gap did worse (-3.4% / -2.4% / -2.3%). Results days (13): both lose.
Fading beats following on ordinary days (the reversal effect), but the misses held to 15:20 without
a stop-loss make it lose overall. Not added as a strategy.
Daily data, 1 year x 76 stocks: results-day gaps carry on 61-75%; ordinary-day gaps of 2%+ reverse 55-58%.
NSE pre-open, 26 Oct: of 13 F&O stocks with a 1%+ pre-open gap only 23% kept going after the open.

## Enhancement pack chart signals (27 Oct 2026), same 60-day data
Reversal backtest with the new Chart Reader (climax-volume absorption, RSI divergence, loss cooldown):
132 trades, 85% at target, average -0.84% per trade (was -1.55%), misses -12% (was -15%),
worst -43% (was -86%), total -Rs 33,086 (was -Rs 56,168). Better, still negative overall.
