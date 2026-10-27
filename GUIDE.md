# Trading Desk: Complete Guide (27 Oct 2026)

Everything about this project in one place: what each agent does, how the agents are wired,
the two competing teams, the daily routine, the files, the settings, what the tests and
backtests found, and how to set it up again.

**Paper trading only. Nothing here places real orders.** INDmoney access is read-only.

---

## 1. The user's rules (never changed without the user's OK)

| Rule | Meaning |
|---|---|
| Intraday only | Every trade is closed by 15:20 IST at the latest |
| Buy options only | Movers team: PUT on a top gainer that is fading, CALL on a top loser that is bouncing. News team: CALL when the news points up, PUT when it points down |
| Target >= 1% net | Exit price must give at least 1% profit after ALL charges (brokerage, STT, exchange fees, GST, stamp duty, SEBI fee) and the bid-ask gap |
| **No stop-loss** | A trade exits only at its target or at the 15:20 square-off |
| Capital | ₹30,000 paper money per team; one trade at a time per team |

---

## 2. The big picture

```
                          INFORMATION TRACK (always on, own threads)
  NSE filings (every 10 s) ─┐
  Results PDFs + OCR ───────┤
  Concalls ─────────────────┤──> Intelligence log ──> Data Analyzer ──> forecast per stock
  News feeds (every 30 s) ──┤      (journal/intel)        │                + market mood
  Policy rulebook ──────────┘                             │
  NSE pre-open + volume spurts (free NSE pages)           ├──> Expectations ("already priced in?")
  Valuation (P/E, P/B vs peers)  ─────────────────────────┤    Results Reaction analyst (3 yrs history)
                                                          v
                                                   NEWS-TEAM IDEAS
                                                          │
       ┌──────────────────────── TRADING TRACK (INDmoney, paced 8 s per call) ──────────────────┐
       │                                                                                         │
       │  NEWS TEAM (runs first)                       MOVERS TEAM                               │
       │  idea + price confirms + chart agrees          top gainers/losers -> chart reversal     │
       │  (or results-gap rule / early entry)           + guards (news, shock, regime)           │
       │        │                                              │                                 │
       │        └──────────── Options agent (contract) -> Risk agent (size, target) ─────────────┤
       │                                       │                                                 │
       │                               paper trade + SIGNAL line                                 │
       │                                       │                                                 │
       │                 Exit checker every 15 s: target reached? else square-off 15:20          │
       └─────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
              Claude (supervisor): checks each SIGNAL, gives TRADE/SKIP, reads RESULTs,
              morning brief, evening review, fixes; changes rules only with the user's OK
```

---

## 3. A trading day, minute by minute (IST)

| Time | What happens | Who |
|---|---|---|
| 08:40 | **Morning brief** (scheduled): holiday check, overnight NSE filings and results, expected Nifty open from US stocks and crude, market picture, Data Analyzer, mover forecast, results calendar; writes `journal/day_mode.json` (normal / careful / no_trade + stocks to avoid); starts the watcher | Claude + agents |
| 09:00-09:08 | NSE pre-open order matching; final indicative opening prices at ~09:08 | NSE |
| 09:08 | Watcher saves the pre-open snapshot (`journal/intel/preopen-<date>.json`) | Pre-open reader |
| 09:10 | **Pre-open mover forecast** message to the user (scheduled): likely top movers, their pre-open gaps and how their direction will be decided | Mover Forecast |
| 09:15 | Market opens; both teams may trade (entries 09:15-15:15) | Both teams |
| 09:30-10:30 | Results-gap rule active (news team) | Gap follower |
| every 10 s | NSE filings checked; results PDFs read at once (up to 20 at a time) | Announcements |
| every 30 s | News feeds, valuations, Data Analyzer, pre-open/volume spurts (spurts every 5 min) | Information agents |
| every ~2-4 min | One trading cycle: exits, news team, movers scan | Trading track |
| every 15 s | Open trades re-priced; exit at target | Exit checker |
| 12:40 | Health check (scheduled): watcher running? restart if needed | Claude |
| 15:15 | Last entry | |
| 15:20 | Square-off: every open trade closed at the bid | Exit checker |
| 15:30 | Market closes; watcher stops | |
| 15:40 | **Evening review** (scheduled): scoreboard, trades, Claude's calls vs rules, the day's highlights, mover forecast vs actual movers; commits `journal/` | Claude + review.py |

The watcher is a background process limited to 2 hours per run by the cloud environment;
it is restarted straight away (standing permission). Open trades are kept in the trade log,
so a restart loses nothing.

---

## 4. The two teams

| | Movers team (technical) | News team |
|---|---|---|
| Idea | Today's top gainers/losers snap back intraday | Results, filings, news and policy move stocks |
| Trades | PUT on a fading gainer, CALL on a bouncing loser | CALL for "up", PUT for "down" |
| Strategy tag | `reversal` | `results`, `intel`, `results-gap` |
| Paper capital | ₹30,000 | ₹30,000 (topped up by ₹13,304 on 26 Oct; not counted as profit) |
| Per trade | All free money (sized by lots) | All free money (user, 26 Oct) |

The evening review keeps a scoreboard. The user picks a winner only after 30+ trades per team.

### 4.1 Movers team, step by step (`watcher.scan`)

1. **Day mode** (`agents/daymode.py`): `no_trade` stops the team; `careful` needs a stronger chart (+10 points); stocks on today's `avoid` list are skipped.
2. **Market Regime** (`agents/regime.py`): Nifty trend and India VIX decide which sides are allowed (in a downtrend, bounce trades on losers are off; very high VIX = no trading).
3. **Shock-day guard** (`agents/shock.py`): Nifty 1.5%+ with confirmation (80% of sectors the same way, VIX jump 12%+, or 3+ big macro headlines): rally = no PUTs on gainers, crash = no CALLs on losers; 2.5%+ = stand aside. Sends a SHOCK line.
4. **Scanner** (`agents/scanner.py`): top 5 gainers and top 5 losers among the 76 F&O stocks (moved 2%+, enough turnover).
5. **Chart Reader** (`agents/chart_reader.py`): 5-minute candles, score 0-100 for "the move is reversing": VWAP, 9/21 EMA cross, RSI cooling from extreme, day high/low not retested, rejection wicks, heavier volume on the reversing side, stretched on the daily chart; minus points for still-making-new-highs (-35), strong trend, aggressive volume continuation (-15). Needs 60 (70 on careful days).
6. **News Guard** (`agents/news_guard.py`): skips the stock if it has results today (calendar or filing), a regulatory filing, a policy hit against the trade, or strong real news against the trade. Headlines that only describe the move are ignored. Logged in `journal/news_guard.csv`.
7. **Options agent** (`agents/options.py`, `agents/indmoney.py`): live option chain; ITM1 strike; contract choice (section 6).
8. **Forecast agent** (`agents/forecast.py`): likely reversal level (VWAP or 38% retracement) and the option price there (information only; filtering on it made the backtest worse).
9. **Risk agent** (`agents/risk.py`): lots that fit the money, all charges, the exit price for 1% net, the chance of reaching it before square-off; veto power.
10. **Macro** (`agents/macro.py`): sector index and rupee moves (is the stock just moving with its sector?).
11. **Crowd Psychology** (`agents/psychology.py`, observe mode): futures OI build-up type (long build-up, short covering, ...), 52-week extremes, circuits. **Valuation** (observe), **Candlestick Patterns** (observe, `agents/candles.py`).
12. **Decision agent** (`agents/decision.py`): chart score + votes -> TRADE / WATCH / SKIP.
13. TRADE -> paper trade at the live ask, SIGNAL line to Claude. While a movers trade is open, new setups are only recorded (`journal/held_setups.csv`).

### 4.2 News team, step by step (`watcher.news_team`)

Ideas come from three places:
- **Data Analyzer forecasts**: a stock's own news is loud and confirmed (2+ independent sources or one major item such as results). Confidence 0-100.
- **Results readings**: the Announcements agent reads the results PDF (text layer or OCR), the Sector Results analyst judges it for the sector, the Results Reaction analyst gives the expected move from the stock's own 3-year history. Because figures alone call the direction only 49.6% of the time, results ideas need the price to confirm.
- **Results-gap rule** (`agents/gapfollow.py`, 09:30-10:30): a stock with results since the last close that opened 1%+ away from Nifty and kept going in the first 15 minutes becomes an idea in the gap's direction (confidence 75), outranking headline readings that day.

Each idea is checked in this order:
1. **Priced in?** (`agents/expectations.py`): 4-week run-up vs Nifty, pre-event hype, price vs analyst target, valuation vs peers. A largely priced-in story loses 25 confidence. Ideas whose check failed are not traded.
2. **Confidence** 60+ and the idea not older than 120 minutes.
3. **Price confirms**: the stock already moves 0.5-4% the news's way today (results-gap ideas up to 8%). **Early entry** (`agents/momentum.early_signals`): from a 0.2% move when the latest 5-minute candle has 1.5x its usual volume for that time of day (closing the news's way) and the NSE order book holds 1.5x more buyers than sellers (reverse for down).
4. **Trend Checker** (`agents/momentum.py`): the chart must back the news, score 60+ (VWAP side, EMAs, RSI 55-75, higher lows/lower highs, volume, near the day's extreme, daily chart; minus points for chasing a stretched move).
5. **Market Context** (`agents/market.py`): no CALL into a market falling 0.8%+ on bad news, no PUT into such a rally.
6. **Options + Risk**: option at least ₹5 (cheap options in huge quantities caused the two big losses); contract choice in section 6; all free money may be used; if one lot costs more than the money, no trade.
7. Paper trade + SIGNAL line. Skipped confirmed ideas are logged with the reason (`journal/intel/news_skips-<date>.csv`).

A new news idea makes the movers scan stop between stocks, so the news team acts within a
few INDmoney calls rather than after a full scan (calls are paced ~8 s apart).

---

## 5. Every agent

### Information (collect)
| Agent | File | Job |
|---|---|---|
| NSE Announcements | `agents/announcements.py` | NSE corporate filings every 10 s (own thread); classifies them (results, board meetings, ratings, orders, deals, regulatory, guidance); reads results PDFs: text layer, else Tesseract OCR (pages in parallel, one OCR per CPU core); revenue/profit with QoQ/YoY, sanity checks against OCR errors |
| Concalls | `agents/concalls.py` | Earnings-call dates and transcripts |
| News feed | `agents/newsfeed.py` | RSS: Economic Times, Mint, Business Standard, CNBC-TV18, Google News (India markets, India macro, global macro, commodities, regulators & policy), fetched in parallel |
| Intelligence log | `agents/intel.py` | One shared log (`journal/intel/<date>.jsonl`); links headlines to our stocks/sectors (filters look-alike names, "ITC" = input tax credit in GST news); finance word-list tone with negation/hedging; round-ups, earnings previews and market-cap round-ups carry no stock tone |
| Policy Impact | `agents/policy.py` (+ `policy-impact` skill) | Rulebook: RBI rates/CRR/risk weights, SEBI F&O, IRDAI commission caps, telecom tariffs, GST, duties, windfall tax, PLI, defence, visas, pharma tariffs...; who is hit or helped and how much; reversed, delayed or "talk" (may/might/expect/question) headlines count less; POLICY lines |
| Commodities | `agents/commodities.py` | MCX crude, gas, gold, silver, copper, aluminium, zinc, nickel; 3%+ moves and the stocks they hit (COMMODITY lines) |
| NSE pre-open + volume spurts | `agents/preopen.py` | Pre-open indicative open price, gap, buy/sell quantities (saved daily at 09:08); stocks trading 3x+ their 1-week volume (every 5 min). Free NSE pages, no INDmoney calls |
| F&O Activity | `agents/activity.py` | Every 2 min from NSE's free OI-spurts page (all F&O stocks in one call): open interest change + price move = long/short build-up. A build-up the news's way lets the news team enter early (from 0.2%) and adds 15 points to the Trend Checker. Saved to `journal/intel/activity-<date>.jsonl`; untested on history, judged after a few weeks. (NSE's volume-spurts page lists only the top 25 market-wide and never showed an F&O stock on 27 Oct) |
| Valuation | `agents/valuation.py` | P/E (P/B for banks and NBFCs) vs the sector-peer median, daily snapshot `journal/valuations/` |
| Holidays | `agents/holidays.py` | NSE holiday calendar; nothing trades on closed days |

### Analysis (understand)
| Agent | File | Job |
|---|---|---|
| Data Analyzer | `agents/analyzer.py` | Forecast per stock: tone x importance of its own items (capped), plus sector and market mood; age counted in market hours (news half-life 3 h, filings/policy 6.5 h); one policy event counts once per stock however many articles cover it; market mood |
| Expectations | `agents/expectations.py` | "Already priced in?" (see 4.2) on every RESULT and FORECAST |
| Sector Results | `agents/sector_results.py` | Seasonal sectors read year-on-year (cement, autos, power, retail), IT and telecom quarter-on-quarter; sector KPIs (NIM and bad loans for banks, constant-currency growth and deal wins for IT, EBITDA/tonne for steel and cement, ARPU for telecom) |
| Results Reaction analyst | `agents/reaction.py` | 3 years of each stock's results reactions (`journal/results_history/`, model `journal/reaction_model.json`): expected gap and close with a range, chance of rising, similar past quarters; also the expected Nifty open from US stocks and Brent |
| Market Context | `agents/market.py` | Nifty's move and why, by theme (geopolitics, policy, domestic economy, global markets, commodities, flows) |
| Mover Forecast | `agents/mover_forecast.py` | Morning list of likely top gainers/losers: results stocks (size from their past results days, direction set by the open), pre-open gaps without results (fade candidates), strong news views. 26 Oct: 6 of the 8 biggest movers were on it |

### Trading (decide and act)
| Agent | File | Job |
|---|---|---|
| Regime | `agents/regime.py` | Nifty trend + India VIX -> which sides to trade, threshold adjustment |
| Scanner | `agents/scanner.py` | Top gainers/losers, stock profile (ATR, distance from the 20-day average, 1-week move, turnover) |
| Chart Reader | `agents/chart_reader.py` | Reversal score (4.1 step 5) |
| Trend Checker | `agents/momentum.py` | Trend score for news trades; early-entry check (volume + order book) |
| Results-gap follower | `agents/gapfollow.py` | 4.2 |
| News Guard | `agents/news_guard.py` | Movers team's safety brake (4.1 step 6) |
| Shock guard | `agents/shock.py` | Market-wide shock days (4.1 step 3) |
| News & Events | `agents/news.py` | Results calendar (NSE event calendar, today included), INDmoney headlines, sudden-volume check |
| Macro / Sectors | `agents/macro.py`, `agents/sectors.py` | Sector index, crude and rupee links |
| Crowd Psychology | `agents/psychology.py` | Futures OI build-up type, 52-week extremes, circuits (observe) |
| Candlestick Patterns | `agents/candles.py` | 19 patterns on the last 3 candles (observe: no edge on 263,000 candles) |
| Options | `agents/options.py`, `agents/indmoney.py` | Live chain, contract choice, Black-Scholes and Greeks |
| Forecast | `agents/forecast.py` | Reversal level |
| Risk + Costs | `agents/risk.py`, `agents/costs.py` | Sizing, all charges, target price, chance of target, veto |
| Decision | `agents/decision.py` | TRADE / WATCH / SKIP |
| Journal | `journal/paper_trades.csv`, `agents/journal.py` | Every paper trade |
| AI Analyst (app) | `agents/ai_analyst.py`, `agents/chart_image.py` | Optional chart-image check in the phone app |

### Research (tested, not trading)
| Tool | File | Finding |
|---|---|---|
| Reversal backtest | `backtest_reversal.py` | 60 days: 83% reach the 1% target, average -1.55% per trade (misses -15%, worst -86%) |
| Order-flow detectors | `agents/orderflow.py`, `backtest_orderflow.py` | Squeeze, spring/upthrust, VWAP reclaim, CVD: none beat its mirror image; all lose |
| Candle patterns | `agents/candles.py test` | No pattern beats chance over 30 minutes |

---

## 6. Contract choice and exits

- **Strike**: ITM1 (one strike in the money): smaller worst loss in the backtest.
- **Expiry**: this month's contract, except:
  - on expiry day and the day before: always next month's;
  - in expiry week (7 days): next month's when this month's option is under ₹5 or its bid-ask gap is over 2%.
- **Minimum premium** ₹5 (news team).
- **Entry** at the live ask; **target** = the bid that gives 1% net after all charges; **exit** at the target or the 15:20 square-off (bid). No stop-loss.

---

## 7. Lines the watcher prints (and which ones wake Claude)

| Line | Meaning | Wakes Claude? |
|---|---|---|
| `SIGNAL` | A team opened a paper trade | Yes: TRADE/SKIP verdict in `journal/claude_verdicts.csv` |
| `EXIT` | A trade closed (target or square-off) | Yes |
| `RESULT` | A company filed results (figures, sector read, priced-in, expected reaction, seconds since NSE published it) | Yes |
| `SHOCK` | Market-wide shock day | Yes |
| `ERROR` | Login lost, call limit, stale data | Only serious ones |
| `STATUS` | Start / market closed | Only market closed |
| `FORECAST`, `POLICY`, `COMMODITY`, `NEWS` | Strong views and alerts | No: summarised in the evening review (saves Claude credits) |

---

## 8. Files

| Path | What |
|---|---|
| `config.yaml` | All settings: capital, teams, timings, targets, call budget, agent weights, universe of 76 stocks |
| `watcher.py` | The all-day program (threads: filings, information, trading cycle, exits) |
| `paper_trade.py` | Claude opens a news-team trade by hand (`open`, `status`) |
| `review.py` | Evening review -> `journal/reviews/<date>.md` |
| `App.py` | Streamlit phone app (Yahoo data, estimated premiums) |
| `journal/paper_trades.csv` | Every paper trade |
| `journal/claude_verdicts.csv` | Claude's TRADE/SKIP calls |
| `journal/news_ideas.csv` | News-team ideas (its "chances") |
| `journal/news_guard.csv`, `journal/held_setups.csv` | Movers setups blocked / held while busy |
| `journal/announcements.csv` | Every material NSE filing for our stocks |
| `journal/intel/` | News log, pre-open, volume spurts, news-team skips (per day) |
| `journal/results_history/`, `journal/reaction_model.json` | 3 years of results reactions |
| `journal/day_mode.json` | Today's mode and avoid list |
| `journal/strategy_changes.md` | Every approved change, with the reason |
| `journal/backtest_summary.md` | What every backtest found |
| `.claude/skills/` | Claude's skills: `trading-desk` (runs the desk), `policy-impact`, `candlestick-patterns`, `quantforge-ai` (validation), earnings preview/analysis, news analyst, NLP earnings sentiment, regulatory events, VectorBT backtesting |
| `tests/` | 148 automated tests (`python -m pytest -q`) |

---

## 9. Evidence so far (what the data says)

- Results figures predict the next day's direction 49.6% of the time (3 years): a coin flip.
- Results-day opening gaps carry on 61-75% (1 year x 76 stocks); ordinary-day gaps of 2%+ reverse 55-58%.
- Gap-downs of 2%+ after results kept falling 69% (n=84); 3%+ 73% (n=48).
- Reversal backtest: 83% hit, -1.55% per trade; buying a big gap's recovery: 89% hit, -2.5% per trade; random-quality entries also hit 80-85%. The small 1% target makes the hit rate high; the misses held to 15:20 without a stop-loss make the average negative. The entry signal matters much less than the exit design.
- NSE pre-open (26 Oct): only 23% of 1%+ gaps kept going after the open.

## 10. Scoreboard (paper, to 26 Oct 2026)

| Team | Trades | Hit target | Net |
|---|---|---|---|
| Movers | 5 | 5 | **+₹3,235** |
| News | 8 | 6 | **-₹12,055** (two big losses: PNB -₹4,711, IOC -₹10,613; both cheap options, now blocked) |

## 11. Set it up again

```
pip install -r requirements.txt
sudo apt install tesseract-ocr poppler-utils     # OCR for scanned results PDFs
python -m agents.indmoney login                  # open the link, approve, copy the final address
python -m agents.indmoney finish "<address>"
python -m pytest -q                              # all tests should pass
python3 -u watcher.py                            # during market hours
streamlit run App.py                             # optional phone app
```
The INDmoney token stays at `~/.config/indmoney/token.json` and is never included in this
archive. For Claude Code: open the folder and say "start the trading desk".

## 12. Known limits

- INDmoney allows 500 calls an hour: the watcher paces itself (one call ~every 8 s); a broker API with streaming (Zerodha Kite Connect, Angel One SmartAPI) would remove this limit.
- Some NSE results PDFs are damaged or scanned badly; the reader then has no figures (the press release is the fallback, read by Claude).
- No history exists for NSE order books, intraday option OI or news, so the early-entry rule, order-flow checks and news forecasts are judged on paper only.
- Backtests price options with Black-Scholes at a fixed volatility and spread, not real quotes.
