# Stock Market Scanner of India

Intraday mover-reversal options strategy on NSE F&O stocks, run by a team of agents
(`agents/`), configured in `config.yaml`. Paper trading only.

- `watcher.py`: all-day watcher on live INDmoney data (via `agents/indmoney.py`, the official
  INDmoney MCP server). Prints SIGNAL/EXIT/ERROR lines only.
- `App.py`: Streamlit phone app (Yahoo data, estimated premiums).
- `journal/paper_trades.csv`: paper-trade log. Commit it at the end of each trading day.
- Run tests with `python -m pytest -q`.

User decisions to respect: intraday only; buy options (PE on fading gainers, CE on
bouncing losers); target >= 1% net of all charges per trade; **no stop-loss**.

To run the desk, use the `trading-desk` skill. To judge whether results are real or luck, use the
`quantforge-ai` skill's validation gates and `scripts/metrics.py` (its stop-loss/kill-switch advice
does not apply here: the user chose no stop-loss).
