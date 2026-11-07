# Graph Report - Stock-market-scanner-of-India  (2026-11-04)

## Corpus Check
- 278 files · ~240,679 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 49 file(s) not represented in the graph (top: .csv 23, .jsonl 23, (none) 3)

## Summary
- 2207 nodes · 4468 edges · 149 communities (141 shown, 8 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 75 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d99b6486`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- numpy
- announcements.py
- preopen.py
- load_config
- watcher.py
- ai_helper.py
- Trusted News Sources for Market Analysis
- news_team
- Market Event Patterns and Market Reactions
- spurt.py
- indicators.py
- config.yaml
- scan
- options.py
- pandas
- Data Fetching
- Corporate News Impact Analysis Framework
- Geopolitical Events and Commodity Correlations
- news
- reaction.py
- NLP Earnings Sentiment
- review.py
- plan
- Quiet volume spurt (user's idea, 28 Oct 2026)
- test_intel.py
- holidays.py
- test_watcher.py
- re
- test_teams.py
- analyzer.py
- candles.py
- carry.py
- indmoney.py
- sector_of
- Complete Indicator Catalog (100+)
- Trading Desk: Complete Guide (27 Oct 2026)
- Report Structure and Templates
- Crypto Market Transaction Costs
- FakeIndMoney
- Market News Analyst
- test_policy.py
- vectorbt-expert/SKILL.md
- expectations.py
- US Market Transaction Costs
- reset_daily
- check
- orderflow.py
- valuation.py
- Creating Indicators & Signals
- Live
- market.py
- newsfeed.py
- pure_spurt_gate
- Trading desk
- DuckDB Direct Data Loading
- data.py
- chain
- Equity Research Earnings Update
- Steps
- Position Sizing
- OpenStatz Tearsheet Integration
- Common Backtesting Pitfalls
- spurt
- intraday
- test_expectations.py
- pick_option
- RateLimited
- Trading desk handover (updated 4 Nov 2026, end of the second long conversation)
- shock.py
- Performance Analysis
- Plotting
- VectorBT Simulation Modes
- build_history
- test_reaction.py
- Best Practices, Examples, and Quality Guidelines
- Detailed Workflow for Earnings Updates
- Indian Market Transaction Costs
- Robustness Testing
- Evening review: 2026-10-27
- Evening review: 2026-11-03
- Strategy changes
- cycle
- json
- Workflow
- teams
- Evening review: 2026-10-21
- Evening review: 2026-10-28
- Evening review: 2026-10-30
- Evening review: 2026-11-02
- Evening review: 2026-11-04
- daymode.py
- Phase 2: Analysis (2-3 hours)
- Execution, Risk Limits, Low-Latency
- QuantForge AI
- Strategy Catalog
- Walk-Forward Analysis
- pure
- Evening review: 2026-10-22
- Evening review: 2026-10-23
- Evening review: 2026-10-26
- Evening review: 2026-10-29
- early_signals
- Analyzing Regulatory Event Impacts
- Comprehensive Quality Control Checklist
- FORMATTING REQUIREMENTS
- Policy impact analysis
- CSV Data Loading & Resampling
- Stop Loss & Take Profit
- VectorBT Backtesting Expert Skill
- charges
- gap_recovery
- macro
- shock
- adjust_forecast
- backtest/SKILL.md
- Critical Requirements
- High-Level Workflow
- Agent Roster
- Strategy Spec (input to backtest) and Research Report (output)
- Validation Gates
- Parameter Optimization
- ai
- budget_otm
- expiry_fallback
- probability
- trade_news
- Stock Market Scanner of India — Mover Reversal Agents
- Candlestick Patterns
- Phase 1: Earnings Data Collection (30-60 minutes)
- optimize/SKILL.md
- Indian Markets and Costs
- analyzer
- carry
- news
- Citation Examples for Specific Content
- quick-stats/SKILL.md
- strategy-compare/SKILL.md
- commodities
- preopen
- valuation
- conftest.py
- _wait_turn
- Third-party skills
- CLAUDE.md
- SOURCE.md
- 2026-10-19.md
- journal_quiet.sh
- wait_event.sh

## God Nodes (most connected - your core abstractions)
1. `load_config()` - 66 edges
2. `scan()` - 54 edges
3. `news_team()` - 52 edges
4. `IndMoney` - 41 edges
5. `plan()` - 38 edges
6. `spurt_entries()` - 35 edges
7. `gap_recovery_entries()` - 33 edges
8. `news` - 30 edges
9. `intraday_sigma_per_min()` - 23 edges
10. `stock_view()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Available Strategies` --references--> `rsi()`  [INFERRED]
  .claude/skills/backtest/SKILL.md → agents/indicators.py
- `Early chart exit (user's idea, 30 Oct 2026)` --references--> `vwap()`  [INFERRED]
  journal/backtest_summary.md → agents/indicators.py
- `Evening review` --references--> `score()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/sector_results.py
- `On a RESULT line (a company in our list just filed results on NSE)` --references--> `highlights()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/announcements.py
- `State on 4 Nov 2026 (morning)` --references--> `should_carry()`  [INFERRED]
  .claude/skills/desk-handover/SKILL.md → agents/carry.py

## Import Cycles
- None detected.

## Communities (149 total, 8 thin omitted)

### Community 0 - "numpy"
Cohesion: 0.05
Nodes (34): assess(), base_rate(), bs_price(), _bucket(), _charges_fast(), features(), fit(), load_model() (+26 more)

### Community 1 - "announcements.py"
Cohesion: 0.05
Nodes (38): change_pct(), classify(), clean_ocr_numbers(), _download(), _extract_table(), fetch_feed(), figures_from_text(), get_nse_session() (+30 more)

### Community 2 - "preopen.py"
Cohesion: 0.07
Nodes (31): confirms(), fetch(), kind(), main(), note(), parse(), save(), assess() (+23 more)

### Community 3 - "load_config"
Cohesion: 0.13
Nodes (22): load_config(), hist_vol(), intraday_sigma_per_min(), suggest_contract(), run(), main(), report(), simulate() (+14 more)

### Community 4 - "watcher.py"
Cohesion: 0.08
Nodes (26): set_hourly_budget(), check_expectations(), emit(), filings_track(), information_track(), lag_seconds(), log_filing(), log_skip() (+18 more)

### Community 5 - "ai_helper.py"
Cohesion: 0.09
Nodes (30): api_key(), ask(), available(), _budget(), _conf(), gemini_text(), _json(), log_verdict() (+22 more)

### Community 6 - "Trusted News Sources for Market Analysis"
Cohesion: 0.04
Nodes (44): Barron's, Best Practices, Bloomberg, Central Bank Researchers, Central Banks and Government Agencies, China-Specific, CNBC, Commodity Markets (+36 more)

### Community 7 - "news_team"
Cohesion: 0.12
Nodes (30): stock_key(), results_calendar(), check_rules(), find_key(), main(), open_trade(), setup(), test_fresh_spurt_is_confirmed_live_and_bought_with_a_10pct_target() (+22 more)

### Community 8 - "Market Event Patterns and Market Reactions"
Cohesion: 0.05
Nodes (40): 2008 Financial Crisis, 2022 Inflation Shock, Bank of Japan (BOJ), Banking Sector Earnings, Central Bank Monetary Policy Events, Commodity-Specific Events, Corporate Defaults / Distress, Corporate Earnings Events (+32 more)

### Community 9 - "spurt.py"
Cohesion: 0.09
Nodes (22): check_multiweek_context(), check_option_limits(), fetch(), fetch_nse(), first_signal(), live_signal(), main(), _num() (+14 more)

### Community 10 - "indicators.py"
Cohesion: 0.11
Nodes (13): candle_png(), _mirror(), read_chart(), _today(), atr(), ema(), rsi(), vwap() (+5 more)

### Community 11 - "config.yaml"
Cohesion: 0.05
Nodes (36): assumed_spread_pct, candles, points, capital, entry_end, entry_start, exit_check_seconds, filings_poll_seconds (+28 more)

### Community 12 - "scan"
Cohesion: 0.11
Nodes (10): main(), go(), IndMoney, main(), check(), daily_candles(), index_candles(), market_context() (+2 more)

### Community 13 - "options.py"
Cohesion: 0.09
Nodes (15): black_scholes(), BSResult, implied_volatility(), last_tuesday(), monthly_expiry(), _ncdf(), _npdf(), strike_step() (+7 more)

### Community 14 - "pandas"
Cohesion: 0.09
Nodes (16): decide(), load(), log(), trades_on(), assess(), _ret(), test_contract_side(), test_decision_keeps_extras_with_ai() (+8 more)

### Community 15 - "Data Fetching"
Cohesion: 0.06
Nodes (32): 1. Indian Markets — OpenAlgo (Primary), 2. US Markets — yfinance (No API Key Needed), 3. Crypto Markets — yfinance or CCXT, 3b. DuckDB Direct Loading (Fastest — No API), 4. Custom Data Provider (Extensible), Adding a Custom Data Provider, CCXT (Higher Resolution — Optional API Key), Crypto Benchmarks (+24 more)

### Community 16 - "Corporate News Impact Analysis Framework"
Cohesion: 0.06
Nodes (30): Bank of America, Wells Fargo, Citigroup, Boeing (Aerospace, Defense), Caterpillar (Construction, Mining Equipment), Consumer Staples Mega-Caps, Corporate News Impact Analysis Framework, Earnings Impact Framework, Energy Mega-Caps, Energy Sector (+22 more)

### Community 17 - "Geopolitical Events and Commodity Correlations"
Cohesion: 0.07
Nodes (29): Agricultural Commodities, Aluminum, Asia-Pacific, Base Metals, Coal, Cobalt, Copper, Corn (+21 more)

### Community 18 - "news"
Cohesion: 0.07
Nodes (30): activity_min_oi_pct, activity_rule, auto_trade, capital, confirm_pct, early_book_x, early_entry, early_pct (+22 more)

### Community 19 - "reaction.py"
Cohesion: 0.14
Nodes (17): dataset(), expected_market_gap(), features_for(), fit(), forecast(), load_history(), load_model(), main() (+9 more)

### Community 20 - "NLP Earnings Sentiment"
Cohesion: 0.07
Nodes (24): Beyond Sentiment, Earnings Call Structure Matters, FinBERT and Financial NLP Models, Usage Pattern, Validation, Why Domain Models, Caveats, Documented Red-Flag Patterns (research-backed) (+16 more)

### Community 21 - "review.py"
Cohesion: 0.16
Nodes (18): ai_scorecard(), _breakdown(), last_change_date(), load(), main(), review(), _risk_summary(), scoreboard() (+10 more)

### Community 22 - "plan"
Cohesion: 0.14
Nodes (12): exit_for_net_target(), round_trip_charges(), reversal_target(), _gamma_adjusted_move(), hit_probability(), plan(), _t(), test_net_target_clears_charges() (+4 more)

### Community 23 - "Quiet volume spurt (user's idea, 28 Oct 2026)"
Cohesion: 0.08
Nodes (25): ATM vs one-strike-ITM (2026-10-19, macro on, same 60 days), Backtest: mover-reversal options, 2026-08 to 2026-10 (60 trading days), Early chart exit (user's idea, 30 Oct 2026), Enhancement pack chart signals (27 Oct 2026), same 60-day data, Gap-recovery idea and results-gap, 26 Oct 2026, New agents (2026-10-19): Macro and Forecast, "News Team Wiring Enhanced" proposal (user, 29 Oct 2026), Order-flow / early-movement detectors (user's whitepaper), 24 Oct 2026 (+17 more)

### Community 24 - "test_intel.py"
Cohesion: 0.15
Nodes (20): to_intel(), load(), make_item(), tone(), item(), test_analyzer_accepts_ist_aware_time(), test_analyzer_needs_agreement_and_fades_old_news(), test_gst_input_tax_credit_is_not_itc_ltd() (+12 more)

### Community 25 - "holidays.py"
Cohesion: 0.17
Nodes (11): holiday_name(), is_trading_day(), load(), refresh(), assess(), headline_date(), next_session(), previous_session() (+3 more)

### Community 26 - "test_watcher.py"
Cohesion: 0.10
Nodes (15): calls_last_hour(), candles_frame(), offline(), test_account_reinvests_profit_and_reserves_open_trades(), test_call_budget_counts_rolling_hour(), test_candles_frame(), test_carry_keeps_a_trade_overnight_and_sells_it_next_day(), test_details_calls_cost_one_per_instrument() (+7 more)

### Community 27 - "re"
Cohesion: 0.16
Nodes (10): commentary(), is_meet(), items_from_rows(), append(), _negated(), path_for(), sectors_in(), symbols_in() (+2 more)

### Community 28 - "test_teams.py"
Cohesion: 0.15
Nodes (16): FakeIndMoney, idea(), test_free_money_is_split_over_the_empty_slots(), test_news_team_enters_early_on_volume_and_order_book(), quotes(), test_news_team_skips_ideas_whose_priced_in_check_failed(), test_news_team_skips_when_the_chart_disagrees(), test_news_team_trades_when_price_confirms() (+8 more)

### Community 29 - "analyzer.py"
Cohesion: 0.19
Nodes (12): as_extra(), main(), market_hours_between(), market_mood(), _mean_tone(), _parse_time(), stock_view(), _top() (+4 more)

### Community 30 - "candles.py"
Cohesion: 0.17
Nodes (11): as_extra(), detect(), main(), _parts(), recent(), test(), frame(), test_bearish_engulfing_after_a_rise() (+3 more)

### Community 31 - "carry.py"
Cohesion: 0.17
Nodes (13): expiry_of(), is_carried(), market_open(), overnight_exit(), _own_filings(), should_carry(), Overnight carry (user, 3 Nov), filing() (+5 more)

### Community 32 - "indmoney.py"
Cohesion: 0.17
Nodes (10): access_token(), _client_auth(), finish_login(), _load(), record_call(), refresh(), _save(), start_login() (+2 more)

### Community 33 - "sector_of"
Cohesion: 0.16
Nodes (11): assess(), kpi_lines(), profile(), score(), sector_of(), test_macro_sector_and_crude(), figs(), test_it_is_read_on_the_sequential_trend() (+3 more)

### Community 34 - "Complete Indicator Catalog (100+)"
Cohesion: 0.10
Nodes (20): Common Signal Pipeline, Complete Indicator Catalog (100+), crossover / crossunder / cross, exrem - Remove Excess Signals (CRITICAL), flip - Regime Detection, Hybrid (7), Momentum (9), NEVER Do This (+12 more)

### Community 35 - "Trading Desk: Complete Guide (27 Oct 2026)"
Cohesion: 0.10
Nodes (19): 10. Scoreboard (paper, to 26 Oct 2026), 11. Set it up again, 12. Known limits, 1. The user's rules (never changed without the user's OK), 2. The big picture, 3. A trading day, minute by minute (IST), 4.1 Movers team, step by step (`watcher.scan`), 4.2 News team, step by step (`watcher.news_team`) (+11 more)

### Community 36 - "Report Structure and Templates"
Cohesion: 0.11
Nodes (19): Business Metrics (1 page), Call Transcript Highlights (optional), Complete Report Structure, Detailed Quarterly Models (if space allows), Guidance & Outlook (1 page), PAGE 1: EARNINGS SUMMARY, PAGES 11-12: APPENDIX (Optional), PAGES 2-3: DETAILED RESULTS ANALYSIS (+11 more)

### Community 37 - "Crypto Market Transaction Costs"
Cohesion: 0.11
Nodes (19): Best Practices, COIN-Margined Futures, Cost Comparison Across Markets, Crypto Market Transaction Costs, Crypto-Specific VectorBT Settings, Crypto Spot (Base Tier), Crypto Spot (BNB Discount), Data Source for Crypto Markets (+11 more)

### Community 38 - "FakeIndMoney"
Cohesion: 0.13
Nodes (11): FakeIndMoney, signals(), test_busy_desk_holds_new_setups(), test_fresh_news_behind_the_move_blocks_the_fade(), test_movers_news_guard_skips_results_day(), test_movers_same_symbol_loss_cooldown(), test_movers_scan_stops_for_a_fresh_news_idea(), test_no_trade_day_mode() (+3 more)

### Community 39 - "Market News Analyst"
Cohesion: 0.11
Nodes (17): Analysis Workflow, Common Pitfalls to Avoid, Important Notes, Key Analysis Principles, Market News Analyst, Output, Overview, Prerequisites (+9 more)

### Community 40 - "test_policy.py"
Cohesion: 0.19
Nodes (14): _one_per_story(), to_intel(), hits(), test_delay_or_softening_is_mild_relief(), test_economists_expectations_are_talk(), test_irdai_commission_caps_hit_policybazaar_hardest(), test_many_articles_about_one_policy_event_count_once(), test_negation_talk_and_false_alarms() (+6 more)

### Community 41 - "vectorbt-expert/SKILL.md"
Cohesion: 0.22
Nodes (4): Best Practices, Compare Long-Only vs Short-Only vs Both, Long + Short Backtesting, Simultaneous Long and Short

### Community 42 - "expectations.py"
Cohesion: 0.20
Nodes (6): analysts(), day_move(), for_symbol(), hype(), run_up(), test_analysts_from_indmoney_details()

### Community 43 - "US Market Transaction Costs"
Cohesion: 0.12
Nodes (16): Best Practices, Data Source for US Markets, Fee Summary by Segment, FINRA Trading Activity Fee (Sell-Side Only), OCC Clearing Fee (Options Only), Popular US Futures Contract Specifications, Quick Reference: Default Fee Constants, Regulatory Fee Details (+8 more)

### Community 44 - "reset_daily"
Cohesion: 0.17
Nodes (11): recent_items(), previous_trading_day(), test_forecast_event_carries_priced_in(), test_results_gap_becomes_an_idea_that_news_cannot_overwrite(), test_ideas_are_logged_once_per_direction(), test_restart_does_not_log_the_same_idea_twice(), test_preopen_and_volume_spurt_ideas_generation(), add_idea() (+3 more)

### Community 45 - "check"
Cohesion: 0.23
Nodes (10): check(), irdai_items(), test_headlines_describing_the_move_do_not_block(), test_policybazaar_bounce_is_blocked(), test_quiet_stock_passes(), test_results_and_regulatory_filings_block_any_side(), test_results_due_today_blocks_both_sides(), test_same_news_does_not_block_a_put() (+2 more)

### Community 46 - "orderflow.py"
Cohesion: 0.27
Nodes (7): features(), latest(), signals(), days(), test_latest_needs_history(), test_spring_and_upthrust(), test_squeeze_breakout_with_volume_gives_a_call()

### Community 47 - "valuation.py"
Cohesion: 0.22
Nodes (7): assess(), fetch(), main(), _metric(), path_for(), snapshot(), test_valuation_against_sector_peers()

### Community 48 - "Creating Indicators & Signals"
Cohesion: 0.14
Nodes (14): ATR (Average True Range), Bollinger Bands Strategy (Default: OpenAlgo ta), Complete OpenAlgo ta Indicator Reference (Default), Creating Indicators & Signals, CRITICAL RULE: OpenAlgo ta by Default, TA-Lib Only on Request, EMA Crossover Strategy (Default: OpenAlgo ta), Fallback: Standalone DuckDB Without OpenAlgo Installed, MACD Strategy (Default: OpenAlgo ta) (+6 more)

### Community 49 - "Live"
Cohesion: 0.14
Nodes (6): test_preopen_idea_needs_the_move_to_continue_after_the_open(), __init__(), gap_setup(), Gapped, Live, test_gap_recovery_skips_a_gap_that_holds()

### Community 50 - "market.py"
Cohesion: 0.24
Nodes (7): context(), headwind(), main(), theme_of(), item(), test_headwind_blocks_trades_against_a_strong_market(), test_themes_and_why()

### Community 51 - "newsfeed.py"
Cohesion: 0.22
Nodes (5): fetch_all(), _fetch_one(), parse(), _when(), test_rss_parsing()

### Community 52 - "pure_spurt_gate"
Cohesion: 0.18
Nodes (7): check_fo_activity(), check_institutional_timing(), check_news_quarantine(), check_preopen_profile(), test_pure_spurt_news_quarantine(), test_pure_spurt_preopen_and_fo_activity(), pure_spurt_gate()

### Community 53 - "Trading desk"
Cohesion: 0.15
Nodes (12): Backtesting, Evening review, Morning brief (about 09:00-09:15 IST, before starting the watcher), On a COMMODITY line (a commodity moved 3% or more today), On a FORECAST line (the Data Analyzer's outlook for a stock turned strong), On a NEWS line (a material NSE filing: rating, order, deal, regulatory, management, guidance), On a POLICY line (a regulator or the government changed the rules), On a SHOCK line (a market-wide rally or crash on big news) (+4 more)

### Community 54 - "DuckDB Direct Data Loading"
Cohesion: 0.15
Nodes (13): 1. Custom DuckDB (User-Created), 2. OpenAlgo Historify DuckDB, Auto-Detection: Which Format?, Best Practices, DuckDB Direct Data Loading, DuckDB Pivot for Wide Format (Memory Efficient), Indicators and Signal Utilities Without openalgo.ta, load_from_custom_duckdb (+5 more)

### Community 55 - "data.py"
Cohesion: 0.26
Nodes (5): daily_bars(), intraday_bars(), nse_lot_sizes(), yahoo_symbol(), load_macro()

### Community 56 - "chain"
Cohesion: 0.20
Nodes (9): _fails(), needs_next_month(), chain(), leg(), test_day_before_expiry_always_rolls(), test_expiry_week_falls_back_to_next_month(), option_chain(), test_incomplete_chain_rows_are_skipped() (+1 more)

### Community 57 - "Equity Research Earnings Update"
Cohesion: 0.18
Nodes (9): Dependencies, Equity Research Earnings Update, Key Differences from Initiation Report, Output Specification, references/best-practices.md, references/report-structure.md, references/workflow.md, Resources (+1 more)

### Community 58 - "Steps"
Cohesion: 0.17
Nodes (11): Arguments, Important Notes, Step 1: Detect Operating System, Step 2: Create Virtual Environment, Step 3: TA-Lib System Dependency (Optional), Step 4: Install Python Packages, Step 5: Create Backtesting Folder, Step 6: Configure .env File (+3 more)

### Community 59 - "Position Sizing"
Cohesion: 0.17
Nodes (10): Futures Backtesting (Lot Size), Futures Fee Structure, Index Futures & Options Lot Sizes (SEBI Revised, Effective 31 Dec 2025), Best Practices, Percent Sizing (Most Popular), Position Sizing, Size Types, Target Percent (Portfolio Rebalancing) (+2 more)

### Community 60 - "OpenStatz Tearsheet Integration"
Cohesion: 0.17
Nodes (11): Basic Usage with VectorBT, Benchmark Options, Complete Backtest Integration Template, Console Metrics (numbers only, no UI), Import Alias: Use `ostz`, Not `os`, Important Notes, Installation, Key Metrics (ostz.stats) (+3 more)

### Community 61 - "Common Backtesting Pitfalls"
Cohesion: 0.17
Nodes (12): 10. Selection Bias in Symbol Choice, 1. Lookahead Bias, 2. Survivorship Bias, 3. Overfitting / Curve Fitting, 4. Data Snooping, 5. Unrealistic Transaction Costs, 6. Ignoring Slippage and Market Impact, 7. Insufficient Trade Count (+4 more)

### Community 62 - "spurt"
Cohesion: 0.17
Nodes (12): spurt, enabled, fresh_min, from, live_max_move_pct, live_min_move_pct, max_move_pct, min_move_pct (+4 more)

### Community 63 - "intraday"
Cohesion: 0.18
Nodes (9): intraday(), test_chart_reader_mirrors_for_losers(), test_chart_reader_retest_of_the_high_is_a_fresh_high(), test_chart_reader_sees_fading_gainer(), test_news_agent_uses_nse_filings(), test_volume_spike_is_sudden_pressure(), candles(), candles() (+1 more)

### Community 64 - "test_expectations.py"
Cohesion: 0.22
Nodes (8): assess(), as_extra(), closes(), test_assess_labels(), test_hype_counts_news_before_the_event(), test_run_up_measures_against_nifty_before_the_event(), test_valuation_extra_observe_and_score(), test_valuation_feeds_priced_in()

### Community 65 - "pick_option"
Cohesion: 0.29
Nodes (6): affordable_option(), lot_cost(), pick_option(), _chain(), test_budget_steps_out_of_the_money_until_one_lot_fits(), test_quotes_are_sent_in_batches_of_ten()

### Community 66 - "RateLimited"
Cohesion: 0.20
Nodes (6): LoginRequired, _parse(), RateLimited, test_leaf_errors_unwraps_groups(), test_rate_limit_reply_raises(), leaf_errors()

### Community 67 - "Trading desk handover (updated 4 Nov 2026, end of the second long conversation)"
Cohesion: 0.22
Nodes (8): assess(), oi_type(), How the user likes to work, One-time setup in a new session (do these before anything else, then tell the user in a few lines), Read next (only what the task needs), The user's standing decisions (do not change without asking), Trading desk handover (updated 4 Nov 2026, end of the second long conversation), test_psychology_oi_types_and_modes()

### Community 68 - "shock.py"
Cohesion: 0.31
Nodes (6): assess(), shock_news(), news(), test_ceasefire_rally_blocks_fading_gainers(), test_extreme_day_stands_aside_and_normal_days_pass(), test_war_crash_blocks_bounce_trades()

### Community 69 - "Performance Analysis"
Cohesion: 0.18
Nodes (10): Benchmark Comparison, CAGR Calculation, Consecutive Wins/Losses Analysis, Equity & Cash, Export Trades, Full Stats, Individual Metrics, Key Metrics to Always Report (+2 more)

### Community 70 - "Plotting"
Cohesion: 0.18
Nodes (10): Available Subplots, Best Practices, Candlestick Chart (Plotly with Category X-Axis), Candlestick with Indicators (Multi-Panel), Custom Strategy vs Benchmark Chart (Plotly), Custom Subplot Settings, Full 7-Panel Plot Pack, NEVER Do This (+2 more)

### Community 71 - "VectorBT Simulation Modes"
Cohesion: 0.18
Nodes (10): 1. from_signals (Signal-Based) - Most Common, 2. from_orders (Order-Based) - Direct Orders, 3. from_order_func (Custom Callback) - Most Powerful, 4. from_holding (Buy-and-Hold Benchmark), Direction, Key Parameters Reference, Random Signal Baseline, Save/Load Portfolio (+2 more)

### Community 72 - "build_history"
Cohesion: 0.20
Nodes (6): add_surprises(), build_history(), _clip(), one(), results_filings(), test_surprise_is_against_own_trend()

### Community 73 - "test_reaction.py"
Cohesion: 0.27
Nodes (4): measure(), reaction_day(), daily(), test_reaction_day_and_measure()

### Community 74 - "Best Practices, Examples, and Quality Guidelines"
Cohesion: 0.20
Nodes (9): 5-Minute Final Review:, Bad Headlines (Avoid):, Best Practices, Examples, and Quality Guidelines, Common Mistakes to Avoid, Example Headlines, Good Earnings Update Headlines:, Pre-Delivery Final Check, Summary Delivery Format (+1 more)

### Community 75 - "Detailed Workflow for Earnings Updates"
Cohesion: 0.20
Nodes (10): ⚠️⚠️⚠️ CRITICAL WARNING: ALWAYS USE THE LATEST EARNINGS DATA ⚠️⚠️⚠️, Detailed Workflow for Earnings Updates, Phase 3: Chart Generation (1-2 hours), Phase 4: Report Creation (2-3 hours), Phase 5: Quality Check & Delivery (30 minutes), Step 12: Generate 8-12 Charts, Step 13: Create DOCX Report, Step 14: Optional - Update XLS Model (+2 more)

### Community 76 - "Indian Market Transaction Costs"
Cohesion: 0.20
Nodes (10): Best Practices, Delivery Equity (CNC), Detailed Breakdown Formulas, F&O Futures, F&O Options, Fee Summary by Segment, Indian Market Transaction Costs, Intraday Equity (+2 more)

### Community 77 - "Robustness Testing"
Cohesion: 0.20
Nodes (9): 1. Monte Carlo Simulation (Trade Shuffling), 2. Noise Test (Price Perturbation), 3. Parameter Sensitivity (Neighbor Test), 4. Entry/Exit Delay Test, 5. Cross-Symbol Validation, 6. Time Period Stability, Best Practices, Robustness Scorecard (+1 more)

### Community 78 - "Evening review: 2026-10-27"
Cohesion: 0.20
Nodes (9): All paper trades so far, Evening review: 2026-10-27, Movers setups stopped by the News Guard: 2, Ready to change the strategy?, Rules only vs Claude-confirmed, Setups held while a trade was open: 1, Team scoreboard: movers vs news, Today (+1 more)

### Community 79 - "Evening review: 2026-11-03"
Cohesion: 0.20
Nodes (9): AI helper's views (observe only): 17 closed trades, All paper trades so far, Evening review: 2026-11-03, Movers setups stopped by the News Guard: 1, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt, Today (+1 more)

### Community 80 - "Strategy changes"
Cohesion: 0.20
Nodes (9): 2026-10-31: Probability Analyzer added in observe mode (user's request), 2026-10-31: Trade News Monitor added in observe mode (user's request), 2026-11-03: News-forecast ("intel") trades paused; money and slots go to the quiet spurt, 2026-11-03: Overnight carry switched on (user's decision), 2026-11-03: Quiet spurt aims for 15% whenever reachable, else 10%, 2026-11-03: Three teams (user's decision), 2026-11-04: Four teams (user's decision), 4 Nov 2026 (evening): revived pure spurt engine (user's design) (+1 more)

### Community 81 - "cycle"
Cohesion: 0.36
Nodes (7): test_save_trades_preserves_concurrent_verdicts_and_external_trades(), test_watcher_signals_then_exits(), cycle(), exits_only(), load_trades(), save_trades(), _trade_key()

### Community 82 - "json"
Cohesion: 0.36
Nodes (4): available(), _parse(), review(), save_model()

### Community 83 - "Workflow"
Cohesion: 0.22
Nodes (8): Earnings Preview, Important Notes, Step 1: Gather Context, Step 2: Key Metrics Framework, Step 3: Scenario Analysis, Step 4: Catalyst Checklist, Step 5: Output, Workflow

### Community 84 - "teams"
Cohesion: 0.22
Nodes (9): capital, news_guard, news_votes, auto_trade, capital, max_open_trades, teams, movers (+1 more)

### Community 85 - "Evening review: 2026-10-21"
Cohesion: 0.22
Nodes (8): All paper trades so far, Evening review: 2026-10-21, Ready to change the strategy?, Rules only vs Claude-confirmed, Setups held while a trade was open: 1, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 86 - "Evening review: 2026-10-28"
Cohesion: 0.22
Nodes (8): All paper trades so far, Evening review: 2026-10-28, Movers setups stopped by the News Guard: 5, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 87 - "Evening review: 2026-10-30"
Cohesion: 0.22
Nodes (8): AI helper's views (observe only): 6 closed trades, All paper trades so far, Evening review: 2026-10-30, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 88 - "Evening review: 2026-11-02"
Cohesion: 0.22
Nodes (8): AI helper's views (observe only): 11 closed trades, All paper trades so far, Evening review: 2026-11-02, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 89 - "Evening review: 2026-11-04"
Cohesion: 0.22
Nodes (8): AI helper's views (observe only): 22 closed trades, All paper trades so far, Evening review: 2026-11-04, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today, Where it wins and loses

### Community 90 - "daymode.py"
Cohesion: 0.29
Nodes (3): apply(), load(), test_day_mode()

### Community 91 - "Phase 2: Analysis (2-3 hours)"
Cohesion: 0.25
Nodes (8): Phase 2: Analysis (2-3 hours), Step 10: Update Valuation & Price Target, Step 11: Assess Rating Impact, Step 5: Beat/Miss Analysis, Step 6: Segment/Geographic/Product Analysis, Step 7: Margin Analysis, Step 8: Guidance Analysis, Step 9: Update Financial Model

### Community 92 - "Execution, Risk Limits, Low-Latency"
Cohesion: 0.25
Nodes (7): Execution, Risk Limits, Low-Latency, Hard risk limits (user supplies values; never invent them), Latency tiers (always label which applies), Modes (never switch silently), Pre-trade checklist (all must pass), Repo layout, Safety mechanisms for execution code

### Community 93 - "QuantForge AI"
Cohesion: 0.25
Nodes (7): Agents (load on demand), Code conventions, Market-specific rules, Non-negotiables, Output format, QuantForge AI, Workflow

### Community 94 - "Strategy Catalog"
Cohesion: 0.25
Nodes (8): 1. EMA Crossover, 2. Donchian Channel Breakout, 3. Momentum (Double MOM), 4. MACD Signal-Candle Breakout, 5. SDA2 Trend Following System, 6. Supertrend (Intraday with Time-Based Exit), 7. Dual Momentum (ETF Rotation), Strategy Catalog

### Community 95 - "Walk-Forward Analysis"
Cohesion: 0.25
Nodes (8): Anchored Walk-Forward, Best Practices, Rolling Walk-Forward, Simple Train/Test Split, Template, Walk-Forward Analysis, Walk-Forward Efficiency Ratio, Why Walk-Forward Matters

### Community 96 - "pure"
Cohesion: 0.25
Nodes (8): enabled, max_delta, max_spread_pct, min_delta, min_oi_pct, preopen_max_gap_pct, window_until, pure

### Community 97 - "Evening review: 2026-10-22"
Cohesion: 0.25
Nodes (7): All paper trades so far, Evening review: 2026-10-22, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 98 - "Evening review: 2026-10-23"
Cohesion: 0.25
Nodes (7): All paper trades so far, Evening review: 2026-10-23, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 99 - "Evening review: 2026-10-26"
Cohesion: 0.25
Nodes (7): All paper trades so far, Evening review: 2026-10-26, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 100 - "Evening review: 2026-10-29"
Cohesion: 0.25
Nodes (7): All paper trades so far, Evening review: 2026-10-29, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news, Today, Where it wins and loses

### Community 101 - "early_signals"
Cohesion: 0.33
Nodes (4): early_signals(), _candles(), test_early_signals_need_volume_and_the_order_book(), test_chart_reader_climax_absorption_and_momentum_fade()

### Community 102 - "Analyzing Regulatory Event Impacts"
Cohesion: 0.29
Nodes (6): Analyzing Regulatory Event Impacts, Inputs To Gather, Output, Quality Checks, When To Use, Workflow

### Community 103 - "Comprehensive Quality Control Checklist"
Cohesion: 0.29
Nodes (7): Accuracy Checklist, Citations & Sources Checklist ⭐⭐⭐ MANDATORY, Comprehensive Quality Control Checklist, Content & Analysis Checklist, Format & Length Checklist, Timeliness Checklist, Writing Style Checklist

### Community 104 - "FORMATTING REQUIREMENTS"
Cohesion: 0.29
Nodes (7): 1. Page 1 Requirements, 2. All Tables Requirements, 3. All Charts Requirements, 4. Year Notation, 5. Writing Style, 6. Hyperlink Requirements ⭐⭐⭐, FORMATTING REQUIREMENTS

### Community 105 - "Policy impact analysis"
Cohesion: 0.29
Nodes (6): 1. What exactly changed?, 2. First-order: whose revenue or costs move directly?, 3. Second-order: who gains from the losers' loss?, 4. Size and speed, 5. Output (to the user, 4-6 lines), Policy impact analysis

### Community 106 - "CSV Data Loading & Resampling"
Cohesion: 0.29
Nodes (6): Best Practices, CSV Data Loading & Resampling, Load from DuckDB and Resample, Load Minute-Level CSV Data, OpenAlgo Historify DuckDB Format, Resample to Different Timeframes

### Community 107 - "Stop Loss & Take Profit"
Cohesion: 0.29
Nodes (6): Best Practices, Combined: Trailing Stop + Take Profit, Fixed Stop Loss + Take Profit, Stop Loss & Take Profit, Stop Loss Variations Summary, Trailing Stop Loss

### Community 108 - "VectorBT Backtesting Expert Skill"
Cohesion: 0.29
Nodes (7): Critical Rules, Environment, Modular Rule Files, Quick Template: DuckDB Backtest Script, Quick Template: Standard Backtest Script, Strategy Templates (in rules/assets/), VectorBT Backtesting Expert Skill

### Community 109 - "charges"
Cohesion: 0.29
Nodes (7): charges, brokerage_per_order, exchange_txn_pct, gst_pct, sebi_per_crore, stamp_buy_pct, stt_sell_pct

### Community 110 - "gap_recovery"
Cohesion: 0.29
Nodes (7): enabled, from, min_bounce_pct, min_gap_pct, targets, until, gap_recovery

### Community 111 - "macro"
Cohesion: 0.29
Nodes (7): macro, crude_move_pct, crude_points, rupee_move_pct, rupee_points, sector_points, sector_trend_pct

### Community 112 - "shock"
Cohesion: 0.29
Nodes (7): shock, breadth_share, extreme_pct, move_pct, news_count, news_hours, vix_jump_pct

### Community 113 - "adjust_forecast"
Cohesion: 0.33
Nodes (4): adjust_forecast(), reaction(), On a RESULT line (a company in our list just filed results on NSE), test_reaction_and_forecast_adjustment()

### Community 114 - "backtest/SKILL.md"
Cohesion: 0.33
Nodes (5): Arguments, Available Strategies, Benchmark Rules, Example Usage, Instructions

### Community 115 - "Critical Requirements"
Cohesion: 0.33
Nodes (6): 1. Speed & Timeliness, 2. Beat/Miss Analysis, 3. Summary Format, 4. Citations & Source Attribution ⭐⭐⭐ MANDATORY, 5. Updated Estimates, Critical Requirements

### Community 116 - "High-Level Workflow"
Cohesion: 0.33
Nodes (6): High-Level Workflow, Phase 1: Data Collection (30-60 minutes), Phase 2: Analysis (2-3 hours), Phase 3: Chart Generation (1-2 hours), Phase 4: Report Creation (2-3 hours), Phase 5: Quality Check & Delivery (30 minutes)

### Community 117 - "Agent Roster"
Cohesion: 0.33
Nodes (5): Agent Creation Spec (for "Create a trading agent"), Agent Roster, Core research, Market specialists, Validation and control

### Community 118 - "Strategy Spec (input to backtest) and Research Report (output)"
Cohesion: 0.33
Nodes (5): 1. Strategy spec: every field required, 2. Backtest quality declaration (state before any result), 3. Research report template, 4. Scoring (0-100, never raw profit alone), Strategy Spec (input to backtest) and Research Report (output)

### Community 119 - "Validation Gates"
Cohesion: 0.33
Nodes (5): Overfitting checklist (PASS / FAIL / UNKNOWN for each), Risk Manager attack list, Robustness tests, Stage gates, Validation Gates

### Community 120 - "Parameter Optimization"
Cohesion: 0.33
Nodes (6): Best Practices, Heatmap Visualization, Method 1: Broadcasting (Vectorized - VectorBT's Killer Feature), Method 2: Loop-Based Optimization (Recommended), Parameter Optimization, When to Use Which Method

### Community 121 - "ai"
Cohesion: 0.33
Nodes (6): ai, enabled, max_calls_per_day, model, provider, timeout

### Community 122 - "budget_otm"
Cohesion: 0.33
Nodes (6): budget_otm, enabled, max_spread_pct, max_steps, min_delta, min_premium

### Community 123 - "expiry_fallback"
Cohesion: 0.33
Nodes (6): expiry_fallback, always_days, days, enabled, max_spread_pct, min_premium

### Community 124 - "probability"
Cohesion: 0.33
Nodes (6): probability, enabled, lookback_days, mode, reject_share, simulations

### Community 125 - "trade_news"
Cohesion: 0.33
Nodes (6): trade_news, enabled, market_impact, mode, raise_pct, use_ai

### Community 126 - "Stock Market Scanner of India — Mover Reversal Agents"
Cohesion: 0.33
Nodes (5): Live watcher with INDmoney (Claude Code), Run it from your phone, Stock Market Scanner of India — Mover Reversal Agents, Tests, The team

### Community 127 - "Candlestick Patterns"
Cohesion: 0.40
Nodes (4): Candlestick Patterns, Commands, On a SIGNAL, What it is worth (keep this honest)

### Community 128 - "Phase 1: Earnings Data Collection (30-60 minutes)"
Cohesion: 0.40
Nodes (5): Phase 1: Earnings Data Collection (30-60 minutes), Step 1: Identify the Latest Earnings Period, Step 2: Gather Earnings Materials, Step 3: Extract Key Metrics, Step 4: Identify Key Themes from Call

### Community 129 - "optimize/SKILL.md"
Cohesion: 0.40
Nodes (4): Arguments, Default Parameter Ranges, Example Usage, Instructions

### Community 130 - "Indian Markets and Costs"
Cohesion: 0.40
Nodes (4): Always specify, Cost model fields (per leg), Indian Markets and Costs, Indian-specific cautions

### Community 131 - "analyzer"
Cohesion: 0.40
Nodes (5): analyzer, against_points, agree_points, forecast_score, min_sources

### Community 132 - "carry"
Cohesion: 0.40
Nodes (5): carry, enabled, min_days_to_expiry, open_after, teams

### Community 133 - "news"
Cohesion: 0.40
Nodes (5): news, block_results_day, fresh_news_points, results_workers, volume_spike_ratio

### Community 134 - "Citation Examples for Specific Content"
Cohesion: 0.50
Nodes (4): Citation Examples for Specific Content, For Beat/Miss Analysis:, For Guidance:, For Key Metrics:

### Community 135 - "quick-stats/SKILL.md"
Cohesion: 0.50
Nodes (3): Arguments, Example Usage, Instructions

### Community 136 - "strategy-compare/SKILL.md"
Cohesion: 0.50
Nodes (3): Arguments, Example Usage, Instructions

### Community 137 - "commodities"
Cohesion: 0.50
Nodes (4): commodities, move_pct, points, shock_pct

### Community 138 - "preopen"
Cohesion: 0.50
Nodes (4): auto_trade, capital, max_open_trades, preopen

### Community 139 - "valuation"
Cohesion: 0.50
Nodes (4): valuation, against_points, agree_points, mode

### Community 141 - "_wait_turn"
Cohesion: 0.67
Nodes (3): _wait_turn(), test_calls_are_paced_evenly(), three()

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_config()` connect `load_config` to `numpy`, `announcements.py`, `preopen.py`, `watcher.py`, `ai_helper.py`, `news_team`, `spurt.py`, `indicators.py`, `scan`, `options.py`, `pandas`, `reaction.py`, `review.py`, `plan`, `test_intel.py`, `test_watcher.py`, `test_teams.py`, `analyzer.py`, `candles.py`, `expectations.py`, `reset_daily`, `valuation.py`, `Live`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `scan()` (e.g. with `4.1 Movers team, step by step (`watcher.scan`)` and `IndMoney`) actually correct?**
  _`scan()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `numpy` be split into smaller, more focused modules?**
  _Cohesion score 0.05388151174668029 - nodes in this community are weakly interconnected._
- **Why does `Trading desk` connect `Trading desk` to `adjust_forecast`, `carry.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `news_team()` (e.g. with `4.2 News team, step by step (`watcher.news_team`)` and `IndMoney`) actually correct?**
  _`news_team()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `announcements.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05446853516657853 - nodes in this community are weakly interconnected._
- **Why does `scan()` connect `scan` to `announcements.py`, `load_config`, `watcher.py`, `news_team`, `indicators.py`, `pandas`, `plan`, `holidays.py`, `test_watcher.py`, `analyzer.py`, `candles.py`, `sector_of`, `Trading Desk: Complete Guide (27 Oct 2026)`, `FakeIndMoney`, `reset_daily`, `check`, `test_expectations.py`, `RateLimited`, `Trading desk handover (updated 4 Nov 2026, end of the second long conversation)`, `shock.py`, `cycle`, `daymode.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._