---
name: trading-desk
description: Run the intraday mover-reversal paper-trading desk. Starts the market watcher on live INDmoney data, waits silently, and on each SIGNAL confirms it with the INDmoney MCP tools (live option chain, candles, news) before giving the user a TRADE/SKIP call; logs exits. Use when the user says "start trading desk", "watch the market", "/trading-desk", or asks about today's signals or paper trades.
---

# Trading desk

Strategy: on NSE F&O stocks that are today's top gainers/losers, buy a PUT on a gainer that
is exhausting, or a CALL on a loser that is bouncing. Intraday only. Target: at least the
configured net % after all charges (`config.yaml` -> `net_target_pct`). **No stop-loss**: the
user chose this. Exits are the target or `square_off_time` only. Do not add a stop-loss or
argue for one on every signal; mention risk only when something is unusual.

These are **paper trades**. INDmoney access is read-only; never claim an order was placed.

**Two teams trade side by side** (`config.yaml` -> `teams`), each with its own paper capital
(₹30,000 each) and its own one-trade-at-a-time rule, so the user can see which one finds more
chances and makes more money:
- **Movers team** (strategy `reversal`): the top gainers/losers reversal above, read from price,
  charts, options and sector moves (`news_votes: false`), with the **News Guard** as a safety
  brake: a stock with results today, regulatory action, a policy hit or strong real news against
  the trade is skipped (headlines that only describe the move do not count). Stopped setups are
  in `journal/news_guard.csv` and the evening review.
- **News team** (strategies `results`, `intel`): NSE filings, results, concalls and news, turned
  into forecasts by the Data Analyzer and checked by the Expectations agent (priced in?). The
  watcher opens its trades by itself when the price confirms the forecast's direction (moving
  0.5-4% that way today); you can also open one with `paper_trade.py`. Buys a CALL for "up",
  a PUT for "down"; same 1% net target, no stop-loss, same exits.
Each SIGNAL line says its `team`. Keep the teams apart: never close one team's trade because of
the other, and report results per team.

**INDmoney allows 500 calls per hour for the whole account**, shared by the watcher (about
250-300 an hour) and your own INDmoney tool calls. Keep your calls few: no surveys or bulk
lookups during market hours. On `ERROR ... hourly call limit reached` the watcher pauses by itself.

## Morning brief (about 09:00-09:15 IST, before starting the watcher)

**First check that NSE is open today:**
`python -c "from agents.holidays import holiday_name; from datetime import date; print(holiday_name(date.today()))"`
(`None` = trading day). If it prints a holiday, tell the user the market is closed and why, do
not start the watcher, and skip the rest. At the start of each month also run
`python -c "from agents.holidays import refresh; refresh()"` and commit `journal/nse_holidays.json`.

One short research pass that sets the day's mode. Keep it to a handful of searches.

1. Web search: overnight US and Asian markets, GIFT Nifty, Brent crude, USD/INR, and major
   geopolitical or policy news (wars, sanctions, OPEC, Fed/RBI). Use the
   `market-news-analyst` skill's references (geopolitical/commodity correlations, event
   patterns) to judge impact, but apply them to Indian stocks and sectors.
2. Overnight company filings: `python -m agents.announcements overnight` lists every material
   NSE filing for our stocks since the last session's close (results with revenue/profit growth
   already read, ratings, orders, deals, regulatory actions, management exits). For each
   result, judge the likely opening reaction (see "On a RESULT line") and put strong ones in
   `notes` as a watchlist with the expected direction; after 09:15, if the price confirms that
   direction, open a results trade with `paper_trade.py` (one trade at a time).
   Then today's events: RBI policy, Budget, F&O expiry (last Tuesday of the month), big results.
   For F&O companies reporting today or tomorrow (results calendar), use the `earnings-preview`
   skill in short form: the 2-3 metrics that will move the stock and a bull/bear case each, so
   the RESULT can be judged in seconds when it lands. Keep it to a few lines per company.
   Run `python -m agents.reaction market`: the likely Nifty open from US stocks and Brent since
   India's last close (with its usual error). For each company reporting today or tomorrow, run
   `python -m agents.reaction SYMBOL`: expected open and close for a strong / in-line / weak
   quarter, learned from that stock's own past results, and its last six reactions. Give the
   user the numbers (e.g. "strong quarter: open +2.1%, close +3.4%, range -0.5 to +7.3").
   Run `python -m agents.valuation` once (saves today's P/E and P/B snapshot vs sector peers;
   about a minute) and mention any stock on the watchlist that is far richer or cheaper than peers.
   Add `python -m agents.expectations SYMBOL` for each (3-4 INDmoney calls): is a good result
   already priced in (run-up vs Nifty, pre-results hype, price vs analyst target), and so what
   bar the numbers must clear to move the stock (valuation vs peers counts towards it).
   Then `python -m agents.market`: why the market is where it is (geopolitics, policy, domestic
   economy, global markets, commodities, FII/DII flows) with the top headlines for each; lead the
   brief with it. Finally `python -m agents.analyzer`: the Data Analyzer's market mood and strongest stock
   forecasts from the overnight intelligence log (filings, concalls, news). Mention the top ones.
   `python -c "from agents.news import results_calendar as r; import json; from datetime import date; print(json.dumps({s: [str(d) for d in v] for s, v in r().items() if date.today() in v}))"`
   lists companies with results today (the News agent already skips those stocks).
3. Write `journal/day_mode.json`:
   `{"date": "YYYY-MM-DD", "mode": "normal" | "careful" | "no_trade", "notes": ["..."], "avoid": ["SYMBOL", ...]}`
   - `careful`: a big overnight shock, crude or the rupee moving sharply, event day. The watcher
     then needs a stronger chart and allows only 1 trade.
   - `no_trade`: market-wide panic or a major scheduled event during market hours (e.g. RBI
     policy at 10:00, Budget speech).
   - `avoid`: stocks with stock-specific news that makes a reversal unlikely today.
4. Tell the user the mode in 2-3 lines with the main reasons.

## Start

1. Check the INDmoney login for the script: `python -m agents.indmoney test`.
   If it says not logged in, run `python -m agents.indmoney login`, give the user the link,
   ask them to paste back the `localhost` address their browser ends on, then run
   `python -m agents.indmoney finish "<address>"` and test again.
2. Start the watcher in the background: `python watcher.py` (Bash, `run_in_background: true`,
   timeout 7200000). Then wait for its output with Monitor, waking only on lines that start
   with `SIGNAL`, `EXIT`, `RESULT`, `NEWS`, `FORECAST`, `COMMODITY`, `ERROR` or `STATUS`. Waiting costs
   nothing; do not poll.
3. Background commands stop after 2 hours: when it ends before 15:30 IST on a weekday,
   start it again. Open trades are kept in `journal/paper_trades.csv`, so nothing is lost.
   **Standing permission (user, 2026-10-20):** for paper trading, restart the watcher (and
   re-arm the Monitor) as many times as needed during market hours without asking first.
   Just mention restarts briefly in the next status line.

## On a SIGNAL line

A **news-team** signal (`team: news`) has passed the Market Context check (`market`: Nifty's
move, the news mood and its drivers by theme; no CALL into a market down 0.8%+ on bad news, no
PUT into such a rally) and the Trend Checker (`trend_score` 60+ and
`trend_signals`: the chart backs the news's direction) and carries `source` (results / intel), `reason`,
`confidence`, `priced_in` and `valuation`. Check that the story is real (the reason, and one web
search if thin) and that it is not already priced in, then give TRADE/SKIP in 2-3 lines. The
rest of this section is about **movers-team** signals.

The rule-based agents already opened a paper trade at the live ask. The signal already
carries what the agents found: `chart_signals`, `news_and_macro` (INDmoney headlines with
sentiment, results calendar, sudden-pressure volume check, sector/crude/rupee moves),
`forecast` (likely reversal level: VWAP or 38% retracement, and the option price there),
`crowd` (Crowd Psychology agent: futures OI build-up type, 52-week extremes, circuit frenzy;
in observe mode it does not change the score yet, but weigh it in your verdict), `valuation`
(P/E or P/B vs sector peers, also observe mode: an expensive gainer fades more easily, a cheap
loser bounces more easily) and `day_mode`. Give your own verdict, using as few tool calls as possible (this is where Claude
credits are spent):

1. Why is it moving? Read `news_and_macro`. Only if it is unclear (no headline but a
   suspicious move, or `news_driven` is true), run one web search for today's news on the
   stock. A real catalyst (results, order win, merger, regulatory action, rating change,
   promoter/block deal) means the move is less likely to reverse intraday -> lean SKIP.
2. Read `chart_signals`; only if borderline, fetch 5-minute candles
   (`get_indian_stocks_ohlc`, `5minute`, `1d`) and read the structure yourself.
3. Check the forecast: if the forecast level is barely beyond the target, say the trade has
   little room. (The forecast is information only: in the backtest, filtering on it or
   aiming the target at it made results worse.)
4. Reply to the user in a few lines: TRADE or SKIP, contract, entry (ask), target bid,
   quantity/lots, net profit at target, square-off time, forecast chance and forecast level,
   why the stock is moving, and a one-line reason.
5. Record your verdict in `journal/paper_trades.csv` (`claude_verdict` = TRADE/SKIP,
   `notes` = the reason). This lets the user compare rules-only vs rules-plus-Claude results.

After every SIGNAL verdict, append a row to `journal/claude_verdicts.csv`
(`date,symbol,contract,verdict,reason`): the watcher rewrites the trade log, so verdicts written
there are lost. The evening review merges this file to compare rules-only with your calls.

## On a RESULT line (a company in our list just filed results on NSE)

The Announcements agent already read the filing: `figures` (revenue and profit: this quarter,
last quarter, year ago, QoQ/YoY %), `highlights` (growth lines from the press release) and
`read` (strong / good / mixed / weak from the numbers alone). Machine reading can fail on
scanned filings: scanned PDFs are read with OCR (Tesseract) and figures that do not add up are
rejected, but if `figures` is empty or disagrees with `highlights`, trust the highlights, and for a
bank whose PDF is unreadable look for its same-day press release (`python -m agents.announcements
recent SYMBOL`).

0. The line's `read` says how the quarter was read for its sector (`how_read`: against last
   year's same quarter for seasonal businesses such as cement, autos, power, retail; on the
   sequential trend for IT and telecom) and `kpis` lists the sector's key lines (NIM and bad
   loans for banks, constant-currency growth and deal wins for IT, EBITDA per tonne for cement
   and steel, ARPU for telecom, volumes for autos, same-store growth for retail). Judge those
   first: they move these stocks more than headline profit. Scanned filings were read with OCR;
   check a surprising figure against `highlights`.
1. Judge the quarter with the beat/miss checklist from the `earnings-analysis` skill (not its
   full report format): revenue, margins and profit versus the consensus estimate (one web
   search for a large company) and versus this morning's preview, guidance, one-offs. Markets
   react to results versus expectations, not to growth alone.
2. Check the first reaction: one `get_indian_stocks_details` call for the stock's live move.
3. Priced in? The line carries `expectations`: `label` and `bar` say how much good (or bad)
   news the price already holds, from the run-up vs Nifty, the hype in the days before and the
   price vs the average analyst target, plus valuation (P/E or, for lenders, P/B vs sector
   peers: an expensive stock already holds good news). If it is "largely priced in", only a clear beat on
   consensus lifts the stock and an in-line quarter can fall ("sell the news"); if pessimism is
   priced in, a merely decent quarter can lift it. `reaction`, when present, says the price is
   already moving against the numbers: believe the price.
4. Forecast: the line carries `reaction_forecast` from the Results Reaction analyst: expected
   gap and close in %, the likely range, the chance of closing up, and the most similar past
   quarters of this stock with how it reacted. Start from those numbers, then adjust for what
   the machine cannot see (consensus beat/miss, guidance, one-offs, management commentary) and
   say how and why you adjusted. Always give the user a % estimate with a range.
5. The news team already has this as a trade idea and will open it by itself once the price
   confirms (watch for its SIGNAL). Only if your read clearly differs from the machine's (e.g. it
   says "strong" but the quarter missed consensus), and it is 09:15-15:15 with no news-team trade
   open, open the trade yourself: `python paper_trade.py open --symbol X --direction up|down
   --strategy results --reason "<one line>"` (same rules: lot must fit, 1% net target, no
   stop-loss; the watcher manages the exit). Otherwise note it for the next morning.
6. Tell the user in a few lines: the numbers, your read, priced in or not, the forecast, and what you did.

For a concall transcript, apply the `nlp-earnings-sentiment` ideas: management's tone and
hedging versus last quarter, and evasive answers in the Q&A; tone that diverges from the
numbers is the signal.

## On a POLICY line (a regulator or the government changed the rules)

The Policy Impact rulebook (`agents/policy.py`) already tagged the stocks it hits or helps
(`impacts`: direction, strength 1-3, why); its impacts also feed the Data Analyzer. Use the
`policy-impact` skill: what exactly changed (final rule, draft, or talk), first- and
second-order winners and losers in our universe, likely size, and whether it is already priced.
Tell the user in 4-6 lines. Fix the rulebook (with a test) if it mis-tagged the headline.

## On a NEWS line (a material NSE filing: rating, order, deal, regulatory, management, guidance)

Usually say one line and move on; the News agent already counts it against reversal trades in
that stock. Only dig deeper (read the PDF via `python -m agents.announcements results <pdf>`
or one web search) if it could move the stock a lot (large order relative to the company, rating
downgrade, regulatory action, CEO exit, merger). Use `paper_trade.py` only with a clear direction.

## On a FORECAST line (the Data Analyzer's outlook for a stock turned strong)

It combines every NSE filing, concall and news headline about the stock, its sector and the
market (newer and more important items count more). Strong means the stock's own news is loud
and confirmed by 2+ sources or one major item. The tone reading is a word list, so check it:
read the `reasons` (and one web search if they are thin). `priced_in` says whether the price
already holds the story; when it does, the confidence was cut by 25 and `priced_in_note` says
what it would take to move further: prefer no trade unless the news is clearly bigger than
what was expected. The news team turns it into a trade by itself when the price confirms, so
usually just tell the user in 2-3 lines whether the story is real. Open a trade yourself
(`python paper_trade.py open --symbol X --direction up|down --strategy intel --reason "..."`)
only for a story the machine under-rated. If it is noise (wrong company, old story, sarcasm), say so in one line.

## On a COMMODITY line (a commodity moved 3% or more today)

One web search for the reason (supply cut, sanctions, OPEC, mine shutdown, demand data). Tell the
user in two lines: what moved, why, and which of our stocks it affects (`stocks_affected`). If
the move is a lasting shock, add the affected stocks to today's `avoid` list in
`journal/day_mode.json` (the watcher reads it every cycle).

## On an EXIT line

Tell the user the result in one line (team, contract, entry, exit, net P&L). Each team trades
one position at a time: movers setups found while its trade is open are only recorded in
`journal/held_setups.csv` (no SIGNAL), and a fresh scan runs right after the exit.

## Evening review

Run it when the watcher prints `STATUS ... market closed`, or whenever the user asks.

1. `python review.py` writes `journal/reviews/<date>.md`. It starts with the **team scoreboard**
   (movers vs news: chances found, trades, hit rate, net ₹, return on each team's capital);
   lead the user's summary with it. Do not call a winner before both teams have 30+ trades.
   Then: today's trades, running totals,
   rules-only vs Claude-confirmed, and breakdowns by side, entry hour, bid-ask gap and
   forecast chance. Send the user a short summary: today's P&L, the running totals, and one
   notable observation.
2. Check the last section of the review.
   - **NOT YET** (under 30 trades since the last strategy change): change nothing. Say how many
     more trades are needed. Do not suggest changes based on one or two days.
   - **READY**: look for a pattern in the breakdowns (e.g. one side, one time window, wide
     bid-ask gaps, or Claude's SKIPs avoiding the big losses). For each candidate change:
     Also compare results by crowd positioning (long build-up / short covering / long unwinding /
     short build-up). If the agent's `would_score` readings clearly separate winners from losers,
     propose switching `psychology.mode` to `score`.
     a. Test it on history: `python backtest_reversal.py --set key=value --out /tmp/x.csv`
        (e.g. `--set sides=[loser]`, `--set entry_end='"13:00"'`), compared with a run
        without `--set`.
     b. Check both the paper trades and the backtest with the `quantforge-ai` validation gates
        and `python .claude/skills/quantforge-ai/scripts/metrics.py --trades
        journal/reviews/pnl_for_metrics_movers.csv` (and `_news.csv`). Keep only changes that help in **both** paper
        trading and the backtest.
     c. Propose at most two changes to the user, each with before/after numbers.
3. **Never apply a change without the user's explicit OK.** When they approve: edit
   `config.yaml` (or the agent code), add a row to `journal/strategy_changes.md`, run the tests,
   and commit that change on its own so it is easy to undo.
4. Changes must keep the user's rules: intraday only, buying options, target at least 1% net,
   **no stop-loss**. If the evidence points at a stop-loss, report the numbers and leave the
   decision to the user.
5. For companies that reported today: `python -m agents.reaction build SYM1 SYM2 ...` adds their
   new quarter and refits the model (`journal/reaction_model.json`); mention if its direction
   hit rate changed.
6. Commit and push `journal/` (trades and the review) so it survives the session.

## Backtesting

Use the `backtest` / `vectorbt-expert` skills for historical tests. This project has no
OpenAlgo server: use yfinance (`.NS` symbols; 5-minute history only covers ~60 days) and the
charge model in `agents/costs.py`.
