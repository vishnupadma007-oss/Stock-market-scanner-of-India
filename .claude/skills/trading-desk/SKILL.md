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
   `notes` as a watchlist with the expected direction; after 09:45, if the price confirms that
   direction, open a results trade with `paper_trade.py` (one trade at a time).
   Then today's events: RBI policy, Budget, F&O expiry (last Tuesday of the month), big results.
   For F&O companies reporting today or tomorrow (results calendar), use the `earnings-preview`
   skill in short form: the 2-3 metrics that will move the stock and a bull/bear case each, so
   the RESULT can be judged in seconds when it lands. Keep it to a few lines per company.
   Finally `python -m agents.analyzer`: the Data Analyzer's market mood and strongest stock
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

The rule-based agents already opened a paper trade at the live ask. The signal already
carries what the agents found: `chart_signals`, `news_and_macro` (INDmoney headlines with
sentiment, results calendar, sudden-pressure volume check, sector/crude/rupee moves),
`forecast` (likely reversal level: VWAP or 38% retracement, and the option price there),
`crowd` (Crowd Psychology agent: futures OI build-up type, 52-week extremes, circuit frenzy;
in observe mode it does not change the score yet, but weigh it in your verdict) and `day_mode`. Give your own verdict, using as few tool calls as possible (this is where Claude
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

## On a RESULT line (a company in our list just filed results on NSE)

The Announcements agent already read the filing: `figures` (revenue and profit: this quarter,
last quarter, year ago, QoQ/YoY %), `highlights` (growth lines from the press release) and
`read` (strong / good / mixed / weak from the numbers alone). Machine reading can fail on
scanned filings: if `figures` is empty or disagrees with `highlights`, trust the highlights.

1. Judge the quarter with the beat/miss checklist from the `earnings-analysis` skill (not its
   full report format): revenue, margins and profit versus the consensus estimate (one web
   search for a large company) and versus this morning's preview, guidance, one-offs. Markets
   react to results versus expectations, not to growth alone.
2. Check the first reaction: one `get_indian_stocks_details` call for the stock's live move.
3. Forecast: direction (up/down), how strong, and whether the price already moved too far.
4. If it is between 09:45 and 14:30 and the numbers and the first reaction agree, open a
   results trade: `python paper_trade.py open --symbol X --direction up|down --strategy results
   --reason "<one line>"`. It applies the same rules (one trade at a time, lot must fit, 1% net
   target, no stop-loss) and the watcher manages the exit. Otherwise note it for the next morning.
5. Tell the user in a few lines: the numbers, your read, the forecast, and what you did.

For a concall transcript, apply the `nlp-earnings-sentiment` ideas: management's tone and
hedging versus last quarter, and evasive answers in the Q&A; tone that diverges from the
numbers is the signal.

## On a NEWS line (a material NSE filing: rating, order, deal, regulatory, management, guidance)

Usually say one line and move on; the News agent already counts it against reversal trades in
that stock. Only dig deeper (read the PDF via `python -m agents.announcements results <pdf>`
or one web search) if it could move the stock a lot (large order relative to the company, rating
downgrade, regulatory action, CEO exit, merger). Use `paper_trade.py` only with a clear direction.

## On a FORECAST line (the Data Analyzer's outlook for a stock turned strong)

It combines every NSE filing, concall and news headline about the stock, its sector and the
market (newer and more important items count more). Strong means the stock's own news is loud
and confirmed by 2+ sources or one major item. The tone reading is a word list, so check it:
read the `reasons` (and one web search if they are thin). If the story is real and the price
agrees (one `get_indian_stocks_details` call), and it is 09:45-14:30 with no trade open, open a
trade: `python paper_trade.py open --symbol X --direction up|down --strategy intel --reason "..."`.
Tell the user in 2-3 lines. If it is noise (wrong company, old story, sarcasm), say so in one line.

## On a COMMODITY line (a commodity moved 3% or more today)

One web search for the reason (supply cut, sanctions, OPEC, mine shutdown, demand data). Tell the
user in two lines: what moved, why, and which of our stocks it affects (`stocks_affected`). If
the move is a lasting shock, add the affected stocks to today's `avoid` list in
`journal/day_mode.json` (the watcher reads it every cycle).

## On an EXIT line

Tell the user the result in one line (contract, entry, exit, net P&L). The desk trades one
position at a time: setups found while a trade is open are only recorded in
`journal/held_setups.csv` (no SIGNAL), and a fresh scan runs right after the exit.

## Evening review

Run it when the watcher prints `STATUS ... market closed`, or whenever the user asks.

1. `python review.py` writes `journal/reviews/<date>.md`: today's trades, running totals,
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
        journal/reviews/pnl_for_metrics.csv`. Keep only changes that help in **both** paper
        trading and the backtest.
     c. Propose at most two changes to the user, each with before/after numbers.
3. **Never apply a change without the user's explicit OK.** When they approve: edit
   `config.yaml` (or the agent code), add a row to `journal/strategy_changes.md`, run the tests,
   and commit that change on its own so it is easy to undo.
4. Changes must keep the user's rules: intraday only, buying options, target at least 1% net,
   **no stop-loss**. If the evidence points at a stop-loss, report the numbers and leave the
   decision to the user.
5. Commit and push `journal/` (trades and the review) so it survives the session.

## Backtesting

Use the `backtest` / `vectorbt-expert` skills for historical tests. This project has no
OpenAlgo server: use yfinance (`.NS` symbols; 5-minute history only covers ~60 days) and the
charge model in `agents/costs.py`.
