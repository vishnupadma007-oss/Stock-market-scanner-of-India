---
name: desk-handover
description: Start of a fresh conversation for the trading desk. Read this first in any new session about the NSE paper-trading desk ("start trading desk", "continue", "what's the status", a scheduled check): current state, the user's standing decisions and preferences, open items, and the one-time setup a new session needs (scheduled tasks, INDmoney login, AI key). Replaces re-reading the old long chat.
---

# Trading desk handover (written 30 Oct 2026, from the first long build conversation)

The user (Vishnu) runs a paper-trading desk of AI agents on NSE F&O options from a phone. The old
conversation got so long that every wake-up re-read it and burned Claude credits (81%+ of the plan
used by 30 Oct). Everything needed is in this repository; this skill is the bridge. Keep new
conversations short and keep this file current: update its "State" section in the 15:40 review
whenever something here changes, and commit it.

## Read next (only what the task needs)

- `CLAUDE.md`: the agents and files, user decisions, standing permission.
- `.claude/skills/trading-desk/SKILL.md`: how to run the day (watcher, events, signals, review).
- `GUIDE.md`: every agent and the daily flow, for the user's questions.
- `journal/strategy_changes.md`: every rule change with its reason (newest at the bottom).
- `journal/backtest_summary.md`: every idea tested and its numbers (what worked, what did not).

## One-time setup in a new session (do these before anything else)

1. **Scheduled tasks** fire into the session that created them. The old ones are bound to the old
   conversation (`trig_01Egk7JGxT7rUrEzweu7WQbw` checks 08:40/12:40/15:40, and
   `trig_01CiWASD1TCEwfDqZLuqTkBw` the 09:10 pre-open message). In the new session: read each with
   `get_trigger`, create the same two with `create_trigger` (no `persistent_session_id`, so they fire
   into the new session; same cron and prompt), then `delete_trigger` the two old ones. Tell the user
   in one line.
2. **INDmoney login** lives in `/root/.config/indmoney/token.json`, outside the repo. A new container
   does not have it: run `python -m agents.indmoney test`; if not logged in, send the user the link
   from `python -m agents.indmoney login` and finish with the address they paste back.
3. **AI helper key** (Google Gemini) lives in `/root/.config/gemini/key`, outside the repo. If missing,
   the helper simply stays off; ask the user once to paste the key again (they cannot set environment
   secrets from the phone app), save it there with mode 600, never commit it, and test with
   `python -m agents.ai_helper test`.
4. Run `python -m pytest -q` once (should pass, about 186 tests).

## The user's standing decisions (do not change without asking)

- Paper trading only; intraday only (overnight carry tested 29 Oct and rejected); buy options only
  (CALL for up, PUT for down); **no stop-loss**; square-off 15:20.
- Standing permission: restart the watcher during market hours without asking.
- "Complete free hands" on paper cash flow: top-ups are fine (not counted as profit).
- Two teams, own capital: movers (reversal of top gainers/losers, ₹30,000) and news (₹1 lakh after
  the 29 Oct top-up; top_up in config.yaml). User picks the better team after 30+ trades each.
- Up to 4 open trades per team, sized from free money split over empty slots; never two on one stock.
- When a lot does not fit the free money, buy a cheaper out-of-the-money strike (delta >= 0.15).
- Quiet Volume Spurt is the user's own strategy (news team): heavy volume (1.5x usual for the time of
  day) at a small move (0.2-0.5%), live from NSE every minute; 10% target, 15% when the news agrees
  (label `quiet-spurt-news`, a live test: compare the labels after ~30 trades).
- Claude credits: wake only for problems; report trades at 12:40 and 15:40; replies short; no live
  re-checks unless the user asks. The AI helper (Gemini) gives the per-signal TRADE/SKIP view
  (observe only, `journal/ai_verdicts.csv`); it may get a say only if its calls beat the rules.

## How the user likes to work

- Writes from a phone, often by voice: messages can be partial; answer the evident question.
- Wants plain English, tables for numbers, an honest verdict, and evidence before changes: test an idea
  on the 60-day data (backtest scripts in the repo) and show the numbers, then let the user decide.
- Brings ideas and documents (strategy write-ups, code). Check them; say clearly when the data says no.
- Never claim a real order; never commit tokens or keys; no model names in commits.

## State on 30 Oct 2026 (evening)

- Scoreboard since 19 Oct (after 30 Oct): movers 9 trades, all hit target, +₹4,407; news 20 trades, 45% hit,
  −₹26,970 (30 Oct: 2 targets, 4 quiet-spurt/intel CALLs lost at square-off, −₹15,076) (better since the quiet spurt: TVS Motor +₹4,297 on 29 Oct, the first quiet-spurt-news trade).
- Live tests to judge with more trades: quiet-spurt 10% vs 15% when news agrees; F&O build-up note on
  spurts; previous-day run-up note on spurts (TVS was +3.7% the day before); AI helper's views;
  News Guard on results filed after the last close.
- 30 Oct: the container restarted twice during market hours (~12:40, 14:39) and killed the watcher;
  wait_event.sh did not catch it. The 14:39 stop stranded 4 trades, closed afterwards at the 15:20
  5-minute candle price (noted in each row). Check the watcher at every wake-up.
- Known weak spots: results PDFs that are scans (the AI helper now reads them; spot-check figures
  marked `source: ai` for the first week, e.g. Maruti 27 Oct read as profit −27% YoY, doubtful);
  the news team's late entries near 15:00 rarely reach target.
- Backtests that said no (do not re-propose without new evidence): candlestick patterns, order-flow
  detectors, gap-recovery, volume-fade early exit, 2x spurt threshold, sector-index filter, overnight
  carry, same-side-of-open filter.
- Cached 60-day backtest data (`bt_intra.pkl`, `bt_daily.pkl`) lived in the old scratchpad; rebuild
  with the backtest scripts' download options if a new test needs it.
