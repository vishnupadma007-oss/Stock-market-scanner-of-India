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

### Quiet spurt with small targets and repeat entries (user's idea, 31 Oct 2026)

Same 60 days x 76 stocks, no hit-chance filter, no stop-loss, 15:20 square-off. "Repeat" = after a trade ends,
the next spurt candle in the same stock that day is traded again.

| Target | Entries | Trades | Hit % | Win avg | Miss avg | Avg per trade | Net |
|---|---|---|---|---|---|---|---|
| 1% | once a day | 341 | 88 | +1.2% | -16.2% | -0.96% | -Rs 98,275 |
| 1% | repeat | 580 | 84 | +1.2% | -16.2% | -1.68% | -Rs 2,91,662 |
| 3% | once a day | 341 | 79 | +3.2% | -13.5% | -0.35% | -Rs 35,541 |
| 5% | once a day | 341 | 69 | +5.2% | -12.1% | -0.17% | -Rs 17,018 |
| 10% | once a day | 341 | 53 | +10.2% | -10.3% | +0.57% | +Rs 58,552 |
| 10% | repeat | 379 | 52 | +10.2% | -10.1% | +0.42% | +Rs 47,398 |

A 1% win cannot pay for the misses: one miss (-16%) wipes out ~14 wins, and repeat entries add mostly losing
trades. Only the 10% target is profitable (more so with the Risk agent's hit-chance filter: +Rs 1,26,586).
Not adopted.

### Small target with a stop-loss and repeat entries (user's idea, 31 Oct 2026)

Quiet spurt, same 60 days x 76 stocks; stop = option bid falls this % below the entry price (checked before
the target inside each 5-minute bar); "repeat" = trade the next spurt in the same stock after each exit.

| Target | Stop-loss | Entries | Trades | Hit % | Stopped % | Avg per trade | Net |
|---|---|---|---|---|---|---|---|
| 0.5% | 3% | once | 341 | 47 | 51 | -1.74% | -Rs 1,77,370 |
| 0.5% | 3% | repeat | 934 | 50 | 48 | -1.72% | -Rs 4,79,947 |
| 0.5% | 5% | repeat | 853 | 63 | 34 | -1.87% | -Rs 4,77,803 |
| 1% | 3% | repeat | 915 | 48 | 49 | -1.59% | -Rs 4,34,378 |
| 2% | 3% | repeat | 866 | 42 | 55 | -1.47% | -Rs 3,79,992 |
| 10% | 3% | once | 341 | 23 | 74 | -0.49% | -Rs 50,435 |
| **10%** | **none** | once | 341 | 53 | 0 | **+0.57%** | **+Rs 58,552** |

A 3% stop on an option is inside its normal 5-minute noise (the bid-ask gap alone is ~1%), so about half of
all trades are stopped out; a 0.5% win (+0.67% after costs) cannot pay for -3.9% stops. More trades only add
more of the same loss. Not adopted; the desk keeps the 10% target and no stop-loss.

### Target x stop-loss grid for both teams (user's request, 1 Nov 2026)

Same 60 days; entries fixed (movers: live reversal rules, 152 trades; quiet spurt: first signal a day, 341),
exits re-simulated for targets 1-30% net x stop-loss none/10/15/20/25/30/40/50% (88 combinations each).
Chosen on the first half, checked on the second (quantforge-ai gates).

- Movers reversal: every one of the 88 combinations loses money in the backtest (best: 15% target, 10% stop,
  -Rs 24,900; current 1% / no stop -Rs 79,300). Its paper record (9 of 9 targets) is not confirmed by history.
- Quiet spurt: no stop-loss beats every stop level at every target. Without the hit-chance filter, 15-20%
  targets look steadier than 10%; with the live 60% hit-chance filter (how the desk trades):

| Target | Trades | Hit % | Avg | Net | Quarters (Rs) |
|---|---|---|---|---|---|
| **10% (current)** | 171 | 68 | +2.47% | **+1,26,586** | +34.6k, +16.6k, +46.8k, +28.6k |
| 12.5% | 111 | 65 | +3.22% | +1,07,175 | +33.5k, +13.5k, +53.4k, +6.7k |
| 15% | 64 | 67 | +4.81% | +92,374 | +32.7k, +27.6k, +43.2k, -11.1k |
| 20% | 23 | 39 | -2.02% | -13,953 | +1.2k, +20.5k, -20.2k, -15.5k |

The current setting (10% target, no stop-loss, hit-chance filter) is the best tested: the most profit, the
most trades, positive in all four quarters. No change.

### Overnight carry on the real paper trades (user, 2 Nov 2026)

The 9 paper trades of 27-30 Oct that missed their target, held to the next session on real INDmoney option
prices (30-minute candles; next-day exit at ~15:20, charges not included):

| Trade | Squared off (actual) | Carried to next day |
|---|---|---|
| TCS PUT 27 Oct | -3,274 | target hit at the open: +2,576 |
| BPCL PUT 28 Oct | +604 | -2,173 |
| Adani Ports CALL 28 Oct | -1,006 | target hit at the open: +2,304 |
| HUL CALL 29 Oct | -190 | -1,710 |
| Asian Paints CALL 29 Oct (results that evening) | -270 | target hit: +1,363 |
| Kotak CALL 30 Oct | -1,593 | target hit: +2,700 |
| Cholamandalam CALL 30 Oct (RBI talk overnight) | -7,507 | target hit: +3,563 |
| Bank of Baroda CALL 30 Oct (results that evening) | -6,375 | target hit: +2,750 |
| Eternal CALL 30 Oct | -2,614 | -1,576 |
| **Total** | **-22,225** | **+9,797** (6 of 9 hit) |

Market-wide "important" news arrived on every night (56-85 items), so a "no big news" rule cannot be
judged from headlines; the stock's own news excluded 3 of the 9. Opposite of the 60-day quiet-spurt test
(51 quiet nights: carrying lost more). Small sample in one rising week; not adopted, for the user to decide.

### Support / resistance check before buying (user, 2 Nov 2026)

Levels: previous day high/low/close, classic pivots (P, R1, S1, R2, S2), 20-day high/low, today's high/low so
far. For each backtest trade: distance to the nearest level AHEAD (in the trade's way, a "hurdle") and BEHIND
(support under a CALL / resistance over a PUT), in % of the stock price.

Quiet spurt (171 trades, 10% target): a hurdle close ahead did not hurt - within 0.3%: 121 trades, 68% hit,
+2.72%/trade; 0.3-0.6%: 36 trades, 75%, +3.05%; more than 0.6% of open space: 14 trades, worse (-0.38% to
-4.14%). Most trades have some level within 0.3% (12 levels per stock), so "a level in the way" is the
normal case and not a reason to skip.

Movers reversal (130 trades, -Rs 36,390): buying right AT a level (within 0.3% of support for a CALL, of
resistance for a PUT) was the only profitable group: 20 trades, 95% hit, +0.99%/trade, +Rs 5,931, positive
in both halves. But at 0.4% it is already flat (29 trades, -Rs 105): a narrow peak on 20 trades, which fails
the quantforge-ai gates (>= 100 trades, no single-parameter peak). Not adopted; worth watching live.

### Which spurts become big movers; bigger targets for them (user, 3 Nov 2026)

60 days, 341 first-of-day spurts (no hit-chance filter) - after the signal: 98% moved further their way at
some point (median +0.76% more), 68% closed the day their way, only 7% ended among the day's top 5
gainers/losers. By group (net, 10% / 15% / 20% target):
- Volume 2x+: +18k / +55k / +59k; 3x+: losing (34 trades). Volume size alone is not a good marker.
- Spurts by 10:15: +74k / +1.12 lakh / +1.26 lakh; after 10:15: -16k / -40k / -22k.
- Price and volume still building 15 minutes later ("confirmed", 58 trades): +3.7% / +4.8% / +6.7% per trade,
  but known only 15 minutes later; entering at confirmation loses (-0.8%/trade): the move is in the first minutes.

With the live hit-chance filter (how the desk trades), 171 trades:

| Target rule | Net | 1st half | 2nd half |
|---|---|---|---|
| 10% always (until 3 Nov) | +Rs 1,26,586 | +51.2k | +75.4k |
| 15% for spurts by 10:15 when reachable, else 10% | +Rs 1,56,505 | +64.4k | +92.1k |
| **15% whenever reachable, else 10%** | **+Rs 1,69,440** | +70.2k | +99.3k |
| 12.5% whenever reachable, else 10% | +Rs 1,44,356 | +69.4k | +74.9k |

Every cut-off time (10:05-15:00) and 12.5%/15% beat 10%-only in both halves: a smooth, robust improvement
with the same trades. Adopted 3 Nov (user: keep whatever makes more profit).

### Pre-open gap recovery (user's idea, 4 Nov 2026) - adopted for the new pre-open team

60 days x 76 stocks (5-min data to 3 Nov). Stocks that open 1.5%+ away from yesterday's close; at 09:30:
"recovery" = back 1%+ from the early extreme (09:15-09:30) AND past the opening price -> buy the recovery's
direction; "continuation" = still 0.5%+ beyond the open the gap's way -> buy the gap's direction.

| Setup | Target | Trades | Hit % | Avg | Net | Halves |
|---|---|---|---|---|---|---|
| **Recovery** | 15% if reachable, else 10% | 35 | - | - | **+Rs 33,588** | +10.3k / +23.3k |
| Recovery | 10% | 35 | 74 | +1.59% | +Rs 16,644 | 0 / +16.6k |
| Recovery | 15% | 19 | 63 | +5.40% | +Rs 30,794 | +8.2k / +22.6k |
| Weak recovery (0.5% bounce only) | 10% | 97 | 66 | -0.18% | -Rs 5,162 | |
| Continuation (gap holds) | 10% | 65 | 54 | -5.34% | -Rs 1,04,117 | -47.8k / -56.3k |

A real recovery (1%+ and past the open) is the key; following a gap that holds loses heavily. Gaps under one
day's average range (ATR) recovered best (+Rs 21,977 on 25 at 10%). Small sample (35 trades): live paper test.

### Research notes (4 Nov 2026, web search)
- Abnormal volume predicts returns over days to weeks, mostly upward (Lee, Kim & Kim 2016; Zheng 2007; Helsinki
  and Thai studies): supports the quiet spurt and carrying spurt trades overnight.
- Intraday momentum: the first half-hour's return predicts the last half-hour's (Gao, Han, Li, Zhou, JFE 2018;
  12 of 16 markets), stronger on high-volume days; one replication found it weak.
- News: prices adjust within 15-90 minutes, negative news more strongly (Oslo, Paris studies; Indian intraday
  study: extreme moves reverse within minutes) -> the news team must act in minutes and not mid-announcement.
- Opening gaps: no academic NSE study found; practitioner data says small gaps fill and big gaps (1+ ATR) follow.
- Open-interest build-ups: only broker explainers, no tested evidence -> recorded on spurt trades (oi_type), scored.

### Quiet spurt: do volume or technical-strength filters help? (user's question, 4 Nov 2026)

`backtest_spurt_filters.py`; 175 first-signal trades, 76 stocks, 60 days, 15%-else-10% target, no stop-loss. Live the
spurt team does NOT check any chart strength (only volume 1.5x+, a 0.2-0.5% move, candle/VWAP side, news, OI note).
All trades +Rs 1,56,206 (halves +1.20L / +0.36L). Volume 2x+: 72 trades +74.6k (fewer trades, less money, avg +3.5%
vs +3.0%); 2.5x+: 34, +43k, avg +4.2%; 3x+: 21, +35k, avg +5.6% (better per trade, less money; both halves positive).
Stretched/overbought set (5-min RSI>70, prev day >2% or 5-day run >4% in the trade's direction, >5% above EMA20, or a 20-day
breakout): 35 trades, +1.5k only (halves -4.1k / +5.6k); the other 140 trades +154.7k. Against-the-trend entries did
better (+3.65% avg) than with-trend (+1.97%); daily RSI in the trade's direction 55-65 lost (-11.5k, 35 trades).
Verdict: no filter adds money in both halves, so none is switched on; a volume floor lowers total profit.
Live (-Rs 7k on 8 trades) is far below this backtest: check live fills/spreads before trusting the backtest.

### Revived pure spurt engine (user's design, 4 Nov 2026): `backtest_spurt_revival.py`

Stage by stage, 60 days x 76 stocks, 15%-else-10% target, no stop-loss (halves split by date):

| Stage | Trades | Hit % | Avg | Net | Half 1 / Half 2 |
|---|---|---|---|---|---|
| 0 old rule (1.5x, to 15:15) | 175 | 63 | +2.98% | +Rs 1,56,206 | +83.6k / +72.6k |
| 1 + volume 1.8x | 103 | 65 | +3.85% | +Rs 1,18,616 | +59.7k / +58.9k |
| 2 + window 09:30-11:30 | 93 | 62 | +3.25% | +Rs 90,388 | +53.4k / +37.0k |
| 3 + calm pre-open (gap <= 1%, proxy: opening bar) | 83 | 64 | +3.91% | +Rs 97,104 | +53.3k / +43.8k |
| 4 + multi-week filter (REVIVED, testable part) | 83 | 64 | +3.91% | +Rs 97,104 | +53.3k / +43.8k |

The multi-week veto never fired in 60 days (needs a 8%+ run into a 20-day high). Not backtestable (no history): zero-news
quarantine, F&O OI confirmation, delta 0.50-0.65 / spread <= 1%. Revived rules: better per trade (+3.9% vs +3.0%), profitable in
both halves, but less total money (fewer trades). Switched on at the user's request. The "dynamic breakeven lock" in the user's
chart (a stop once +8-10%) was NOT built: it is a stop-loss, against the no-stop-loss rule.

### Spurt redesign: trade WITH the market (user's question, 7 Nov 2026): `backtest_spurt_v2.py`

Why the live spurt team lost: the plain rule has been flat in the backtest too in the last two weeks (+Rs 637 and -Rs 4,821 per week), while it
earned in Aug-Oct. Live 13 closed trades since 30 Oct: spurts WITH the Nifty's move that day 8 trades +Rs 6,103; against it 5 trades -Rs 16,948.
60 days x 76 stocks (data to 6 Nov), window 09:30-11:30, 15%-else-10% target, no stop-loss; control = same entries the opposite way (all lose).

| Rule | Trades | Hit % | Avg | Net | Half 1 / Half 2 |
|---|---|---|---|---|---|
| Plain rule (1.5x, 0.2-0.5% move) | 165 | 62 | +2.5% | +Rs 1,25,259 | +75k / +50k |
| + with the Nifty | 106 | 67 | +4.2% | +Rs 1,33,936 | +58k / +76k |
| + against the Nifty | 97 | 54 | -0.7% | -Rs 20,635 | +28k / -48k |
| + with the Nifty & volume 1.8x | 59 | 71 | +6.5% | +Rs 1,14,120 | +56k / +58k |
| + with the Nifty & volume 2.5x | 37 | 78 | +6.9% | +Rs 75,954 | +30k / +46k |
| Revived rules (1.8x, window, calm gap) | 87 | 62 | +3.5% | +Rs 91,179 | +63k / +28k |
| **Revived + with the Nifty (adopted)** | 53 | 74 | +7.4% | **+Rs 1,17,463** | +60k / +58k |

Waiting for a breakout first (past the first-30-minute range, yesterday's high/low, the day's high/low, opening-range style) removed the edge
(+Rs 5k to +40k; the move is already used up). Stock stronger than the Nifty by 0.2%: ~0. Against-the-market and 'last-bar burst' lost.
Revived + with the Nifty is positive in 10 of 12 weeks (revived alone: 3 negative weeks in the last 4). Caveats: 60 days, one regime, many
variants tried (the control and both halves guard against luck); news, OI and delta/spread gates cannot be backtested.

Direction split by the Nifty's day (same entries, 60 days; flat = |Nifty| < 0.15%): Nifty up: CALLs +Rs 44,663 (51 trades) vs PUTs against +Rs 1,422 (45);
Nifty down: PUTs +Rs 22,999 (20) vs CALLs against -Rs 39,303 (27); flat market: both directions +Rs 66,428 (57; CALLs +36,008, PUTs +31,761, both
halves positive). Rule adopted: up -> CALLs only, down -> PUTs only, flat -> both (config spurt.pure.market_flat_band_pct).

### Spurt and support / resistance (user's question, 7 Nov 2026) - on top of the market rule (120 trades, +Rs 1,26,057, halves +67k / +59k)
Levels = swing highs/lows of the last 60 sessions. Room ahead >= 1%: 100 trades +Rs 1,10,102; >= 2%: 81, +Rs 1,02,793; >= 3%: 68, +Rs 68,482 (less
money, avg +3.7 / +4.2 / +3.4% vs +3.5%). Right at the wall (< 1% ahead): 26 trades +Rs 31,905 (still profitable). Breaking the 20-day high/low today:
27 trades, 74% hit, +4.4% avg, +Rs 35,459 (both halves positive, but little money). Room ahead >= 1% with the level behind within 2%: 44 trades, 77% hit,
+6.8% avg, +Rs 89,618 (both halves positive), but its opposite-direction control also earned (+Rs 17k), so part of it is volatility, not direction.
No level filter adds money, so none is a gate; the level note (room ahead, level behind, 20-day breakout) is recorded on every spurt trade (observe only).
