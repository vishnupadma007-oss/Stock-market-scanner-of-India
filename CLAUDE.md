# Stock Market Scanner of India

Intraday mover-reversal options strategy on NSE F&O stocks, run by a team of agents
(`agents/`), configured in `config.yaml`. Paper trading only.

- `watcher.py`: all-day watcher on live INDmoney data (via `agents/indmoney.py`, the official
  INDmoney MCP server). Prints SIGNAL/EXIT/ERROR lines only.
- `App.py`: Streamlit phone app (Yahoo data, estimated premiums).
- `journal/paper_trades.csv`: paper-trade log. `review.py` writes the evening review to
  `journal/reviews/`; approved strategy changes are logged in `journal/strategy_changes.md`.
  Commit `journal/` at the end of each trading day.
- Agents: regime, scanner, chart reader, options, risk, decision, journal, plus News & Events
  (`agents/news.py`), Macro (`agents/macro.py`), Forecast (`agents/forecast.py`), Crowd Psychology
  (`agents/psychology.py`, observe mode until paper trades prove it) and the morning
  brief's day mode (`agents/daymode.py`, `journal/day_mode.json`), NSE Announcements
  (`agents/announcements.py`: live filings, results figures, OCR for scanned PDFs via Tesseract),
  Market Context (`agents/market.py`: Nifty's move and why, by theme), Commodities (`agents/commodities.py`)
  Policy Impact (`agents/policy.py`: regulator/government moves -> stocks hit/helped, POLICY events;
  `policy-impact` skill), Sector Results (`agents/sector_results.py`: seasonality, YoY vs QoQ, sector KPIs;
  results filings read by 10 parallel workers)
  and NSE holidays (`agents/holidays.py`).
- Information agents write to one log (`agents/intel.py`, `journal/intel/<date>.jsonl`): NSE filings,
  Concalls (`agents/concalls.py`), News (`agents/newsfeed.py`: ET, Mint, BS, CNBC-TV18, Google News).
  The Data Analyzer (`agents/analyzer.py`) turns it into a forecast per stock + market mood.
  The Expectations agent (`agents/expectations.py`) checks whether news/results are already priced
  in (run-up vs Nifty, pre-event hype, price vs analyst target, valuation) on every RESULT and FORECAST.
  The Valuation agent (`agents/valuation.py`, Yahoo P/E, P/B for lenders, vs sector peers, daily
  snapshot in `journal/valuations/`) feeds it and shows on signals (observe mode).
- Results Reaction analyst (`agents/reaction.py`): learns from ~3 years of each stock's results
  (NSE PDFs + Yahoo prices, cached in `journal/results_history/`, model in
  `journal/reaction_model.json`) to give the expected gap/close % with a range on every RESULT;
  also the likely Nifty open from US stocks and Brent (`python -m agents.reaction market`).
- Two teams trade side by side, each with its own paper capital (`config.yaml` -> `teams`):
  movers (top gainers/losers reversal from the chart; the News Guard, `agents/news_guard.py`, borrows
  the news team's knowledge to skip stocks with results, regulatory action, policy hits or strong
  news against the trade, logged in `journal/news_guard.csv`); on market-wide shock days (`agents/shock.py`: big news +
  Nifty 1.5%+ with breadth/VIX/news confirmation) it stops fading gainers in a rally, stops bounce
  trades in a crash, and stands aside on extreme days (SHOCK events) and news (filings/results/news forecasts; the
  watcher opens its trades when the price confirms and the Trend Checker, `agents/momentum.py`,
  scores the chart 60+; ideas logged in `journal/news_ideas.csv`).
  `review.py` keeps a team scoreboard. The user will pick the better team once both have 30+ trades.
- `paper_trade.py`: Claude opens news-team paper trades with it; the watcher manages exits.
- Run tests with `python -m pytest -q`.

Standing permission: restart the watcher during market hours as often as needed, without
asking (paper trading only).

User decisions to respect: intraday only; buy options (PE on fading gainers, CE on
bouncing losers); target >= 1% net of all charges per trade; **no stop-loss**.

To run the desk, use the `trading-desk` skill. To judge whether results are real or luck, use the
`quantforge-ai` skill's validation gates and `scripts/metrics.py` (its stop-loss/kill-switch advice
does not apply here: the user chose no stop-loss).
