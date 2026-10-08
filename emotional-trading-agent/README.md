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

The meeting happens once a day and is saved, so a restart doesn't pay for it again.

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

## A day on autopilot

```
15:30 → 08:00   News watcher (cheap, fast model) checks the news every 10 minutes and keeps a log.
                (Saturday: hourly. Sunday: every 10 minutes, so Monday's meeting is current.)
08:00           Morning meeting: Moderator, 12 specialists, Strategist and Arjun read the overnight
                news log and the markets, and set the day's plan. Entries are ARMED with trigger
                prices ("buy TCS if it crosses 2,140 before 11:30").
09:15 → 15:10   The reflex engine (plain code, no AI, no cost) checks prices every 3 seconds live
                (30 seconds on paper):
                  - fires an armed entry the instant its price is crossed
                  - takes targets and stop-losses
                  - trails stops: break-even at 1R profit, locks 1R at 2R
                The AI is woken only when something happens:
                  - a sharp move (1% in 5 minutes)
                  - important news (the watcher keeps checking every 10 minutes)
                  - a scheduled review every 30 minutes
                Each time, Arjun can exit, enter now, or re-arm setups.
15:10           Square-off of every intraday position.
                Then the day's verdict, report, journal, and back to watching the news.
```

**Why the AI doesn't watch every tick:** one AI decision takes 10-60 seconds and costs money. Code
reacts in milliseconds for free. So the AI does the thinking (what to trade and at which levels), and
the code does the watching and the reflexes. An AI outage or an empty budget never stops the code
from managing open positions.

## What the AI costs

Estimates for Claude at list prices (Opus 5.5: $4 / $20 per million input/output tokens; Haiku 5.5:
$0.10 / $0.50; web search $10 per 1,000 searches). Real costs depend on how much each search returns.

| Work | Model | How often | Approx. per day |
|---|---|---|---|
| Morning meeting (29 calls, most with web search) | Opus 5.5 | once | $5-6 |
| Arjun's intraday decisions (repeated context cached) | Opus 5.5 | ~15-25 calls | $2-3 |
| News watcher | Haiku 5.5 | ~140 checks, day and night | $2-3 |
| **Trading day total** | | | **~$10** |

That's roughly **$230-250 a month** (about ₹20,000), including weekend news watching. With
`--team-model claude-sonnet-5-5` for the specialists, about $200 a month.

For comparison, an AI looking at every 3-second tick would be ~7,000 calls a day: about $850 a day.
It also couldn't keep up, because each call takes longer than a tick.

**The daily budget** (`--daily-budget`, default $20) is enforced in code, with separate shares so one
kind of work can't starve another: morning meeting 50%, intraday decisions 35%, news watching 15%.
When a share runs out, that work pauses until tomorrow, and the code engine keeps trading the armed plan
and managing positions. Every call's cost is recorded in `state/ai_spend.json` and in the day's report.

Grok: set your real rates with `GROK_PRICE_IN` / `GROK_PRICE_OUT` (USD per million tokens, from xAI's
pricing page) so the budget is accurate. The default is a deliberately high placeholder.

**There is no unlimited plan for the API.** It's pay-as-you-go, billed separately from a Claude.ai
chat subscription. To keep the brains from ever stopping mid-day:

1. Buy prepaid credits in the Claude Console (and/or the xAI console) and turn on **auto-reload**, so
   the balance tops itself up.
2. Set a **monthly spend limit** there too, as a hard ceiling above the code's daily budget.
3. Higher usage tiers raise rate limits as your account's spend grows; the desk's ~30 calls in a burst
   at 08:00 is the peak.
4. If credits ever run out, nothing breaks: the code engine keeps trading the plan and protecting
   positions, and the AI resumes when credits return.

## Setup

```bash
cd emotional-trading-agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # Claude, from https://platform.claude.com
export XAI_API_KEY=xai-...              # Grok, from https://console.x.ai (optional)
```

You need at least one of the two keys. With only one, the whole desk uses it. With both, the default is Claude.

**It needs a computer that stays on**: your PC (no sleep, stable internet) or a small cloud server,
ideally in the Mumbai region for low latency to NSE. Start it with `python agent.py --autopilot` and
leave it running.

**NSE holidays:** put the year's holiday dates (from NSE's website) in `holidays.txt`, one `YYYY-MM-DD`
per line. Without it, the session still notices a holiday when no prices arrive, but the 08:00 meeting
would already have run.

## Use

```bash
python agent.py --autopilot                       # around the clock on paper: news, 08:00 meeting, sessions
python agent.py --session                         # just today's session, tick by tick, until 15:10
python agent.py                                   # one look: meeting + decisions now, no monitoring
python agent.py --autopilot --boss claude --team grok
python agent.py --autopilot --team-model claude-sonnet-5-5   # cheaper specialists
python agent.py --autopilot --daily-budget 10     # spend at most $10 a day on AI
python agent.py --mode swing RELIANCE TCS LT      # delivery trades (longs only)
```

Tuning: `--tick` (seconds between price checks), `--review-every` (minutes between scheduled AI
reviews, default 30), `--news-every` / `--night-every` (news checks, default 10), `--shock` (% move in 5
minutes that wakes the AI, default 1), `--ai-cooldown` (minimum minutes between AI calls, default 3).

Each session writes `output/session_<time>.md`: the news log, agenda, minutes, plan, a timeline of every
trigger, fill, stop move, exit and veto, each of Arjun's decisions, the day's verdict and the AI spend.
To start over, delete `state/`.

## Live trading with Zerodha

```bash
export KITE_API_KEY=...
export KITE_ACCESS_TOKEN=...   # expires daily; generate a fresh one each morning
python agent.py --live --autopilot
```

- At start it asks you once to type `YES` to allow real orders (with `--autopilot`, on every trading day
  until you stop it).
- Prices come from Zerodha every 3 seconds (one request covers the whole watchlist).
- Entries are LIMIT orders. Once an entry fills, it gets protection at Zerodha: a stop-loss order for
  intraday (MIS) or a GTT order with stop and target for delivery (CNC).
- Trailing stops modify the stop-loss order at the exchange.
- The session takes intraday targets and squares off at 15:10. Zerodha also auto-squares MIS near 15:20.
- No orders are sent while the market is closed.
- The Kite access token expires every day, so you must log in each morning before 09:15. Live market
  data through Kite Connect may need a paid API plan; check Zerodha's current pricing.
- SEBI has rules for retail algorithmic trading through broker APIs. Check with Zerodha what applies to
  your account before running this live.

**Other brokers (INDmoney, Upstox, Angel One, ...):** add a class to `broker.py` with the same methods
as `ZerodhaBroker` (`portfolio`, `equity`, `realized_today`, `ltp`, `open`, `close`, `check_exits`,
`square_off`), and wire it in `agent.py`. If your broker's charges differ, edit `RATES` in `charges.py`.

## Files

| File | What it does |
|---|---|
| `agent.py` | Autopilot schedule, morning meeting, trading session, AI wake-ups, verdict, report |
| `reflex.py` | The code engine: armed triggers, trailing stops, sharp-move detector |
| `feed.py` | Fast prices: Zerodha live, or Yahoo 1-minute bars on paper |
| `news.py` | The news watcher and its log |
| `council.py` | The Moderator, 12 specialists, debate, Strategist and Arjun's decision |
| `persona.py` | Arjun's story, mission, emotions, mood, journal and track record |
| `risk.py` | Limits, sizing, charges checks, daily target and loss locks |
| `charges.py` | Indian equity charges (edit `RATES` for your broker) |
| `broker.py` | `PaperBroker` and `ZerodhaBroker` |
| `market_data.py` | NSE daily and 5-minute data from Yahoo Finance, with indicators |
| `llm.py` | Grok and Claude clients, cost metering and the daily AI budget |

*This is an experiment, not investment advice. The agent can be wrong, and with `--live` the money is real.*
