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

## Quiet volume spurt (user's idea, 28 Oct 2026)

Heavy volume for the time of day (cumulative volume vs the same bar over the previous 10 sessions)
while the stock has moved only a little from yesterday's close; buy the option in the direction of
that move (latest candle and VWAP side agreeing), first signal per stock per day from 09:30.
~60 days x 76 stocks, ITM1, 1% net target, square-off 15:20, no stop-loss; opposite direction as control.

| Volume vs usual | Move so far | Trades | Hit % | Avg per trade | Opposite (control) |
|---|---|---|---|---|---|
| >= 1.5x | 0.2-0.5% | 338 | 90% | -0.72% | -2.51% |
| >= 3.0x | 0.3-1.0% | 71 | 90% | -0.96% | -2.68% |
| >= 2.0x | 0.2-0.7% | 200 | 85% | -1.72% | -1.92% |
| >= 2.0x | 0.3-1.0% | 256 | 85% | -1.85% | -2.50% |
| >= 3.0x | 0.2-0.7% | 56 | 86% | -1.79% | -1.23% |

The direction carries real information (the best variants beat their mirror image by ~1.7 points),
but every variant loses on average with this exit: in the best one 304 wins averaged +1.19%
(+Rs 1.09 lakh) and 34 losers averaged -17.8% (-Rs 1.82 lakh). Same pattern as every strategy
tested so far: the small fixed target with no stop-loss.

### Quiet volume spurt with bigger targets (user's plan, 28 Oct 2026)

`python backtest_spurt.py --targets 1 10` (uses agents/spurt.py, the live code). Volume >= 1.5x usual,
move 0.2-0.5%, same option model, no stop-loss, square-off 15:20:

| Net target | Trades | Hit % | Avg per trade | Opposite (control) | Net |
|---|---|---|---|---|---|
| 1% | 338 | 90% | -0.72% | -2.51% | -Rs 72,982 |
| **10%** | 174 | 68% | **+2.89%** | -4.19% | **+Rs 1,50,515** |

The first strategy in our tests that is positive and clearly beats its mirror image; positive in both
halves of the period (+3.35% and +2.43% per trade). Winners averaged +10.2%, the rest -12.5%.
(The Risk agent's 60% hit-chance filter keeps 174 of the 338 signals at the 10% target.)
20%+ targets: too few trades pass to judge. Live from 29 Oct (news team, label `quiet-spurt`).

### "News Team Wiring Enhanced" proposal (user, 29 Oct 2026)

Same 60 days x 76 stocks, quiet-spurt entries, no stop-loss, 15:20 square-off; the proposal's
1-minute volume-fade exit approximated on 5-minute candles (sell on a candle with < 50% of the spurt
candle's volume and no new high or a 35%+ wick, if the option is up 5%+ or between -1% and +2%).

| Variant | Trades | Avg per trade | Net |
|---|---|---|---|
| **Current: 1.5x, 0.2-0.5%, 10% target, hold** | 174 | **+2.89%** | **+Rs 1,50,515** |
| Current + volume-fade exit | 174 | +1.49% | +Rs 77,542 |
| Proposed 2.0x, 0.2-0.6%, 10% target | 91 | +1.96% | +Rs 53,259 |
| Proposed 2.0x + volume-fade exit | 91 | +0.22% | +Rs 5,958 |
| Current, 15% target (hit-chance filter) | 61 | +5.89% | +Rs 1,07,715 |
| Current, 25% target, no filter | 347 | +1.15% | +Rs 1,19,122 |

The fade exit cut trades that went on to reach their target (scratch exits in 36-50% of trades);
the stricter 2.0x spurt halved the trades and lowered the average. Bigger targets earn more per
trade but fewer trades qualify; the 10% target gave the most in total. News tiers cannot be tested
(no news history). Not adopted; kept for the user's decision.

### Sector check and overnight carry (user's ideas, 29 Oct 2026)

Quiet spurt, 1.5x / 0.2-0.5% / 10% target, 60 days x 76 stocks. Sector = average move of the other
F&O stocks in the same sector at the signal time (no sector index history in our data).

| Variant | Trades | Hit % | Avg per trade | Net |
|---|---|---|---|---|
| **Current** | 174 | 68% | **+2.89%** | **+Rs 1,50,515** |
| Skip when the sector moves against the trade at all | 94 | 65% | +2.09% | +Rs 58,920 |
| ...the trades that would be skipped | 78 | 71% | +3.65% | +Rs 85,434 |
| Skip when the sector is 0.5%+ against | 143 | 66% | +2.65% | +Rs 1,13,555 |
| Hold overnight when the target is not hit by 15:20 | 174 | 79% | +1.84% | +Rs 95,900 (worst -94.5%) |
| ...the 56 trades carried overnight | 56 | 36% | -15.77% | -Rs 2,64,597 |
| ...the same 56 squared off at 15:20 | 56 | 0% | -12.51% | -Rs 2,09,982 |

A spurt against its own sector did better, not worse (stock-specific buying is the signal), and
carrying unfinished trades overnight lost more than squaring them off. Neither adopted.

### Overnight carry on quiet nights only (user, 29 Oct 2026)

The 52 quiet-spurt trades that missed their target by 15:20, split by whether the stock had results
that day or the next (from journal/results_history; RBI/Fed dates not in our data):

| Group | Trades | Square off 15:20 | Carry to next day |
|---|---|---|---|
| All | 52 | -12.48% | -15.99% |
| Quiet (no results) | 51 | -12.27% | -14.64% |
| Quiet and in profit at 15:20 | 10 | **+3.91%** | -5.53% |
| Quiet and at a loss at 15:20 | 41 | -16.22% | -16.86% |

51 of the 52 nights were already "quiet", and carrying still lost more: the overnight losses are not
event-driven. Not adopted.

### Early chart exit (user's idea, 30 Oct 2026)

Sell as soon as the chart turns against the trade, instead of holding to the target or 15:20.
Two rules on 5-minute closes: `entry_bar` (the stock closes beyond the low/high of the candle
before entry) and `vwap` (closes on the wrong side of VWAP on a falling candle with rising volume).
`--set early_exit=entry_bar|vwap`, same 60 days x 76 stocks (5 Aug - 30 Oct 2026).

| Strategy | Exit | Trades | Hit % | Avg per trade | Net |
|---|---|---|---|---|---|
| Quiet spurt, 10% target | **hold (current)** | 171 | 68 | **+2.47%** | **+Rs 1,26,586** |
| Quiet spurt, 10% target | entry_bar | 171 | 52 | +0.90% | +Rs 45,937 |
| Quiet spurt, 10% target | vwap | 171 | 54 | +0.77% | +Rs 39,267 |
| Movers reversal, 1% target | **hold (current)** | 130 | 85 | -0.93% | -Rs 36,390 |
| Movers reversal, 1% target | entry_bar | 130 | 68 | -1.18% | -Rs 46,169 |
| Movers reversal, 1% target | vwap | 130 | 72 | -1.04% | -Rs 40,617 |

Both rules cut the worst losses (spurt worst trade -46% -> -31%) but sell too many trades that
later reach the target, so total profit falls by about two thirds. On 30 Oct alone they would have
helped (news team about -Rs 8,000 / -Rs 6,700 instead of -Rs 15,076). Not adopted.

### Probability Analyzer (user's design, 31 Oct 2026)

`python backtest_probability.py --intraday .. --daily ..`: every quiet-spurt trade (10% target, no
stop-loss) judged before entry, walk-forward (base rate and learned score fitted on earlier days only;
first 15 days used for learning). Readings: historical base rate (time of day x spurt size x side),
Monte Carlo of 2,000 futures re-sampling the stock's own 5-minute moves with the option re-priced,
logistic-regression score, expected value after charges; cut = weakest third of past trades.

| Group (out-of-sample) | Trades | Hit % | Avg per trade | Worst | Net |
|---|---|---|---|---|---|
| All | 133 | 69 | +2.34% | -46.1% | +Rs 93,087 |
| Approved | 87 | 71 | **+3.48%** | -33.2% | +Rs 90,768 |
| Rejected | 46 | 65 | +0.17% | -46.1% | +Rs 2,318 |

The Monte Carlo is cautious (57% average chance vs 68% actual: spurts have follow-through a
random walk lacks). Not proven: in the first half of the period the rejected trades did better
(+4.5% vs +3.8%), only the second half separated (-2.9% vs +3.2%); a random 87 trades matched the
approved average 9% of the time. Running in observe mode; switch `probability.mode: gate` only if
live trades agree.

### Trade News Monitor (user's request, 31 Oct 2026)

`python backtest_trade_news.py --intraday ..`: the 30 closed paper trades of 21-30 Oct replayed bar by bar
with the news that was in `journal/intel/` at each moment (option re-priced at the volatility implied by
the real entry; shock states were not logged, so not replayed). Totals in the same model:

| Variant | Net (30 trades) | Trades acted on |
|---|---|---|
| No monitor (model) | -Rs 11,344 | - |
| Word list: own + market/geopolitical news | -Rs 14,894 | 13 |
| Word list: stock's own news only | -Rs 10,584 | 1 (no exit fired) |
| Own news, raise target +5% on milder good news | -Rs 9,585 | 3 raises |
| Own news, raise +10% | -Rs 18,954 | 3 raises |
| AI helper (Gemini) judging own + market news | -Rs 14,708 | 8 |

Market-wide exits fired on background Iran-war / crude headlines and cut winners (TVS Motor +4,079 -> -917,
Sun Pharma +1,621 -> -85); the AI helper made the same calls. The stock's own bad news never arrived during a
trade in these 30, so that part is untested. Live in observe mode with market-news exits off.

Probability Analyzer on the 30 Oct live quiet-spurt trades (model fitted on the 130 earlier backtest trades):
it approved all four (Kotak, Cholamandalam, Bank of Baroda, Eicher), so it would not have changed the day.
