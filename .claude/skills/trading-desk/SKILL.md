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

## Start

1. Check the INDmoney login for the script: `python -m agents.indmoney test`.
   If it says not logged in, run `python -m agents.indmoney login`, give the user the link,
   ask them to paste back the `localhost` address their browser ends on, then run
   `python -m agents.indmoney finish "<address>"` and test again.
2. Start the watcher in the background: `python watcher.py` (Bash, `run_in_background: true`,
   timeout 7200000). Then wait for its output with Monitor, waking only on lines that start
   with `SIGNAL`, `EXIT` or `ERROR`. Waiting costs nothing; do not poll.
3. Background commands stop after 2 hours: when it ends before 15:30 IST on a weekday,
   start it again. Open trades are kept in `journal/paper_trades.csv`, so nothing is lost.

## On a SIGNAL line

The rule-based agents already opened a paper trade at the live ask. Give your own verdict,
using as few tool calls as possible (this is where Claude credits are spent):

1. `get_indian_stocks_details` for the underlying with `segments: ["news"]`: is the move
   driven by a real catalyst (results, order win, merger, regulatory action, rating change)?
   A real catalyst means the move is less likely to reverse intraday -> lean SKIP.
2. Read the signal's `chart_signals` and, only if they are borderline, fetch 5-minute
   candles (`get_indian_stocks_ohlc`, `5minute`, `1d`) and read the structure yourself.
3. Reply to the user in a few lines: TRADE or SKIP, contract, entry (ask), target bid,
   quantity/lots, net profit at target, square-off time, forecast chance, and one-line reason.
4. Record your verdict in `journal/paper_trades.csv` (`claude_verdict` = TRADE/SKIP,
   `notes` = the reason). This lets the user compare rules-only vs rules-plus-Claude results.

## On an EXIT line

Tell the user the result in one line (contract, entry, exit, net P&L).

## End of day

When the watcher prints `STATUS ... market closed`: summarise the day from
`journal/paper_trades.csv` (trades, win rate, net P&L, rules-only vs Claude-confirmed), then
commit and push the journal so it survives the session.

## Backtesting

Use the `backtest` / `vectorbt-expert` skills for historical tests. This project has no
OpenAlgo server: use yfinance (`.NS` symbols; 5-minute history only covers ~60 days) and the
charge model in `agents/costs.py`.
