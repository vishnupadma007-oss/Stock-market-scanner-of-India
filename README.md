# Stock Market Scanner of India — Mover Reversal Agents

A team of agents that scans NSE top gainers and losers and looks for intraday reversals,
then suggests an option trade (PE on a fading gainer, CE on a bouncing loser) with a
target that clears all charges. Runs as a Streamlit web app you open on your phone.

**Signals only, for paper trading. It does not place orders.**

## The team

| Agent | File | Job |
|---|---|---|
| Market Regime | `agents/regime.py` | Nifty 1-day/1-week/1-month trend + India VIX → which side to trade, or no trade |
| Scanner | `agents/scanner.py` | Top gainers/losers among liquid F&O stocks |
| Chart Reader | `agents/chart_reader.py` | Reads 5-min candles: VWAP, EMA 9/21, RSI, rejection wicks, lower highs, volume → score 0-100 |
| Options | `agents/options.py` | Picks the strike/expiry, estimates premium and delta |
| Risk Manager | `agents/risk.py`, `agents/costs.py` | Position size, trades/day cap, entry window, exit premium for the net target after all charges, forecast chance of reaching it (no stop-loss) |
| AI Analyst | `agents/ai_analyst.py` | Claude looks at the chart image and checks the news; can veto |
| Decision | `agents/decision.py` | TRADE / WATCH / SKIP |
| Journal | `agents/journal.py` | Logs signals for review |

All settings live in `config.yaml`.

## Run it from your phone

1. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and deploy this repo with main file `App.py`.
2. Optional, for the AI analyst: in the app's **Settings → Secrets**, add
   `ANTHROPIC_API_KEY = "sk-ant-..."` (key from console.anthropic.com). Without it the rule-based agents still run.
3. Open the app URL on your phone and use "Add to Home Screen".
4. During market hours (after 09:45 IST), tap **RUN AGENT TEAM**.

## Live watcher with INDmoney (Claude Code)

`watcher.py` runs the same agents on live INDmoney data (real option bid/ask, lot sizes,
greeks) and stays silent until there is a signal, so Claude is only used to confirm signals.
One-time login: `python -m agents.indmoney login`, then `finish "<address>"`. In Claude Code,
just say **start the trading desk** (see `.claude/skills/trading-desk/SKILL.md`).
Paper trades are logged in `journal/paper_trades.csv`.

## Tests

```
pip install -r requirements.txt pytest
pytest
```
