# Trading Desk: Complete Guide

Everything about this project in one place: what each agent does, how they are wired, the two
competing teams, the skills, the daily routine, and how to set it up again from this archive.

**Paper trading only. Nothing here places real orders.**

---

## 1. The user's rules (never change without the user's OK)

- Intraday only. Every trade is closed by 15:20 IST at the latest.
- Buy options only: a PUT on a top gainer that is fading, a CALL on a top loser that is bouncing
  (news team: CALL when the forecast is up, PUT when it is down).
- Target: at least 1% net profit per trade after all charges (brokerage, STT, exchange fees,
  GST, stamp duty, the bid-ask gap).
- **No stop-loss.** Exits are the target or the 15:20 square-off only.
- Capital: ₹30,000 per team, one trade at a time per team; setups found while busy are only recorded.

## 2. The two teams (from 21 Oct 2026)

| | Movers team | News team |
|---|---|---|
| Idea | Top gainers/losers snap back intraday | Results and news move stocks |
| Looks at | Price, chart, option chain, sector moves | NSE filings, results PDFs, concalls, news (ET, Mint, BS, CNBC-TV18, Google News), forecasts, priced-in check, valuation |
| Enters when | Chart shows a gainer fading / loser bouncing, score high enough, 1% net target reachable | A strong results/forecast idea (confidence >= 60 after the priced-in cut) and the stock already moving 0.5-4% that way today |
| Strategy tag | `reversal` | `results`, `intel` |
| Capital | ₹30,000 | ₹30,000 |

The evening review (`review.py`) starts with a scoreboard: chances found, trades, hit rate,
net ₹ and return on capital per team. Pick a winner only after 30+ trades per team.

## 3. The agents (21 + Claude as supervisor)

### Information track (every 30 seconds, all day, in its own thread)
| Agent | File | Job |
|---|---|---|
| NSE Announcements | `agents/announcements.py` | Live NSE filings for our 76 F&O stocks; reads results PDFs (revenue, profit, QoQ/YoY) and scores them strong/good/mixed/weak |
| Concalls | `agents/concalls.py` | Conference-call dates and transcripts |
| News feed | `agents/newsfeed.py` | RSS: Economic Times, Mint, Business Standard, CNBC-TV18, Google News (India markets, global macro, India macro, commodities) |
| Intelligence log | `agents/intel.py` | One shared log (`journal/intel/<date>.jsonl`); links headlines to stocks/sectors, reads tone with finance word lists (negation and hedging aware) |
| Data Analyzer | `agents/analyzer.py` | Forecast per stock (up/down, confidence) + market mood; newer and bigger items weigh more |
| Valuation | `agents/valuation.py` | P/E (P/B for banks/NBFCs) vs sector-peer median, from Yahoo once a day (`journal/valuations/`) |
| Expectations | `agents/expectations.py` | "Already priced in?": 4-week run-up vs Nifty, pre-event hype, price vs analyst target, valuation; post-results "sell the news" / relief reaction |

### Trading track (scan about every 2 minutes, exits every 15 seconds)
| Agent | File | Job |
|---|---|---|
| Holidays | `agents/holidays.py` | NSE trading holidays from NSE's own calendar |
| Regime | `agents/regime.py` | Nifty trend + India VIX: trade gainers, losers, both, or nothing today |
| Scanner | `agents/scanner.py` | Top gainers/losers among the F&O stocks |
| Chart Reader | `agents/chart_reader.py` | 5-min candles: VWAP, EMA 9/21, RSI, wicks, lower highs, volume -> score 0-100 |
| Options | `agents/options.py`, `agents/indmoney.py` | Picks the contract (ITM1 strike), live bid/ask, lot size |
| Forecast | `agents/forecast.py` | Likely reversal level (VWAP or 38% retracement) |
| Risk | `agents/risk.py`, `agents/costs.py` | Lots that fit, all charges, target premium for 1% net, chance of reaching it |
| News & Events | `agents/news.py` | Results day, fresh headlines, sudden volume (news team's vote) |
| Macro | `agents/macro.py`, `agents/sectors.py` | Sector index and rupee moves |
| Commodities | `agents/commodities.py` | MCX crude, gas, gold, silver, copper, aluminium, zinc, nickel; shock alerts |
| Crowd Psychology | `agents/psychology.py` | Futures OI build-up, 52-week extremes, circuits (observe mode) |
| Decision | `agents/decision.py` | Adds up chart score and votes -> TRADE / SKIP |
| Journal | `agents/journal.py`, `journal/paper_trades.csv` | Records every paper trade |

### Daily
| Agent | File | Job |
|---|---|---|
| Day mode | `agents/daymode.py` | Morning brief sets normal / careful / no_trade and stocks to avoid (`journal/day_mode.json`) |
| Evening review | `review.py` | Scoreboard, breakdowns, and whether there are enough trades to propose a strategy change |

### Wiring
```
INFORMATION TRACK (every 30 s)
  NSE filings + Concalls + News feed -> Intelligence log -> Data Analyzer -> forecasts
  Valuation -> Expectations ("priced in?") -> trade ideas for the NEWS team
  Alerts to Claude: RESULT, NEWS, FORECAST, COMMODITY

TRADING TRACK (every ~2 min)
  Holidays -> Regime -> Scanner -> Chart Reader -> Options -> Forecast -> Risk
     -> Macro + Crowd Psychology (observe) -> Decision -> MOVERS team paper trade -> SIGNAL
  News team: idea + price confirms (0.5-4% move its way) -> Options -> Risk -> paper trade -> SIGNAL
  Exits (every 15 s): target reached, or square-off at 15:20. No stop-loss.

DAY
  Morning brief -> watcher all day -> evening review -> proposals (applied only with the user's OK)
```

## 4. Event lines the watcher prints (`watcher.py`)

| Line | Meaning |
|---|---|
| `SIGNAL` | A team opened a paper trade (`team`: movers or news). Claude checks it and says TRADE/SKIP |
| `EXIT` | A trade closed at the target or square-off |
| `RESULT` | A company filed results; figures already read, priced-in check done |
| `NEWS` | A major NSE filing (regulatory action, etc.) |
| `FORECAST` | The Data Analyzer's outlook for a stock turned strong |
| `COMMODITY` | A commodity moved 3%+ today |
| `ERROR` / `STATUS` | Problems; start/stop |

Claude is only woken by these lines, so Claude credits are spent only when something happens.

## 5. Data sources and limits

- **INDmoney MCP** (`https://mcp.indmoney.com/mcp`): live prices, candles, option chains, news,
  analyst targets. Login: `python -m agents.indmoney login`, then
  `python -m agents.indmoney finish "<the localhost:8765/callback?code=... address>"`.
  Token stays at `~/.config/indmoney/token.json` (never shared, not in this archive).
  **500 calls/hour per account**; the watcher paces itself at 450/hour (one call every 8 s).
- **NSE public APIs**: corporate announcements, event calendar, holiday master.
- **Yahoo Finance**: valuations (P/E, P/B), USD/INR, and history for backtests.
- **RSS feeds**: ET, Mint, Business Standard, CNBC-TV18, Google News.

## 6. Skills (in `.claude/skills/`)

| Skill | Use |
|---|---|
| `trading-desk` (own) | Runs the desk: morning brief, start, what to do on each event line, evening review |
| `quantforge-ai` | Validation gates: is a result skill or luck? (`scripts/metrics.py`). Its stop-loss advice does not apply |
| `earnings-preview` (Anthropic) | Before results: the metrics that will move the stock, bull/bear case |
| `earnings-analysis` (Anthropic) | After results: beat/miss checklist |
| `nlp-earnings-sentiment` | Concall tone and hedging |
| `market-news-analyst` | Big market-moving news and its impact |
| `backtest`, `optimize`, `quick-stats`, `strategy-compare`, `vectorbt-expert`, `setup` | VectorBT backtesting toolkit |

Licences and review notes: `.claude/skills/THIRD_PARTY.md`.

## 7. Daily routine

1. **~09:00 morning brief**: holiday check; overnight NSE filings
   (`python -m agents.announcements overnight`); `python -m agents.valuation`; companies reporting
   today (`python -m agents.expectations SYMBOL`, earnings-preview); `python -m agents.analyzer`;
   global markets and commodities; write `journal/day_mode.json`.
2. **09:15-15:30**: `python3 -u watcher.py` runs both teams. Entries 09:15-15:15, square-off 15:20.
3. **After 15:30**: `python review.py` -> `journal/reviews/<date>.md`; commit `journal/`.
4. Strategy changes: only after 30+ trades, tested in a backtest (`backtest_reversal.py`) and on
   paper, and only with the user's approval; logged in `journal/strategy_changes.md`.

## 8. What we learned so far (backtest, `journal/backtest_summary.md`)

- About 90% of reversal trades reach the target, but without a stop-loss the few misses are big
  enough to wipe out the gains.
- Losers-only (CALLs on bouncing losers) was positive (+0.49% per trade); gainers were weaker.
- The Macro agent helped (-0.35% -> +0.10% per trade). Forecast filters and time exits hurt.
- ITM1 strikes beat ATM.
- QuantForge verdict: **not ready for real money** until paper trades confirm it.

## 9. Set it up again

```
pip install -r requirements.txt
python -m agents.indmoney login          # open the link, approve, copy the final address
python -m agents.indmoney finish "<address>"
python -m pytest -q                      # all tests should pass
python3 -u watcher.py                    # during market hours
streamlit run App.py                     # optional phone app (Yahoo data, estimated premiums)
```
Settings: `config.yaml` (capital, teams, targets, timings, call budget, agent weights, universe).
For Claude Code: open the folder and say "start the trading desk".
