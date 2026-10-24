---
name: candlestick-patterns
description: Read Japanese candlestick patterns (hammer, engulfing, morning/evening star, harami, doji, three soldiers/crows...) on a stock's 5-minute or daily chart, and judge how much they are worth. Use on a SIGNAL to describe the last candles, when the user asks what the candles say, or to re-test whether patterns predict moves on our data.
---

# Candlestick Patterns

The agent is `agents/candles.py` (19 patterns, pandas only). Reversal patterns count only after a
move into them (a hammer needs a fall before it).

## On a SIGNAL
1. The watcher already adds a "Candles: ..." note when a pattern formed on the last 3 candles.
2. For a PUT on a fading gainer, bearish patterns (shooting star, bearish engulfing, evening star,
   dark cloud cover, three black crows) support it; for a CALL on a bouncing loser, bullish ones.
3. Treat it as colour, not a reason: say what formed, and never turn a SKIP into a TRADE on candles alone.

## What it is worth (keep this honest)
- Our test (22 Oct 2026): 60 days, 76 F&O stocks, 263,000 five-minute candles. No pattern called
  the next 30 minutes better than a random candle; the best (dark cloud cover, bearish harami)
  were within noise, and bullish patterns were slightly worse than random in a falling period.
- Published studies agree: Duvinage, Mazza & Petitjean (83 rules, Dow stocks, 5-min bars) found no
  exploitable edge after luck, risk and costs; Fock, Klein & Zwergel (DAX/Bund) found results no
  better than random trades.
- So `candles.points` in config.yaml stays 0 (observe mode). Re-test with
  `python -m agents.candles test` every month or so; give it points only if a pattern beats the
  base rate by a clear margin over thousands of cases, and only with the user's OK.

## Commands
    python -m agents.candles test [intraday.pkl]   # predictive test on 60 days of 5-min data
