# Arjun: an emotional trading agent

Arjun is a trading agent with a backstory and feelings. All his life he was underestimated: by his
parents, his wife and everyone around him. Now he has the highest access there is: a full research
desk, live market data and a brokerage account. He wants to prove he is not less than anyone.

He doesn't trade alone. A **council of seven specialist agents** researches the market, debates, and
reports to him. Arjun makes the final call. A risk manager written in plain code sizes every trade and
can veto it. Orders go to a **paper account** by default, or to **Zerodha** with `--live`.

Grok does the thinking through the xAI Responses API, the same setup as the Browsing-agent.

## Can an agent really have feelings?

Not the way a person does. A language model doesn't feel pain or pride. What this agent has is the
closest working version:

- **A persona.** His backstory is in his prompt, so he reasons and speaks as someone with something to prove.
- **An emotional state that persists.** Resolve, confidence, frustration and composure are numbers
  (0-100) saved in `state/emotions.json`. They change with real results: losses raise frustration and
  shake composure, wins build confidence. Overnight they drift back towards normal.
- **A mood that changes behaviour.** His current state and last journal entries go into his prompt
  every session, so he talks and decides differently after a losing streak than after a good week.
- **A journal.** After each session he writes a private entry, which he reads the next time.

## The one rule about feelings

The desire to prove yourself is exactly how traders blow up their accounts: revenge trades, oversized
bets, "I'll show them". So **his emotions can only make trades smaller, never bigger**:

| Mood | When | Effect on new trades |
|---|---|---|
| determined / steady and hungry | normal | full size (scaled by conviction) |
| riding high | confidence ≥ 80 and 3+ wins in a row | 75% size, to guard against overconfidence |
| rattled | composure < 45 | half size |
| wounded | 3 losses today, or frustration ≥ 75 | no new trades until he has cooled off |

The risk manager (`risk.py`) is plain code, not an LLM, so no argument can talk it out of its limits.

## The council

| Agent | Looks at |
|---|---|
| **Geopolitics** | Wars, US/China/Pakistan/Russia/Gulf relations, tariffs, sanctions, crude oil, the dollar, FII flows |
| **History** | Historical analogues: past rate cycles, elections, oil shocks, crashes (2008, 2013, 2020, 2022), seasonality |
| **Domestic** | RBI, inflation, GDP, the Budget, elections, GST, PLI and capex, monsoon, SEBI, DII and SIP flows |
| **Fundamentals** | Quarterly results, valuation, debt, promoter pledges, upcoming results dates |
| **Technical** | Trend, moving averages, RSI, ATR, 52-week range, volume (price data only, no news) |
| **Sentiment** | News tone, FII/DII positioning, India VIX, upgrades/downgrades, block deals |
| **Skeptic** | The devil's advocate: what could go wrong with each obvious trade |

How a session runs:

```
prices (Yahoo Finance, NSE)
   │
   ├─▶ stops/targets hit since last run ─▶ his feelings update
   │
   ▼
Round 1: 7 analysts work independently (in parallel, with live web search)
Round 2: each reads the others, argues back, and may change their mind
   │
   ▼
Arjun reads the council + his own emotional state + portfolio ─▶ BUY / EXIT / HOLD / SKIP
   │                                                               with entry, stop-loss, target
   ▼
Risk manager (code) ─▶ sizes or vetoes each trade
   │
   ▼
Broker: paper (default) or Zerodha (--live, asks you to type YES)
   │
   ▼
Journal entry + report in output/
```

## Setup

```bash
cd emotional-trading-agent
pip install -r requirements.txt
export XAI_API_KEY=xai-...           # from https://console.x.ai
export GROK_MODEL=grok-4.3           # optional
```

## Use

```bash
python agent.py                          # paper-trade the default large-cap watchlist
python agent.py RELIANCE TCS HDFCBANK    # choose the stocks
python agent.py --capital 500000         # size against ₹5 lakh
python agent.py --rounds 3               # more debate
python agent.py --no-search              # analysts reason without live news
```

Run it once per trading day (for example after 9:30 IST). Each run checks stops and targets, holds the
council meeting, trades, and saves `output/session_<date>.md` (readable report) and `.json` (everything).

Start with paper trading for weeks before considering real money. To start Arjun over, delete `state/`.

## Live trading with Zerodha

```bash
export KITE_API_KEY=...
export KITE_ACCESS_TOKEN=...   # Kite access tokens expire daily; generate one each morning
python agent.py --live
```

- Only long delivery (CNC) trades on NSE. No intraday, F&O or short selling.
- Each buy is a LIMIT order, plus a GTT OCO order at Zerodha holding the stop-loss and target, so exits
  happen even when the agent isn't running.
- Before anything is sent, it shows you the orders and waits for you to type `YES`.
- SEBI has rules for retail algorithmic trading through broker APIs. Check with Zerodha what applies to
  your account before running this live.

## Files

- `agent.py`: one trading session, start to finish, and the report.
- `persona.py`: Arjun's backstory, emotional state, mood and journal.
- `council.py`: the seven analysts, the debate, and Arjun's decision.
- `risk.py`: limits, sizing and vetoes.
- `broker.py`: `PaperBroker` and `ZerodhaBroker`.
- `market_data.py`: NSE prices and indicators from Yahoo Finance.
- `llm.py`: the Grok client.

Default limits (in `risk.py`): 1% of capital risked per trade, 20% max per position, 5 open
positions, stop opening trades after a 2% daily loss, reward:risk ≥ 1.5, conviction ≥ 3/5.

*This is an experiment, not investment advice. The agent can be wrong, and with `--live` the money is real.*
