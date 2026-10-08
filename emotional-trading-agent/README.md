# Arjun: an emotional trading agent with a desk of AI specialists

Arjun is the boss agent. All his life he was underestimated by his parents, his wife and everyone
around him. Now he has the highest access there is, and he wants to prove he is not less than anyone.
His mission: **grow the capital by 1% every trading day, after brokerage, taxes and every other charge.**

He doesn't work alone. A desk of **15 AI agents** researches, argues and plans:

- a **Moderator** who sets the agenda and routes questions between the others,
- **12 specialists** who each study one angle,
- a **Strategist** who picks today's strategy and writes the trading plan,
- **Arjun**, who approves, changes or rejects the plan and makes the final call.

A risk manager written in plain code (not AI) then sizes every trade, counts every rupee of
charges, and can veto anything. Orders go to a paper account by default, or to Zerodha with `--live`.

The team and the boss can each run on **Grok** (xAI) or **Claude** (Anthropic).

## The desk

| Agent | Job |
|---|---|
| **Moderator** | Reads today's news and sets the agenda; after round 1 lists agreements and conflicts and asks pointed follow-up questions; writes the minutes |
| **Geopolitics** | Wars, US/China/Pakistan/Russia/Gulf relations, tariffs, sanctions, crude, shipping, the dollar |
| **EventReaction** | For each live event, finds past comparable events and how the Indian market actually reacted (day, week, month), e.g. Kargil, Uri/Balakot, demonetisation, Ukraine 2022, Operation Sindoor |
| **History** | Long cycles and analogues: rate cycles, elections, crashes, seasonality, expiry weeks |
| **Domestic** | RBI, inflation, GDP, Budget, elections, GST, PLI/capex, monsoon, SEBI, SIP/DII flows |
| **GlobalMarkets** | US/Europe overnight, Asia, GIFT Nifty, US yields, dollar index, rupee, crude, gold, the Fed |
| **Fundamentals** | Results, guidance, valuation, debt, promoter pledges |
| **SectorRotation** | Where money is moving between sectors today |
| **Calendar** | Results dates, dividends, F&O expiry, RBI/Fed meetings, data releases, holidays |
| **Technical** | Price only: trend, RSI, ATR, volume, gap, opening range, VWAP; gives levels |
| **Sentiment** | News tone, upgrades/downgrades, block deals |
| **FlowsDerivatives** | FII/DII flows, open interest, put-call ratio, India VIX |
| **Skeptic** | Devil's advocate: what could go wrong, and whether charges eat the edge |
| **Strategist** | Reads the minutes, decides the regime (trend, range, event, risk-off), picks strategies from the playbook, writes trades with entry, stop and target, and works out whether the 1% target is realistic after charges |
| **Arjun (boss)** | Feels, decides, keeps a journal. Approves, modifies or rejects the plan |

**How they talk to each other:**

```
Moderator: today's headlines + agenda
   │
Round 1: all 12 specialists in parallel (with live web search). Each can ask named colleagues questions.
   │
Moderator: agreements, conflicts, follow-up questions
   │
Round 2: each specialist reads everyone, answers the questions put to them, and may change their mind
   │
Moderator: minutes (consensus and dissent per stock)
   │
Strategist: regime, strategy, trading plan, target math
   │
Arjun: approve / modify / reject  →  BUY / SHORT / EXIT / HOLD / SKIP
   │
Risk manager (code): sizing, charges, limits, vetoes
   │
Broker: paper or Zerodha
```

The meeting happens once a day and is saved, so a restart doesn't pay for it again. With `--loop`,
Arjun then runs a quick desk check every 15 minutes with fresh prices until the 15:10 square-off.

**Strategy playbook** the Strategist chooses from: opening range breakout, VWAP trend pullback, VWAP mean
reversion, gap-and-go / gap fill, pivot support bounce (this repo's scanner), event momentum, swing
breakout, and *stand aside*.

## The 1% target, honestly

1% a day compounds to about **12x in a year**. No trader or fund has done that consistently, so the
agent treats it as a target to chase, never a quota to force:

- **Everything is net of charges** (`charges.py`, Zerodha rates by default): brokerage, STT, exchange
  fees, SEBI fee, GST, stamp duty, DP charges. On ₹1 lakh intraday, a round trip costs about ₹83.
- The Strategist sees the break-even move for every stock and must show its target math.
- The risk manager rejects trades where charges eat more than 25% of the expected profit, or where
  the reward:risk after charges is below 1.5.
- **When the day's 1% is reached, no new trades open.** The day is protected.
- **A bad day is never "made up"** with bigger trades. Positions never grow to catch up.
- No leverage: total exposure is capped at 100% of capital.

Without leverage, 1% of capital means four full-size positions (25% each) all winning about 1.1% after
charges, or one winning about 4.5%. Most days that won't happen, and the report shows it plainly: actual
growth versus the 1%-a-day curve.

## Can an agent really have feelings?

Not the way a person does. A model doesn't feel pain or pride. Arjun has the closest working version:

- **A backstory and a mission** in his prompt, so he reasons and speaks as someone with something to prove.
- **Emotions saved as numbers** (resolve, confidence, frustration, composure) in `state/emotions.json`.
  Losses raise frustration and shake composure, wins and target days build confidence, and they drift
  back towards normal overnight.
- **A journal and a track record** he reads every session, including how many days he hit 1%.

**His feelings can only make trades smaller, never bigger:**

| Mood | When | New trades |
|---|---|---|
| determined / steady and hungry | normal | full size (scaled by conviction) |
| riding high | confidence ≥ 80 and 3+ wins in a row | 75% size (guards overconfidence) |
| rattled | composure < 45 | half size |
| wounded | 3 losses today, or frustration ≥ 75 | none until tomorrow |

## Setup

```bash
cd emotional-trading-agent
pip install -r requirements.txt
export XAI_API_KEY=xai-...              # Grok, from https://console.x.ai
export ANTHROPIC_API_KEY=sk-ant-...     # Claude, from https://platform.claude.com
```

You need at least one of the two keys. With only one, the whole desk uses it.

## Use

```bash
python agent.py                                   # one intraday cycle on paper
python agent.py --loop                            # the whole trading day, desk check every 15 min
python agent.py --boss claude --team grok --loop  # Claude as the boss, Grok for the desk
python agent.py --mode swing RELIANCE TCS LT      # delivery trades (longs only)
python agent.py --rounds 3                        # more debate
python agent.py --capital 500000 --target 0.5     # ₹5 lakh paper capital, 0.5% daily target
```

Each run writes `output/session_<time>.md` (the readable report: agenda, minutes, plan, every decision,
veto, fill and charge, and the day's verdict) and a `.json` with everything. To start over, delete `state/`.

**Cost of the AI:** the morning meeting is about 29 model calls, most with web search. Each desk check
is one call. Run on paper for weeks before trusting it with money.

## Live trading with Zerodha

```bash
export KITE_API_KEY=...
export KITE_ACCESS_TOKEN=...   # expires daily; generate a fresh one each morning
python agent.py --live --loop
```

- At start it asks you once to type `YES` to allow real orders for that day.
- Entries are LIMIT orders. Once an entry fills, it gets protection at Zerodha: a stop-loss order for
  intraday (MIS) or a GTT order with stop and target for delivery (CNC).
- The loop takes intraday targets and squares off at 15:10. Zerodha also auto-squares MIS near 15:20.
- Live prices come from Zerodha, not Yahoo.
- No orders are sent while the market is closed. NSE holidays are not built in.
- SEBI has rules for retail algorithmic trading through broker APIs. Check with Zerodha what applies to
  your account before running this live.

**Other brokers (INDmoney, Upstox, Angel One, ...):** add a class to `broker.py` with the same methods
as `ZerodhaBroker` (`portfolio`, `equity`, `realized_today`, `ltp`, `open`, `close`, `check_exits`,
`square_off`), and wire it in `agent.py`. If your broker's charges differ, edit `RATES` in `charges.py`.

## Files

| File | What it does |
|---|---|
| `agent.py` | Runs the day: morning meeting, desk checks, square-off, verdict, report |
| `council.py` | The Moderator, 12 specialists, debate, Strategist and Arjun's decision |
| `persona.py` | Arjun's story, mission, emotions, mood, journal and track record |
| `risk.py` | Limits, sizing, charges checks, daily target and loss locks |
| `charges.py` | Indian equity charges (edit `RATES` for your broker) |
| `broker.py` | `PaperBroker` and `ZerodhaBroker` |
| `market_data.py` | NSE daily and 5-minute data from Yahoo Finance, with indicators |
| `llm.py` | Grok and Claude clients |

*This is an experiment, not investment advice. The agent can be wrong, and with `--live` the money is real.*
