---
name: desk-handover
description: Start of a fresh conversation for the trading desk. Read this first in any new session about the NSE paper-trading desk ("start trading desk", "continue", "what's the status", a scheduled check): current state, the user's standing decisions and preferences, open items, and the one-time setup a new session needs (branch, scheduled tasks, INDmoney login, AI key). Replaces re-reading the old long chats.
---

# Trading desk handover (updated 4 Nov 2026, end of the second long conversation)

The user (Vishnu) runs a paper-trading desk of AI agents on NSE F&O stock options from a phone. Long
conversations burn Claude credits on every wake-up, so the desk moves to a fresh conversation every few
days. Everything needed is in this repository; this skill is the bridge. Keep replies short and keep this
file current: update "State" in the 15:40 review whenever something here changes, and commit it.

## Read next (only what the task needs)

- `CLAUDE.md`: the agents and files, user decisions, standing permission.
- `.claude/skills/trading-desk/SKILL.md`: how to run the day (watcher, events, signals, review, carry).
- `GUIDE.md`: every agent and the daily flow, for the user's questions.
- `journal/strategy_changes.md`: every rule change with its reason (newest at the bottom).
- `journal/backtest_summary.md`: every idea tested and its numbers (what worked, what did not).

## One-time setup in a new session (do these before anything else, then tell the user in a few lines)

1. **Branch.** All desk code and the journal live on branch `ccr-059c7961-s472hv` (pushed). If this session's
   designated branch is different, bring it up to date with that one: `git fetch origin ccr-059c7961-s472hv`
   and `git merge --ff-only origin/ccr-059c7961-s472hv` (or `git checkout -B <your branch>
   origin/ccr-059c7961-s472hv`), push, and from then on commit to this session's branch. Check
   `ls agents/carry.py agents/probability.py` exists; `pip install -q -r requirements.txt` if imports fail.
2. **Scheduled tasks** fire into the session that created them. Move all three: read each with `get_trigger`,
   create the same with `create_trigger` (no `persistent_session_id`; same name, cron and prompt), then
   `delete_trigger` the old one:
   - `trig_01JSWRPZE47U3krN79HeDBHU` checks 08:40 / 12:40 / 15:40 (morning brief, midday, evening review)
   - `trig_012ugnnYg5NNwYCa82oPDhCU` pre-open mover forecast 09:10
   - `trig_01NShpeSkUZU4eyDE5GRxZX2` watcher health checks 13:40 / 14:40 (restart if the container killed it)
   If a trigger id is not found, list them with `list_triggers` and move whatever "Trading desk",
   "Pre-open" and "Watcher health" tasks exist.
3. **INDmoney login** lives in `/root/.config/indmoney/token.json`, outside the repo. Run
   `python -m agents.indmoney test`; if not logged in, send the user the link from
   `python -m agents.indmoney login` and finish with `python -m agents.indmoney finish "<address>"`.
4. **AI helper key** (Google Gemini) lives in `/root/.config/gemini/key`, outside the repo. If missing, ask
   the user once to paste it, save it with mode 600, never commit it, test with `python -m agents.ai_helper test`.
5. `pip install -q graphifyy` (code-graph MCP in `.mcp.json`, graph in `graphify-out/`; `graphify update .` after code changes). Run `python -m pytest -q` once (209 tests should pass).
6. Archive the previous conversation (`archive_session`) when the user asks; the last one was
   `session_016quqf66GTbFcU8arPvsQra`.

## The user's standing decisions (do not change without asking)

- Paper trading only; buy options only (CALL for up, PUT for down); **no stop-loss**; square-off 15:20,
  except the overnight carry rule (below).
- Standing permission: restart the watcher during market hours without asking.
- "Complete free hands" on paper cash flow (top-ups fine, not counted as profit).
- **Profit first (2 Nov):** keep whatever strategy makes good profit; switch a change on only when the
  backtest shows more money (both halves of the period), otherwise run it in observe mode.
- **Four teams (3-4 Nov), each with its own paper money and 4 slots; the user picks the best after 30+ trades each:**
  - **preopen** (Rs 1 lakh): gap recovery (new 4 Nov: gap 1.5%+, back 1%+ from the early extreme and past
    the open by 09:30 -> trade the recovery; skip results days and gaps with strong news behind them),
    pre-open order flow, results-day gaps (results-gap rule).
  - **news** (Rs 1 lakh): agents' news forecasts (`intel`, unpaused 4 Nov but skipped on a stock's results
    day), results, and quiet spurts the news agrees with (`quiet-spurt-news`).
  - **spurt** (Rs 1 lakh): the user's Quiet Volume Spurt (volume 1.5x usual at a 0.2-0.5% move, no strong
    news); 15% target when the Risk agent's hit chance allows, else 10%; F&O OI build-up recorded (`oi_type`).
  - (4 Nov evening) spurt team is now the user's revived pure engine (`spurt.pure` in config.yaml: no news, calm pre-open, OI not against, multi-week ok, 09:30-11:30, volume 1.8x, spread <= 1%, delta 0.50-0.65); backtest of the testable gates +Rs 97k vs +Rs 156k old rule, see backtest_summary.md. Judge it on live trades.
  - **movers** (Rs 30,000): top gainers/losers reversal, 1% target.
- **Overnight carry (3 Nov, live test):** a trade short of its target at 15:20 stays one night unless results
  today/next session, its own results/regulatory filing today, or expiry within 3 days; sold at the open on
  overnight bad news, else at target or next 15:20 (`agents/carry.py`, notes "carried overnight").
- Observe-only agents (log, never block; AI spurt context check from 6 Nov, journal/ai_spurt_context.csv): Probability Analyzer (`journal/probability.csv`), Trade News
  Monitor (`journal/trade_news.csv`, market-news exits off), AI helper TRADE/SKIP (`journal/ai_verdicts.csv`).
- **Free hands on logic (4 Nov):** I may change the logic of any team on my own judgment; the goal is that every team runs profitably. Change only on backtest evidence (both halves), log it in `journal/strategy_changes.md`, tell the user in one line; a team that keeps losing live gets fixed or paused, not left running.
- Claude credits: wake only for problems; report trades at 12:40 and 15:40; short replies; no live
  re-checks unless the user asks.

## How the user likes to work

- Writes from a phone, often by voice: messages can be partial; answer the evident question.
- Wants plain English, tables for numbers, an honest verdict, and evidence: test an idea on the 60-day data
  (backtest scripts in the repo) and show the numbers. Says clearly when the data says no.
- Brings ideas, code and articles (Quantpedia, research); check them against our data before adopting.
- Never claim a real order; never commit tokens or keys; no model names in commits.

## State on 4 Nov 2026 (morning)

- Scoreboard since 19 Oct, re-sorted into the four teams: preopen 4 trades +Rs 16,759; movers 9 trades (all
  hit) +Rs 4,407; spurt 6 trades -Rs 9,877; news 21 trades -Rs 24,267 (news forecasts alone -Rs 25,965).
- The container restarts most afternoons and kills the watcher (30 Oct, 2 Nov, 3 Nov). The 13:40/14:40 health
  checks restart it. If it still died before 15:20, judge each open trade with the carry rules
  (`carry.should_carry`); square off only those it refuses, at the 15:20 5-minute candle price from INDmoney
  (`get_indian_stocks_ohlc`, 5minute, 1h/3h), with a note in the row.
- NSE changed number formats on 2 Nov ("472.67 L"); `spurt._num` reads both. Watch for similar breaks
  (`ERROR ... spurt scan`) in the morning.
- Backtests that said no (do not re-propose without new evidence): 1% or 0.5% targets with or without repeat
  entries, stop-losses (3-50%, every target), early chart exits, volume-fade exits, candlestick patterns,
  order-flow detectors, 2x spurt threshold, sector filter, support/resistance filter for spurts, gap
  continuation. Promising, watching live: support/resistance "at a level" for movers (20 trades), overnight
  carry, Probability Analyzer gate, news-agrees spurts.
- Ideas offered, not yet built: post-earnings drift (hold results-gap trades 2-3 days), first-30-minute
  momentum filter for spurts, broker live-data API (user may pick a broker; data only, key outside the repo),
  a fix for the news team's return-on-capital shown against Rs 30,000 instead of Rs 1 lakh.
- Backtest data is not in the repo: rebuild 60 days of 5-minute data with yfinance (see `backtest_reversal.load`
  without paths, or the download snippet in the scratchpad notes) when a new test needs it.
