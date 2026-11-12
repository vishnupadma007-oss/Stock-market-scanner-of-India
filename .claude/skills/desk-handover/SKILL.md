---
name: desk-handover
description: Start of a fresh conversation for the trading desk. Read this first in any new session about the NSE paper-trading desk ("start trading desk", "continue", "what's the status", a scheduled check): current state, the user's standing decisions and preferences, open items, and the one-time setup a new session needs (branch, scheduled tasks, INDmoney login, AI key). Replaces re-reading the old long chats.
---

# Trading desk handover (updated 12 Nov 2026, end of the third long conversation)

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

1. **Branch.** All desk code and the journal live on branch `ccr-259c0717-ll9dkr` (pushed). If this session's
   designated branch is different: `git fetch origin ccr-259c0717-ll9dkr` and
   `git checkout -B <your branch> origin/ccr-259c0717-ll9dkr`, push (force if the remote branch is stale),
   and from then on commit to this session's branch. The checkout may be sparse: use `git add --sparse`.
   `pip install -q -r requirements.txt pytest` if imports fail.
2. **Scheduled tasks** fire into the session that created them. Move all three: read each with `get_trigger`,
   create the same with `create_trigger` (no `persistent_session_id`; same name, cron and prompt), then
   `delete_trigger` the old one:
   - `trig_01Qm2H4a6KxmVmgSnDXZeFSC` checks 08:40 / 12:40 / 15:40 (morning brief, midday, evening review)
   - `trig_01QRGKfxihGKGFFG3LN6TNLD` pre-open mover forecast 09:10
   - `trig_01X3FsW2ErbPnF7AYDvZzjVb` watcher health checks 13:40 / 14:40 (restart if the container killed it)
   If a trigger id is not found, list them with `list_triggers` and move whatever "Trading desk",
   "Pre-open" and "Watcher health" tasks exist.
3. **INDmoney login** lives in `/root/.config/indmoney/token.json`, outside the repo; a new container will not
   have it. Run `python -m agents.indmoney test`; if not logged in, send the user the link from
   `python -m agents.indmoney login` and finish with `python -m agents.indmoney finish "<address>"`.
   The login expires about daily: at the 08:40 check, if it fails, send the link at once (on 12 Nov it was
   renewed only at 12:29 and the morning entries were missed).
4. **AI helper key** (Google Gemini) lives in `/root/.config/gemini/key`, outside the repo. If missing, ask the
   user for it (a secure route if possible, not chat), save with mode 600, never commit it, test with
   `python -m agents.ai_helper test`.
5. `pip install -q graphifyy` (code-graph MCP in `.mcp.json`, graph in `graphify-out/`; `graphify update .`
   after code changes). Run `python -m pytest -q` once (219 tests should pass).
6. Archive the previous conversation (`archive_session`) when the user asks; the last one was
   `session_016quqf5PhBLMRVciw3PhMwG`.
7. Daily routine: watcher `setsid nohup python3 -u watcher.py >> <scratchpad>/watcher.log 2>&1 < /dev/null &`;
   one background `scripts/wait_event.sh <scratchpad>/watcher.log` (run_in_background, timeout 7200000;
   restart it when its 2-hour limit stops it in market hours); `scripts/journal_quiet.sh on` during the day,
   off for commits. A stop hook asks to commit changed journal/intel files: commit and push them.

## The user's standing decisions (do not change without asking)

- Paper trading only; buy options only (CALL for up, PUT for down); **no stop-loss**; square-off 15:20 (overnight carry is OFF since 10 Nov),
  no overnight holding.
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
- **One desk (10 Nov):** the user wants one profitable desk, not a contest. Playbooks: spurt WITH the market (pure engine), pre-open, news, movers reversal with the stretched-mover big target (`stretch`). Overnight carry is OFF (it lost Rs 45.7k live). See journal/strategy_changes.md 6-10 Nov.
- Claude credits: wake only for problems; report trades at 12:40 and 15:40; short replies; no live
  re-checks unless the user asks.

## How the user likes to work

- Writes from a phone, often by voice: messages can be partial; answer the evident question.
- Wants plain English, tables for numbers, an honest verdict, and evidence: test an idea on the 60-day data
  (backtest scripts in the repo) and show the numbers. Says clearly when the data says no.
- Brings ideas, code and articles (Quantpedia, research); check them against our data before adopting.
- Never claim a real order; never commit tokens or keys; no model names in commits.

## State on 12 Nov 2026 (evening)

- Scoreboard (net so far): news 36 trades +Rs 14,532; movers 11 +Rs 2,974; preopen 14 -Rs 5,707;
  spurt 13 -Rs 23,439. 11 Nov: +Rs 6,915 on same-day trades (gap recovery 3/3 at target). 12 Nov: no trades
  (login renewed only at 12:29).
- Overnight carry is OFF since 10 Nov: carried trades lost (spurt -Rs 20.8k on 5, gap recovery -Rs 44.6k on 4)
  while same-day trades made money. The user asked to cut it (11 Nov): keep it off.
- The user is most focused on the spurt team. Rewired 10 Nov: pure engine + trade only in Nifty's direction
  (flat band 0.15%), window 09:30-11:30, volume 1.8x+, ITM1 delta 0.50-0.65. Backtest 53 trades, 74% hit,
  +Rs 117k in both halves. No live trade yet under the new rules. 12 Nov fix: a spurt hit by an INDmoney
  server error is retried (was dropped). Told the user: judge after ~15 live trades; if still losing, stop it
  and move its money to news and preopen. Do not loosen rules just to get trades.
- Other rules from 6-10 Nov: movers stretched-week reversal (4%+ in a week, 15/10% target), commodity guard on
  movers, news team trades results-backed ideas only (`paused_sources: [intel-news]`), news entries until 13:00.
  Observe only: AI spurt context check, support/resistance level note, valuation.
- Waiting on the user: broker API for live data (key via secure form, never chat); NSE MCP connector.
- The container restarts some afternoons and kills the watcher; the 13:40/14:40 checks restart it.
- Backtests that said no (do not re-propose without new evidence): 1%/0.5% targets, stop-losses, early chart
  exits, volume-fade exits, candlestick patterns, order-flow detectors, 2x spurt threshold, sector filter, gap
  continuation, buying top movers in their direction, 15-day/month screens, overnight carry.
- Backtest data is not in the repo: rebuild 60 days of 5-minute data with yfinance when a new test needs it.
