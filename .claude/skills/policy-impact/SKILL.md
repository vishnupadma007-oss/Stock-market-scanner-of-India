---
name: policy-impact
description: Work out which Indian F&O stocks a regulator's or government's move hurts or helps, and how much, before the market fully prices it. Use on a POLICY line from the watcher, in the morning brief for policy news, or when the user asks how an RBI / SEBI / IRDAI / TRAI / GST / budget / tariff / visa / duty decision affects stocks.
---

# Policy impact analysis

Regulatory news reprices whole business models in minutes. Example: on 24 Sep 2026 IRDAI's
consultation paper proposing caps on insurance commissions sent PB Fintech (PolicyBazaar) down
36% in a day, because commissions are its revenue; banks earning bancassurance fees were hit
far less. The watcher's rulebook (`agents/policy.py`) gives the first answer within seconds and
emits a POLICY line; your job is the analysis a good sell-side analyst would do in the next
ten minutes. Keep it short: the user reads it on a phone.

## 1. What exactly changed?

- Who decided (RBI, SEBI, IRDAI, TRAI, GST Council, Finance Ministry, DGCA, CERC, a foreign
  government) and what instrument: final rule, draft/consultation paper (still moves stocks:
  markets price the probability), speech or "may consider" (weak), or a court/enforcement order.
- When it takes effect, and whether there is a comment deadline. Read the source (one web search,
  or the regulator's circular) if the headline is ambiguous; headlines get policy details wrong.

## 2. First-order: whose revenue or costs move directly?

For each stock in our universe (`config.yaml` -> `universe`), ask: does this change the price,
volume, cost or capital of what the company sells? Estimate the exposure: the share of revenue or
profit touched (e.g. insurance distribution is ~all of PolicyBazaar's revenue but a few % of a
bank's fee income). Rank by exposure x size of the change. Use `agents/sector_results.py` GROUPS
for peers.

## 3. Second-order: who gains from the losers' loss?

Customers (lower commissions -> cheaper policies -> insurers' volumes), competitors (curbs on
NBFC unsecured loans -> banks gain share), suppliers and lenders (an OMC margin squeeze ->
upstream ONGC realisations), substitutes (gold duty hike -> lab-grown / other discretionary).
Name at most three second-order effects, only those you can defend in one sentence each.

## 4. Size and speed

- Direct business-model hit (rule changes the core revenue line): stocks can move 10-35% (PB
  Fintech -36%). Margin effects of a few %: 2-6%. Sector-wide sentiment: 1-3%.
- Already priced? Check the stock's move since the news broke (`get_indian_stocks_details`) and
  `python -m agents.expectations SYMBOL`. If the stock already moved most of your estimate, say so.
- Draft rules can be softened after consultation: say what would change the call. For a pending
  decision (draft, consultation paper, a meeting still to come), use the
  `analyzing-regulatory-event-impacts` skill's method in short form: probability for each outcome
  (final as proposed / softened / dropped), the stock move in each, the expected value, and what
  the price already implies. Ignore its stop-loss and sizing advice (user rules apply).

## 5. Output (to the user, 4-6 lines)

`POLICY: <what changed, who, final/draft>`
`Hit: SYMBOL (-big/-small, why)`, `Helped: SYMBOL (+, why)`, `Second-order: ...`
`Already priced: ...` and, if it fits our rules (intraday, buy options, 1% net target, no
stop-loss, 09:45-14:30, one news-team trade at a time), whether the news team should trade it:
`python paper_trade.py open --symbol X --direction up|down --strategy news --reason "..."`.
Most policy news is for watching, not trading: trade only a direct, large, not-yet-priced hit
whose chart agrees.

If the rulebook got it wrong (false match, wrong direction), say so and fix `agents/policy.py`
with a test in `tests/test_policy.py`.
