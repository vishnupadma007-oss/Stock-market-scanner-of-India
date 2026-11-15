# Graph Report - Stock-market-scanner-of-India  (2026-11-15)

## Corpus Check
- 318 files · ~286,007 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 74 file(s) not represented in the graph (top: .jsonl 41, .csv 30, (none) 3)

## Summary
- 2512 nodes · 5117 edges · 180 communities (157 shown, 23 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 58 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `041c07ab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- probability.py
- announcements.py
- preopen.py
- load_config
- watcher.py
- ai_helper.py
- Trusted News Sources for Market Analysis
- news_team
- Market Event Patterns and Market Reactions
- check_news_quarantine
- reset_daily
- config.yaml
- scan
- math
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
- news.py
- asyncio
- overnight.py
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
- adr_team.py
- US Market Transaction Costs
- trade_news.py
- check
- indicators.py
- pathlib
- Creating Indicators & Signals
- daymode.py
- market.py
- newsfeed.py
- orderflow.py
- expectations.py
- DuckDB Direct Data Loading
- requests
- chain
- Equity Research Earnings Update
- Steps
- Position Sizing
- OpenStatz Tearsheet Integration
- Common Backtesting Pitfalls
- spurt
- valuation.py
- test_events.py
- Evening review: 2026-11-14
- RateLimited
- Trading desk handover (updated 4 Nov 2026, end of the second long conversation)
- shock.py
- Performance Analysis
- Plotting
- VectorBT Simulation Modes
- Trading desk
- figures_from_text
- Best Practices, Examples, and Quality Guidelines
- Detailed Workflow for Earnings Updates
- Indian Market Transaction Costs
- Robustness Testing
- Evening review: 2026-10-27
- Evening review: 2026-11-03
- Strategy changes
- test_expectations.py
- json
- Workflow
- teams
- Evening review: 2026-10-21
- Evening review: 2026-10-28
- Evening review: 2026-10-30
- Evening review: 2026-11-02
- Evening review: 2026-11-04
- classify
- Phase 2: Analysis (2-3 hours)
- Execution, Risk Limits, Low-Latency
- QuantForge AI
- Strategy Catalog
- Walk-Forward Analysis
- Evening review: 2026-11-06
- Evening review: 2026-10-22
- Evening review: 2026-10-23
- Evening review: 2026-10-26
- Evening review: 2026-10-29
- Evening review: 2026-11-09
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
- Evening review: 2026-11-11
- early_signals
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
- backtest_trade_news.py
- valuation
- conftest.py
- Evening review: 2026-11-12
- test_spurt.py
- CLAUDE.md
- SOURCE.md
- 2026-10-19.md
- journal_quiet.sh
- wait_event.sh
- Evening review: 2026-11-13
- first_signal
- Evening review: 2026-11-05
- numpy
- commodities.py
- Long + Short Backtesting
- stretch
- parse_nse
- Futures Backtesting (Lot Size)
- graphify
- offline
- cycle
- candles
- psychology
- Live
- mover_forecast.py
- adr
- backtest/SKILL.md
- monthly_expiry
- check_fo_activity
- adjust_forecast
- as_extra
- Third-party skills
- 4. The two teams
- stretch_week_pct

## God Nodes (most connected - your core abstractions)
1. `load_config()` - 78 edges
2. `scan()` - 53 edges
3. `news_team()` - 50 edges
4. `plan()` - 44 edges
5. `spurt_entries()` - 43 edges
6. `IndMoney` - 42 edges
7. `suggest_contract()` - 33 edges
8. `news` - 32 edges
9. `gap_recovery_entries()` - 31 edges
10. `Quiet volume spurt (user's idea, 28 Oct 2026)` - 31 edges

## Surprising Connections (you probably didn't know these)
- `Available Strategies` --references--> `rsi()`  [INFERRED]
  .claude/skills/backtest/SKILL.md → agents/indicators.py
- `Evening review` --references--> `score()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/sector_results.py
- `On a RESULT line (a company in our list just filed results on NSE)` --references--> `highlights()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/announcements.py
- `Overnight carry (user, 3 Nov)` --references--> `should_carry()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/carry.py
- `Third-party skills` --references--> `setup()`  [INFERRED]
  .claude/skills/THIRD_PARTY.md → tests/test_spurt.py

## Import Cycles
- 2-file cycle: `agents/mover_forecast.py -> agents/overnight.py -> agents/mover_forecast.py`

## Communities (180 total, 23 thin omitted)

### Community 0 - "probability.py"
Cohesion: 0.09
Nodes (31): assess(), base_rate(), bs_price(), _bucket(), _charges_fast(), features(), fit(), load_model() (+23 more)

### Community 1 - "announcements.py"
Cohesion: 0.12
Nodes (12): change_pct(), _download(), _extract_table(), get_nse_session(), _numbers(), _ocr_page(), ocr_text(), pdf_text() (+4 more)

### Community 2 - "preopen.py"
Cohesion: 0.08
Nodes (27): confirms(), fetch(), kind(), main(), note(), parse(), save(), assess() (+19 more)

### Community 3 - "load_config"
Cohesion: 0.10
Nodes (29): load_config(), hist_vol(), intraday_sigma_per_min(), strike_step(), suggest_contract(), main(), report(), simulate() (+21 more)

### Community 4 - "watcher.py"
Cohesion: 0.07
Nodes (30): recent_items(), holiday_name(), is_trading_day(), previous_trading_day(), append(), test_forecast_event_carries_priced_in(), test_holidays_and_expiry(), check_expectations() (+22 more)

### Community 5 - "ai_helper.py"
Cohesion: 0.12
Nodes (20): api_key(), ask(), available(), _budget(), _conf(), context_info(), gemini_text(), _json() (+12 more)

### Community 6 - "Trusted News Sources for Market Analysis"
Cohesion: 0.04
Nodes (44): Barron's, Best Practices, Bloomberg, Central Bank Researchers, Central Banks and Government Agencies, China-Specific, CNBC, Commodity Markets (+36 more)

### Community 7 - "news_team"
Cohesion: 0.13
Nodes (30): stock_key(), results_calendar(), check_rules(), main(), open_trade(), setup(), test_fresh_spurt_is_confirmed_live_and_bought_with_a_10pct_target(), test_old_spurt_is_not_traded() (+22 more)

### Community 8 - "Market Event Patterns and Market Reactions"
Cohesion: 0.05
Nodes (40): 2008 Financial Crisis, 2022 Inflation Shock, Bank of Japan (BOJ), Banking Sector Earnings, Central Bank Monetary Policy Events, Commodity-Specific Events, Corporate Defaults / Distress, Corporate Earnings Events (+32 more)

### Community 9 - "check_news_quarantine"
Cohesion: 0.20
Nodes (6): check_institutional_timing(), check_news_quarantine(), late_burst_ok(), test_bar_burst_and_late_window(), test_news_quarantine_ignores_routine_news(), test_pure_spurt_news_quarantine()

### Community 10 - "reset_daily"
Cohesion: 0.18
Nodes (10): test_result_reported_once_per_company_unless_figures_arrive_later(), test_results_gap_becomes_an_idea_that_news_cannot_overwrite(), test_ideas_are_logged_once_per_direction(), test_restart_does_not_log_the_same_idea_twice(), test_preopen_and_volume_spurt_ideas_generation(), add_idea(), preopen_early_ideas(), reset_daily() (+2 more)

### Community 11 - "config.yaml"
Cohesion: 0.06
Nodes (33): assumed_spread_pct, capital, commodity_guard, entry_end, entry_start, exit_check_seconds, filings_poll_seconds, forecast_capture (+25 more)

### Community 12 - "scan"
Cohesion: 0.11
Nodes (11): main(), go(), IndMoney, check(), find_key(), daily_candles(), index_candles(), market_context() (+3 more)

### Community 13 - "math"
Cohesion: 0.19
Nodes (6): black_scholes(), BSResult, implied_volatility(), _ncdf(), _npdf(), test_implied_volatility_and_live_greeks_enrichment()

### Community 14 - "pandas"
Cohesion: 0.10
Nodes (21): main(), test(), context_table(), ctx_of(), daily(), part_a(), part_b(), part_c() (+13 more)

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
Cohesion: 0.06
Nodes (32): activity_min_oi_pct, activity_rule, auto_trade, capital, confirm_pct, early_book_x, early_entry, early_pct (+24 more)

### Community 19 - "reaction.py"
Cohesion: 0.08
Nodes (28): add_surprises(), build_history(), _clip(), dataset(), expected_market_gap(), features_for(), fit(), forecast() (+20 more)

### Community 20 - "NLP Earnings Sentiment"
Cohesion: 0.07
Nodes (24): Beyond Sentiment, Earnings Call Structure Matters, FinBERT and Financial NLP Models, Usage Pattern, Validation, Why Domain Models, Caveats, Documented Red-Flag Patterns (research-backed) (+16 more)

### Community 21 - "review.py"
Cohesion: 0.06
Nodes (39): nifty_gap_fallback(), acall(), go(), call(), daily_history(), go(), _f(), history_frame() (+31 more)

### Community 22 - "plan"
Cohesion: 0.08
Nodes (24): exit_for_net_target(), round_trip_charges(), decide(), reversal_target(), assess(), _ret(), _gamma_adjusted_move(), hit_probability() (+16 more)

### Community 23 - "Quiet volume spurt (user's idea, 28 Oct 2026)"
Cohesion: 0.05
Nodes (38): ADR-stocks team idea (user, 14 Nov 2026): `backtest_adr_team.py` - not adopted, ADR team: regime-switching plan (user, 15 Nov 2026): `backtest_adr_regimes.py`, `agents/adr_team.py`, Are we late on results? (user's question, 10 Nov 2026) - 29 results filings with a clear read, 19 Oct - 6 Nov, ATM vs one-strike-ITM (2026-10-19, macro on, same 60 days), Backtest: mover-reversal options, 2026-08 to 2026-10 (60 trading days), Can the news predict the move? (user's question, 10 Nov 2026) - 164 live news ideas, 21 Oct - 6 Nov, measured on 5-minute prices, Early chart exit (user's idea, 30 Oct 2026), Enhancement pack chart signals (27 Oct 2026), same 60-day data (+30 more)

### Community 24 - "test_intel.py"
Cohesion: 0.11
Nodes (27): to_intel(), commentary(), is_meet(), items_from_rows(), load(), make_item(), _negated(), path_for() (+19 more)

### Community 25 - "news.py"
Cohesion: 0.30
Nodes (6): assess(), headline_date(), next_session(), previous_session(), volume_spike(), test_news_results_and_headlines()

### Community 26 - "asyncio"
Cohesion: 0.22
Nodes (6): main(), set_hourly_budget(), _wait_turn(), test_quotes_are_sent_in_batches_of_ten(), test_calls_are_paced_evenly(), three()

### Community 27 - "overnight.py"
Cohesion: 0.12
Nodes (19): main(), compare(), _daily(), evaluate(), fit(), forecast(), gap_table(), label() (+11 more)

### Community 28 - "test_teams.py"
Cohesion: 0.11
Nodes (22): intraday(), test_news_agent_uses_nse_filings(), test_volume_spike_is_sudden_pressure(), FakeIndMoney, idea(), test_free_money_is_split_over_the_empty_slots(), test_news_team_enters_early_on_volume_and_order_book(), candles() (+14 more)

### Community 29 - "analyzer.py"
Cohesion: 0.24
Nodes (10): main(), market_hours_between(), market_mood(), _mean_tone(), _parse_time(), stock_view(), _top(), _trading_day() (+2 more)

### Community 30 - "candles.py"
Cohesion: 0.20
Nodes (9): as_extra(), detect(), _parts(), recent(), frame(), test_bearish_engulfing_after_a_rise(), test_hammer_after_a_fall(), test_no_reversal_pattern_without_a_prior_move() (+1 more)

### Community 31 - "carry.py"
Cohesion: 0.16
Nodes (14): expiry_of(), is_carried(), market_open(), overnight_exit(), _own_filings(), should_carry(), Overnight carry (user, 3 Nov), filing() (+6 more)

### Community 32 - "indmoney.py"
Cohesion: 0.14
Nodes (14): access_token(), calls_last_hour(), _client_auth(), finish_login(), _load(), LoginRequired, record_call(), refresh() (+6 more)

### Community 33 - "sector_of"
Cohesion: 0.16
Nodes (11): assess(), kpi_lines(), profile(), score(), sector_of(), test_macro_sector_and_crude(), figs(), test_it_is_read_on_the_sequential_trend() (+3 more)

### Community 34 - "Complete Indicator Catalog (100+)"
Cohesion: 0.10
Nodes (20): Common Signal Pipeline, Complete Indicator Catalog (100+), crossover / crossunder / cross, exrem - Remove Excess Signals (CRITICAL), flip - Regime Detection, Hybrid (7), Momentum (9), NEVER Do This (+12 more)

### Community 35 - "Trading Desk: Complete Guide (27 Oct 2026)"
Cohesion: 0.12
Nodes (16): 10. Scoreboard (paper, to 26 Oct 2026), 11. Set it up again, 12. Known limits, 1. The user's rules (never changed without the user's OK), 2. The big picture, 3. A trading day, minute by minute (IST), 5. Every agent, 6. Contract choice and exits (+8 more)

### Community 36 - "Report Structure and Templates"
Cohesion: 0.11
Nodes (19): Business Metrics (1 page), Call Transcript Highlights (optional), Complete Report Structure, Detailed Quarterly Models (if space allows), Guidance & Outlook (1 page), PAGE 1: EARNINGS SUMMARY, PAGES 11-12: APPENDIX (Optional), PAGES 2-3: DETAILED RESULTS ANALYSIS (+11 more)

### Community 37 - "Crypto Market Transaction Costs"
Cohesion: 0.11
Nodes (19): Best Practices, COIN-Margined Futures, Cost Comparison Across Markets, Crypto Market Transaction Costs, Crypto-Specific VectorBT Settings, Crypto Spot (Base Tier), Crypto Spot (BNB Discount), Data Source for Crypto Markets (+11 more)

### Community 38 - "FakeIndMoney"
Cohesion: 0.08
Nodes (22): candles_frame(), FakeIndMoney, signals(), test_account_reinvests_profit_and_reserves_open_trades(), test_busy_desk_holds_new_setups(), test_candles_frame(), test_carry_keeps_a_trade_overnight_and_sells_it_next_day(), test_fresh_news_behind_the_move_blocks_the_fade() (+14 more)

### Community 39 - "Market News Analyst"
Cohesion: 0.11
Nodes (17): Analysis Workflow, Common Pitfalls to Avoid, Important Notes, Key Analysis Principles, Market News Analyst, Output, Overview, Prerequisites (+9 more)

### Community 40 - "test_policy.py"
Cohesion: 0.16
Nodes (16): _one_per_story(), assess(), main(), to_intel(), hits(), test_delay_or_softening_is_mild_relief(), test_economists_expectations_are_talk(), test_irdai_commission_caps_hit_policybazaar_hardest() (+8 more)

### Community 42 - "adr_team.py"
Cohesion: 0.08
Nodes (13): atr14(), classify_regime(), detect_exhaustion(), expected_gap_pct(), fade_decision(), generate_trade_signal(), overnight_context(), move() (+5 more)

### Community 43 - "US Market Transaction Costs"
Cohesion: 0.12
Nodes (16): Best Practices, Data Source for US Markets, Fee Summary by Segment, FINRA Trading Activity Fee (Sell-Side Only), OCC Clearing Fee (Options Only), Popular US Futures Contract Specifications, Quick Reference: Default Fee Constants, Regulatory Fee Details (+8 more)

### Community 44 - "trade_news.py"
Cohesion: 0.19
Nodes (13): ai_helper_cfg(), ai_judge(), check(), raised_target(), _when(), walk(), item(), test_bad_news_for_the_stock_is_good_for_a_put() (+5 more)

### Community 45 - "check"
Cohesion: 0.23
Nodes (10): check(), irdai_items(), test_headlines_describing_the_move_do_not_block(), test_policybazaar_bounce_is_blocked(), test_quiet_stock_passes(), test_results_and_regulatory_filings_block_any_side(), test_results_due_today_blocks_both_sides(), test_same_news_does_not_block_a_put() (+2 more)

### Community 46 - "indicators.py"
Cohesion: 0.09
Nodes (21): candle_png(), _mirror(), read_chart(), _today(), atr(), ema(), rsi(), vwap() (+13 more)

### Community 48 - "Creating Indicators & Signals"
Cohesion: 0.14
Nodes (14): ATR (Average True Range), Bollinger Bands Strategy (Default: OpenAlgo ta), Complete OpenAlgo ta Indicator Reference (Default), Creating Indicators & Signals, CRITICAL RULE: OpenAlgo ta by Default, TA-Lib Only on Request, EMA Crossover Strategy (Default: OpenAlgo ta), Fallback: Standalone DuckDB Without OpenAlgo Installed, MACD Strategy (Default: OpenAlgo ta) (+6 more)

### Community 49 - "daymode.py"
Cohesion: 0.33
Nodes (3): apply(), load(), test_day_mode()

### Community 50 - "market.py"
Cohesion: 0.24
Nodes (7): context(), headwind(), main(), theme_of(), item(), test_headwind_blocks_trades_against_a_strong_market(), test_themes_and_why()

### Community 51 - "newsfeed.py"
Cohesion: 0.23
Nodes (5): fetch_all(), _fetch_one(), parse(), _when(), test_rss_parsing()

### Community 52 - "orderflow.py"
Cohesion: 0.27
Nodes (7): features(), latest(), signals(), days(), test_latest_needs_history(), test_spring_and_upthrust(), test_squeeze_breakout_with_volume_gives_a_call()

### Community 53 - "expectations.py"
Cohesion: 0.20
Nodes (6): analysts(), day_move(), for_symbol(), hype(), run_up(), test_analysts_from_indmoney_details()

### Community 54 - "DuckDB Direct Data Loading"
Cohesion: 0.15
Nodes (13): 1. Custom DuckDB (User-Created), 2. OpenAlgo Historify DuckDB, Auto-Detection: Which Format?, Best Practices, DuckDB Direct Data Loading, DuckDB Pivot for Wide Format (Memory Efficient), Indicators and Signal Utilities Without openalgo.ta, load_from_custom_duckdb (+5 more)

### Community 55 - "requests"
Cohesion: 0.31
Nodes (4): daily_bars(), intraday_bars(), nse_lot_sizes(), yahoo_symbol()

### Community 56 - "chain"
Cohesion: 0.15
Nodes (14): affordable_option(), _fails(), lot_cost(), needs_next_month(), pick_option(), _chain(), test_budget_steps_out_of_the_money_until_one_lot_fits(), chain() (+6 more)

### Community 57 - "Equity Research Earnings Update"
Cohesion: 0.18
Nodes (9): Dependencies, Equity Research Earnings Update, Key Differences from Initiation Report, Output Specification, references/best-practices.md, references/report-structure.md, references/workflow.md, Resources (+1 more)

### Community 58 - "Steps"
Cohesion: 0.17
Nodes (11): Arguments, Important Notes, Step 1: Detect Operating System, Step 2: Create Virtual Environment, Step 3: TA-Lib System Dependency (Optional), Step 4: Install Python Packages, Step 5: Create Backtesting Folder, Step 6: Configure .env File (+3 more)

### Community 59 - "Position Sizing"
Cohesion: 0.29
Nodes (7): Best Practices, Percent Sizing (Most Popular), Position Sizing, Size Types, Target Percent (Portfolio Rebalancing), Value Sizing (Fixed Capital Per Trade), Whole Shares Only (Realistic)

### Community 60 - "OpenStatz Tearsheet Integration"
Cohesion: 0.17
Nodes (11): Basic Usage with VectorBT, Benchmark Options, Complete Backtest Integration Template, Console Metrics (numbers only, no UI), Import Alias: Use `ostz`, Not `os`, Important Notes, Installation, Key Metrics (ostz.stats) (+3 more)

### Community 61 - "Common Backtesting Pitfalls"
Cohesion: 0.17
Nodes (12): 10. Selection Bias in Symbol Choice, 1. Lookahead Bias, 2. Survivorship Bias, 3. Overfitting / Curve Fitting, 4. Data Snooping, 5. Unrealistic Transaction Costs, 6. Ignoring Slippage and Market Impact, 7. Insufficient Trade Count (+4 more)

### Community 62 - "spurt"
Cohesion: 0.08
Nodes (25): enabled, late_burst_x, late_until, market_flat_band_pct, market_min_pct, max_delta, max_spread_pct, min_delta (+17 more)

### Community 63 - "valuation.py"
Cohesion: 0.22
Nodes (7): assess(), fetch(), main(), _metric(), path_for(), snapshot(), test_valuation_against_sector_peers()

### Community 64 - "test_events.py"
Cohesion: 0.24
Nodes (11): classify(), material(), contract_expiry(), filing(), test_board_meeting_outcome_is_opened_for_results(), test_classify_real_filing_shapes(), test_contract_expiry_from_name(), test_material_filters_universe_and_date() (+3 more)

### Community 65 - "Evening review: 2026-11-14"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-14, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news+spurt vs preopen, Today (+1 more)

### Community 66 - "RateLimited"
Cohesion: 0.33
Nodes (4): _parse(), RateLimited, test_leaf_errors_unwraps_groups(), test_rate_limit_reply_raises()

### Community 67 - "Trading desk handover (updated 4 Nov 2026, end of the second long conversation)"
Cohesion: 0.18
Nodes (10): assess(), oi_type(), Changes 13-14 Nov 2026, How the user likes to work, One-time setup in a new session (do these before anything else, then tell the user in a few lines), Read next (only what the task needs), State on 12 Nov 2026 (evening), The user's standing decisions (do not change without asking) (+2 more)

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

### Community 72 - "Trading desk"
Cohesion: 0.15
Nodes (12): Backtesting, Evening review, Morning brief (about 09:00-09:15 IST, before starting the watcher), On a COMMODITY line (a commodity moved 3% or more today), On a FORECAST line (the Data Analyzer's outlook for a stock turned strong), On a NEWS line (a material NSE filing: rating, order, deal, regulatory, management, guidance), On a POLICY line (a regulator or the government changed the rules), On a SHOCK line (a market-wide rally or crash on big news) (+4 more)

### Community 73 - "figures_from_text"
Cohesion: 0.15
Nodes (11): clean_ocr_numbers(), fetch_feed(), figures_from_text(), highlights(), main(), results_summary(), score_results(), test_ocr_rows_are_cleaned_and_checked() (+3 more)

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
Cohesion: 0.22
Nodes (9): 1. Monte Carlo Simulation (Trade Shuffling), 2. Noise Test (Price Perturbation), 3. Parameter Sensitivity (Neighbor Test), 4. Entry/Exit Delay Test, 5. Cross-Symbol Validation, 6. Time Period Stability, Best Practices, Robustness Scorecard (+1 more)

### Community 78 - "Evening review: 2026-10-27"
Cohesion: 0.20
Nodes (9): All paper trades so far, Evening review: 2026-10-27, Movers setups stopped by the News Guard: 2, Ready to change the strategy?, Rules only vs Claude-confirmed, Setups held while a trade was open: 1, Team scoreboard: movers vs news, Today (+1 more)

### Community 79 - "Evening review: 2026-11-03"
Cohesion: 0.20
Nodes (9): AI helper's views (observe only): 17 closed trades, All paper trades so far, Evening review: 2026-11-03, Movers setups stopped by the News Guard: 1, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt, Today (+1 more)

### Community 80 - "Strategy changes"
Cohesion: 0.09
Nodes (21): 10 Nov 2026: one desk (user: "rewire it, one strong team is enough"), 12 Nov: spurt candidates retried after a data error, 14 Nov 2026 (evening): no time limits, overnight gauge, commodity guard on news+spurt (user), 14 Nov 2026: News + Spurt merged into one team (user), 14 Nov 2026: spurt team trades big late bursts (user's idea), 15 Nov 2026: ADR team (user's regime plan), fifth book, 2026-10-31: Probability Analyzer added in observe mode (user's request), 2026-10-31: Trade News Monitor added in observe mode (user's request) (+13 more)

### Community 81 - "test_expectations.py"
Cohesion: 0.22
Nodes (8): assess(), as_extra(), closes(), test_assess_labels(), test_hype_counts_news_before_the_event(), test_run_up_measures_against_nifty_before_the_event(), test_valuation_extra_observe_and_score(), test_valuation_feeds_priced_in()

### Community 82 - "json"
Cohesion: 0.26
Nodes (5): available(), _parse(), review(), load(), refresh()

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

### Community 90 - "classify"
Cohesion: 0.32
Nodes (3): classify(), own_items(), test_newsspurt_verdicts()

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

### Community 96 - "Evening review: 2026-11-06"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 1 closed trades, AI helper's views (observe only): 36 closed trades, All paper trades so far, Evening review: 2026-11-06, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

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

### Community 101 - "Evening review: 2026-11-09"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 42 closed trades, All paper trades so far, Evening review: 2026-11-09, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

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
Cohesion: 0.33
Nodes (6): Best Practices, Combined: Trailing Stop + Take Profit, Fixed Stop Loss + Take Profit, Stop Loss & Take Profit, Stop Loss Variations Summary, Trailing Stop Loss

### Community 108 - "VectorBT Backtesting Expert Skill"
Cohesion: 0.29
Nodes (7): Critical Rules, Environment, Modular Rule Files, Quick Template: DuckDB Backtest Script, Quick Template: Standard Backtest Script, Strategy Templates (in rules/assets/), VectorBT Backtesting Expert Skill

### Community 109 - "charges"
Cohesion: 0.29
Nodes (7): charges, brokerage_per_order, exchange_txn_pct, gst_pct, sebi_per_crore, stamp_buy_pct, stt_sell_pct

### Community 110 - "gap_recovery"
Cohesion: 0.18
Nodes (11): enabled, from, min_bounce_pct, min_gap_pct, targets, until, auto_trade, capital (+3 more)

### Community 111 - "macro"
Cohesion: 0.29
Nodes (7): macro, crude_move_pct, crude_points, rupee_move_pct, rupee_points, sector_points, sector_trend_pct

### Community 112 - "shock"
Cohesion: 0.29
Nodes (7): shock, breadth_share, extreme_pct, move_pct, news_count, news_hours, vix_jump_pct

### Community 113 - "Evening review: 2026-11-11"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-11, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

### Community 114 - "early_signals"
Cohesion: 0.33
Nodes (4): early_signals(), _candles(), test_early_signals_need_volume_and_the_order_book(), test_chart_reader_climax_absorption_and_momentum_fade()

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
Cohesion: 0.33
Nodes (6): carry, carry_puts, enabled, min_days_to_expiry, open_after, teams

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

### Community 138 - "backtest_trade_news.py"
Cohesion: 0.33
Nodes (5): implied_vol(), main(), parse_contract(), replay(), years()

### Community 139 - "valuation"
Cohesion: 0.50
Nodes (4): valuation, against_points, agree_points, mode

### Community 141 - "Evening review: 2026-11-12"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-12, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

### Community 142 - "test_spurt.py"
Cohesion: 0.17
Nodes (9): check_market_alignment(), check_option_limits(), gap_setup(), Gapped, test_gap_recovery_buys_the_bounce_on_the_preopen_team(), test_gap_recovery_skips_a_gap_that_holds(), test_pure_spurt_multiweek_context(), test_pure_spurt_option_limits() (+1 more)

### Community 149 - "Evening review: 2026-11-13"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-13, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

### Community 150 - "first_signal"
Cohesion: 0.14
Nodes (12): check_multiweek_context(), fetch(), first_signal(), level_note(), main(), prepare(), save_snapshot(), scan() (+4 more)

### Community 151 - "Evening review: 2026-11-05"
Cohesion: 0.22
Nodes (8): AI helper's views (observe only): 28 closed trades, All paper trades so far, Evening review: 2026-11-05, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today, Where it wins and loses

### Community 152 - "numpy"
Cohesion: 0.46
Nodes (3): bootstrap_sharpe(), main(), perf()

### Community 153 - "commodities.py"
Cohesion: 0.40
Nodes (3): assess(), shocks(), test_commodities_agent()

### Community 154 - "Long + Short Backtesting"
Cohesion: 0.40
Nodes (4): Best Practices, Compare Long-Only vs Short-Only vs Both, Long + Short Backtesting, Simultaneous Long and Short

### Community 155 - "stretch"
Cohesion: 0.50
Nodes (4): stretch, enabled, targets, week_pct

### Community 156 - "parse_nse"
Cohesion: 0.17
Nodes (8): bar_burst(), fetch_nse(), live_signal(), _num(), parse_nse(), usual_now(), test_nse_live_page_and_live_signal(), test_parse_nse_reads_numbers_with_units()

### Community 157 - "Futures Backtesting (Lot Size)"
Cohesion: 0.67
Nodes (3): Futures Backtesting (Lot Size), Futures Fee Structure, Index Futures & Options Lot Sizes (SEBI Revised, Effective 31 Dec 2025)

### Community 160 - "cycle"
Cohesion: 0.36
Nodes (7): test_save_trades_preserves_concurrent_verdicts_and_external_trades(), test_watcher_signals_then_exits(), cycle(), exits_only(), load_trades(), save_trades(), _trade_key()

### Community 167 - "mover_forecast.py"
Cohesion: 0.31
Nodes (5): forecast(), preopen_gaps(), results_move(), results_since_last_close(), typical_move()

### Community 168 - "adr"
Cohesion: 0.25
Nodes (8): auto_trade, capital, enabled, from, max_open_trades, targets, until, adr

### Community 169 - "backtest/SKILL.md"
Cohesion: 0.33
Nodes (5): Arguments, Available Strategies, Benchmark Rules, Example Usage, Instructions

### Community 170 - "monthly_expiry"
Cohesion: 0.33
Nodes (3): last_tuesday(), monthly_expiry(), test_expiry_is_last_tuesday_and_rolls()

### Community 171 - "check_fo_activity"
Cohesion: 0.40
Nodes (3): check_fo_activity(), check_preopen_profile(), test_pure_spurt_preopen_and_fo_activity()

### Community 172 - "adjust_forecast"
Cohesion: 0.33
Nodes (4): adjust_forecast(), reaction(), On a RESULT line (a company in our list just filed results on NSE), test_reaction_and_forecast_adjustment()

### Community 176 - "4. The two teams"
Cohesion: 0.67
Nodes (3): 4.1 Movers team, step by step (`watcher.scan`), 4.2 News team, step by step (`watcher.news_team`), 4. The two teams

## Knowledge Gaps
- **1 isolated node(s):** `python`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1337 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_config()` connect `load_config` to `probability.py`, `announcements.py`, `preopen.py`, `watcher.py`, `ai_helper.py`, `news_team`, `backtest_trade_news.py`, `reset_daily`, `scan`, `pandas`, `test_spurt.py`, `reaction.py`, `review.py`, `first_signal`, `plan`, `test_intel.py`, `overnight.py`, `test_teams.py`, `analyzer.py`, `FakeIndMoney`, `mover_forecast.py`, `indicators.py`, `expectations.py`, `valuation.py`, `test_events.py`, `figures_from_text`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `scan()` (e.g. with `4.1 Movers team, step by step (`watcher.scan`)` and `.candles()`) actually correct?**
  _`scan()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `python` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `probability.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0858843537414966 - nodes in this community are weakly interconnected._
- **Why does `scan()` connect `scan` to `load_config`, `watcher.py`, `news_team`, `plan`, `news.py`, `commodities.py`, `analyzer.py`, `candles.py`, `cycle`, `sector_of`, `FakeIndMoney`, `as_extra`, `indicators.py`, `check`, `4. The two teams`, `daymode.py`, `stretch_week_pct`, `Trading desk handover (updated 4 Nov 2026, end of the second long conversation)`, `shock.py`, `test_expectations.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Should `announcements.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11594202898550725 - nodes in this community are weakly interconnected._
- **Should `preopen.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07641196013289037 - nodes in this community are weakly interconnected._