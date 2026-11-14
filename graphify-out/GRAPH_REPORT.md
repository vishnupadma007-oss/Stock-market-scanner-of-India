# Graph Report - Stock-market-scanner-of-India  (2026-11-14)

## Corpus Check
- 313 files · ~279,208 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 74 file(s) not represented in the graph (top: .jsonl 41, .csv 30, (none) 3)

## Summary
- 2443 nodes · 4909 edges · 176 communities (154 shown, 22 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 55 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `efb97c76`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- probability.py
- announcements.py
- activity.py
- load_config
- watcher.py
- ai_helper.py
- Trusted News Sources for Market Analysis
- news_team
- Market Event Patterns and Market Reactions
- spurt.py
- poll_filings
- config.yaml
- scan
- options.py
- preopen.py
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
- record_call
- overnight.py
- test_teams.py
- analyzer.py
- candles.py
- carry.py
- indmoney.py
- expectations.py
- Complete Indicator Catalog (100+)
- Trading Desk: Complete Guide (27 Oct 2026)
- Report Structure and Templates
- Crypto Market Transaction Costs
- FakeIndMoney
- Market News Analyst
- test_policy.py
- re
- US Market Transaction Costs
- is_trading_day
- check
- read_chart
- pathlib
- Creating Indicators & Signals
- daymode.py
- market.py
- newsfeed.py
- orderflow.py
- main
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
- test_events.py
- Evening review: 2026-11-14
- RateLimited
- Trading desk handover (updated 4 Nov 2026, end of the second long conversation)
- shock.py
- Performance Analysis
- Plotting
- VectorBT Simulation Modes
- build_history
- figures_from_text
- Best Practices, Examples, and Quality Guidelines
- Detailed Workflow for Earnings Updates
- Indian Market Transaction Costs
- Robustness Testing
- Evening review: 2026-10-27
- Evening review: 2026-11-03
- Strategy changes
- test_activity.py
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
- preopen
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
- candles
- psychology
- Live
- forecast
- test_overnight.py
- backtest/SKILL.md
- gapfollow.py
- check_fo_activity
- leaf_errors
- check_option_limits
- test_preopen_idea_needs_the_move_to_continue_after_the_open

## God Nodes (most connected - your core abstractions)
1. `load_config()` - 73 edges
2. `scan()` - 53 edges
3. `news_team()` - 50 edges
4. `spurt_entries()` - 43 edges
5. `plan()` - 42 edges
6. `IndMoney` - 41 edges
7. `news` - 32 edges
8. `gap_recovery_entries()` - 31 edges
9. `Quiet volume spurt (user's idea, 28 Oct 2026)` - 28 edges
10. `suggest_contract()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Available Strategies` --references--> `rsi()`  [INFERRED]
  .claude/skills/backtest/SKILL.md → agents/indicators.py
- `Evening review` --references--> `score()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/sector_results.py
- `On a RESULT line (a company in our list just filed results on NSE)` --references--> `highlights()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/announcements.py
- `Overnight carry (user, 3 Nov)` --references--> `should_carry()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/carry.py
- `On a RESULT line (a company in our list just filed results on NSE)` --references--> `reaction()`  [INFERRED]
  .claude/skills/trading-desk/SKILL.md → agents/expectations.py

## Import Cycles
- 2-file cycle: `agents/mover_forecast.py -> agents/overnight.py -> agents/mover_forecast.py`

## Communities (176 total, 22 thin omitted)

### Community 0 - "probability.py"
Cohesion: 0.09
Nodes (31): assess(), base_rate(), bs_price(), _bucket(), _charges_fast(), features(), fit(), log() (+23 more)

### Community 1 - "announcements.py"
Cohesion: 0.11
Nodes (14): _download(), fetch_feed(), get_nse_session(), highlights(), main(), material(), _ocr_page(), ocr_text() (+6 more)

### Community 2 - "activity.py"
Cohesion: 0.19
Nodes (9): confirms(), fetch(), kind(), main(), note(), parse(), save(), test_confirms_needs_rising_oi_and_price_the_news_way() (+1 more)

### Community 3 - "load_config"
Cohesion: 0.10
Nodes (32): load_config(), hist_vol(), intraday_sigma_per_min(), suggest_contract(), plan(), first_signal(), prepare(), main() (+24 more)

### Community 4 - "watcher.py"
Cohesion: 0.09
Nodes (25): set_hourly_budget(), results_calendar(), emit(), filings_track(), gap_recovery_entries(), information_track(), lag_seconds(), log_filing() (+17 more)

### Community 5 - "ai_helper.py"
Cohesion: 0.08
Nodes (33): api_key(), ask(), available(), _budget(), _conf(), context_info(), gemini_text(), _json() (+25 more)

### Community 6 - "Trusted News Sources for Market Analysis"
Cohesion: 0.04
Nodes (44): Barron's, Best Practices, Bloomberg, Central Bank Researchers, Central Banks and Government Agencies, China-Specific, CNBC, Commodity Markets (+36 more)

### Community 7 - "news_team"
Cohesion: 0.10
Nodes (35): hit_probability(), analyzing-regulatory-event-impacts (CaseMark/skills, Apache-2.0), Third-party skills, check_rules(), find_key(), main(), open_trade(), setup() (+27 more)

### Community 8 - "Market Event Patterns and Market Reactions"
Cohesion: 0.05
Nodes (40): 2008 Financial Crisis, 2022 Inflation Shock, Bank of Japan (BOJ), Banking Sector Earnings, Central Bank Monetary Policy Events, Commodity-Specific Events, Corporate Defaults / Distress, Corporate Earnings Events (+32 more)

### Community 9 - "spurt.py"
Cohesion: 0.24
Nodes (5): bar_burst(), check_institutional_timing(), late_burst_ok(), usual_now(), test_bar_burst_and_late_window()

### Community 10 - "poll_filings"
Cohesion: 0.08
Nodes (21): recent_items(), stock_key(), append(), load(), path_for(), typical_move(), test_result_reported_once_per_company_unless_figures_arrive_later(), test_forecast_event_carries_priced_in() (+13 more)

### Community 11 - "config.yaml"
Cohesion: 0.06
Nodes (33): assumed_spread_pct, capital, commodity_guard, entry_end, entry_start, exit_check_seconds, filings_poll_seconds, forecast_capture (+25 more)

### Community 12 - "scan"
Cohesion: 0.09
Nodes (13): main(), go(), IndMoney, check(), 4.1 Movers team, step by step (`watcher.scan`), 4.2 News team, step by step (`watcher.news_team`), 4. The two teams, test_stretch_week_pct() (+5 more)

### Community 13 - "options.py"
Cohesion: 0.07
Nodes (19): exit_for_net_target(), round_trip_charges(), black_scholes(), BSResult, implied_volatility(), last_tuesday(), monthly_expiry(), _ncdf() (+11 more)

### Community 14 - "preopen.py"
Cohesion: 0.24
Nodes (12): preopen_gaps(), fetch_preopen(), fetch_spurts(), _get(), load(), main(), parse_preopen(), parse_spurts() (+4 more)

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
Cohesion: 0.12
Nodes (19): add_surprises(), _clip(), dataset(), expected_market_gap(), features_for(), fit(), forecast(), load_history() (+11 more)

### Community 20 - "NLP Earnings Sentiment"
Cohesion: 0.07
Nodes (24): Beyond Sentiment, Earnings Call Structure Matters, FinBERT and Financial NLP Models, Usage Pattern, Validation, Why Domain Models, Caveats, Documented Red-Flag Patterns (research-backed) (+16 more)

### Community 21 - "review.py"
Cohesion: 0.06
Nodes (41): acall(), go(), call(), daily_history(), go(), _f(), history_frame(), list_tools() (+33 more)

### Community 22 - "plan"
Cohesion: 0.09
Nodes (17): decide(), reversal_target(), assess(), _ret(), test_contract_side(), test_decision_keeps_extras_with_ai(), test_decision_respects_regime_and_ai_veto(), test_lot_too_big_for_10k_is_blocked() (+9 more)

### Community 23 - "Quiet volume spurt (user's idea, 28 Oct 2026)"
Cohesion: 0.06
Nodes (35): Are we late on results? (user's question, 10 Nov 2026) - 29 results filings with a clear read, 19 Oct - 6 Nov, ATM vs one-strike-ITM (2026-10-19, macro on, same 60 days), Backtest: mover-reversal options, 2026-08 to 2026-10 (60 trading days), Can the news predict the move? (user's question, 10 Nov 2026) - 164 live news ideas, 21 Oct - 6 Nov, measured on 5-minute prices, Early chart exit (user's idea, 30 Oct 2026), Enhancement pack chart signals (27 Oct 2026), same 60-day data, Gap-recovery idea and results-gap, 26 Oct 2026, Movers "exhaustion reversal" proposal (user, 13 Nov 2026): `backtest_movers_exhaust.py` (+27 more)

### Community 24 - "test_intel.py"
Cohesion: 0.16
Nodes (19): to_intel(), make_item(), tone(), item(), test_analyzer_accepts_ist_aware_time(), test_analyzer_needs_agreement_and_fades_old_news(), test_gst_input_tax_credit_is_not_itc_ltd(), test_linking_and_tone() (+11 more)

### Community 25 - "news.py"
Cohesion: 0.24
Nodes (8): assess(), headline_date(), next_session(), previous_session(), volume_spike(), test_news_agent_uses_nse_filings(), test_news_results_and_headlines(), test_volume_spike_is_sudden_pressure()

### Community 26 - "record_call"
Cohesion: 0.27
Nodes (8): calls_last_hour(), record_call(), _usage(), _wait_turn(), test_call_budget_counts_rolling_hour(), test_calls_are_paced_evenly(), three(), test_details_calls_cost_one_per_instrument()

### Community 27 - "overnight.py"
Cohesion: 0.25
Nodes (8): _daily(), evaluate(), fit(), forecast(), gap_table(), load_model(), main(), predict_gap()

### Community 28 - "test_teams.py"
Cohesion: 0.15
Nodes (16): FakeIndMoney, idea(), test_free_money_is_split_over_the_empty_slots(), test_news_team_enters_early_on_volume_and_order_book(), candles(), quotes(), test_news_team_skips_ideas_whose_priced_in_check_failed(), test_news_team_trades_when_price_confirms() (+8 more)

### Community 29 - "analyzer.py"
Cohesion: 0.19
Nodes (12): as_extra(), main(), market_hours_between(), market_mood(), _mean_tone(), _parse_time(), stock_view(), _top() (+4 more)

### Community 30 - "candles.py"
Cohesion: 0.17
Nodes (11): as_extra(), detect(), main(), _parts(), recent(), test(), frame(), test_bearish_engulfing_after_a_rise() (+3 more)

### Community 31 - "carry.py"
Cohesion: 0.08
Nodes (27): expiry_of(), is_carried(), market_open(), overnight_exit(), _own_filings(), should_carry(), Backtesting, Evening review (+19 more)

### Community 32 - "indmoney.py"
Cohesion: 0.18
Nodes (10): access_token(), _client_auth(), finish_login(), _load(), LoginRequired, main(), refresh(), _save() (+2 more)

### Community 33 - "expectations.py"
Cohesion: 0.05
Nodes (35): adjust_forecast(), analysts(), assess(), day_move(), for_symbol(), hype(), reaction(), run_up() (+27 more)

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
Nodes (23): candles_frame(), FakeIndMoney, signals(), test_account_reinvests_profit_and_reserves_open_trades(), test_busy_desk_holds_new_setups(), test_candles_frame(), test_carry_keeps_a_trade_overnight_and_sells_it_next_day(), test_consolidated_results_preferred_over_standalone() (+15 more)

### Community 39 - "Market News Analyst"
Cohesion: 0.11
Nodes (17): Analysis Workflow, Common Pitfalls to Avoid, Important Notes, Key Analysis Principles, Market News Analyst, Output, Overview, Prerequisites (+9 more)

### Community 40 - "test_policy.py"
Cohesion: 0.17
Nodes (16): _one_per_story(), assess(), main(), to_intel(), hits(), test_delay_or_softening_is_mild_relief(), test_economists_expectations_are_talk(), test_irdai_commission_caps_hit_policybazaar_hardest() (+8 more)

### Community 42 - "re"
Cohesion: 0.24
Nodes (6): commentary(), is_meet(), items_from_rows(), _negated(), sectors_in(), symbols_in()

### Community 43 - "US Market Transaction Costs"
Cohesion: 0.12
Nodes (16): Best Practices, Data Source for US Markets, Fee Summary by Segment, FINRA Trading Activity Fee (Sell-Side Only), OCC Clearing Fee (Options Only), Popular US Futures Contract Specifications, Quick Reference: Default Fee Constants, Regulatory Fee Details (+8 more)

### Community 44 - "is_trading_day"
Cohesion: 0.36
Nodes (5): holiday_name(), is_trading_day(), previous_trading_day(), test_holidays_and_expiry(), _next_session()

### Community 45 - "check"
Cohesion: 0.23
Nodes (10): check(), irdai_items(), test_headlines_describing_the_move_do_not_block(), test_policybazaar_bounce_is_blocked(), test_quiet_stock_passes(), test_results_and_regulatory_filings_block_any_side(), test_results_due_today_blocks_both_sides(), test_same_news_does_not_block_a_put() (+2 more)

### Community 46 - "read_chart"
Cohesion: 0.15
Nodes (9): candle_png(), _mirror(), read_chart(), _today(), ema(), rsi(), vwap(), read_trend() (+1 more)

### Community 47 - "pathlib"
Cohesion: 0.09
Nodes (12): candidates(), day_frame(), load(), main(), run(), summary(), trade(), calc_cagr() (+4 more)

### Community 48 - "Creating Indicators & Signals"
Cohesion: 0.14
Nodes (14): ATR (Average True Range), Bollinger Bands Strategy (Default: OpenAlgo ta), Complete OpenAlgo ta Indicator Reference (Default), Creating Indicators & Signals, CRITICAL RULE: OpenAlgo ta by Default, TA-Lib Only on Request, EMA Crossover Strategy (Default: OpenAlgo ta), Fallback: Standalone DuckDB Without OpenAlgo Installed, MACD Strategy (Default: OpenAlgo ta) (+6 more)

### Community 49 - "daymode.py"
Cohesion: 0.29
Nodes (3): apply(), load(), test_day_mode()

### Community 50 - "market.py"
Cohesion: 0.24
Nodes (7): context(), headwind(), main(), theme_of(), item(), test_headwind_blocks_trades_against_a_strong_market(), test_themes_and_why()

### Community 51 - "newsfeed.py"
Cohesion: 0.15
Nodes (8): load(), refresh(), fetch_all(), _fetch_one(), parse(), _when(), one(), test_rss_parsing()

### Community 52 - "orderflow.py"
Cohesion: 0.27
Nodes (7): features(), latest(), signals(), days(), test_latest_needs_history(), test_spring_and_upthrust(), test_squeeze_breakout_with_volume_gives_a_call()

### Community 53 - "main"
Cohesion: 0.31
Nodes (7): main(), compare(), load(), path(), save(), stock_note(), _overnight()

### Community 54 - "DuckDB Direct Data Loading"
Cohesion: 0.15
Nodes (13): 1. Custom DuckDB (User-Created), 2. OpenAlgo Historify DuckDB, Auto-Detection: Which Format?, Best Practices, DuckDB Direct Data Loading, DuckDB Pivot for Wide Format (Memory Efficient), Indicators and Signal Utilities Without openalgo.ta, load_from_custom_duckdb (+5 more)

### Community 55 - "data.py"
Cohesion: 0.10
Nodes (13): daily_bars(), intraday_bars(), nse_lot_sizes(), yahoo_symbol(), atr(), load(), log(), trades_on() (+5 more)

### Community 56 - "chain"
Cohesion: 0.18
Nodes (10): _fails(), needs_next_month(), pick_option(), chain(), leg(), test_day_before_expiry_always_rolls(), test_expiry_week_falls_back_to_next_month(), option_chain() (+2 more)

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

### Community 63 - "intraday"
Cohesion: 0.28
Nodes (6): intraday(), test_chart_reader_mirrors_for_losers(), test_chart_reader_sees_fading_gainer(), test_news_team_skips_when_the_chart_disagrees(), candles(), test_trend_checker_backs_or_blocks_the_news()

### Community 64 - "test_events.py"
Cohesion: 0.22
Nodes (12): change_pct(), classify(), contract_expiry(), filing(), test_board_meeting_outcome_is_opened_for_results(), test_change_pct_reads_loss_to_profit_as_a_rise(), test_classify_real_filing_shapes(), test_contract_expiry_from_name() (+4 more)

### Community 65 - "Evening review: 2026-11-14"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-14, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news+spurt vs preopen, Today (+1 more)

### Community 66 - "RateLimited"
Cohesion: 0.40
Nodes (3): _parse(), RateLimited, test_rate_limit_reply_raises()

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

### Community 72 - "build_history"
Cohesion: 0.18
Nodes (4): build_history(), measure(), reaction_day(), results_filings()

### Community 73 - "figures_from_text"
Cohesion: 0.18
Nodes (8): clean_ocr_numbers(), _extract_table(), figures_from_text(), _numbers(), plausible(), _row(), test_ocr_rows_are_cleaned_and_checked(), test_scanned_misreads_are_not_trusted()

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
Cohesion: 0.10
Nodes (20): 10 Nov 2026: one desk (user: "rewire it, one strong team is enough"), 12 Nov: spurt candidates retried after a data error, 14 Nov 2026 (evening): no time limits, overnight gauge, commodity guard on news+spurt (user), 14 Nov 2026: News + Spurt merged into one team (user), 14 Nov 2026: spurt team trades big late bursts (user's idea), 2026-10-31: Probability Analyzer added in observe mode (user's request), 2026-10-31: Trade News Monitor added in observe mode (user's request), 2026-11-03: News-forecast ("intel") trades paused; money and slots go to the quiet spurt (+12 more)

### Community 81 - "test_activity.py"
Cohesion: 0.33
Nodes (5): affordable_option(), lot_cost(), _chain(), test_budget_steps_out_of_the_money_until_one_lot_fits(), test_quotes_are_sent_in_batches_of_ten()

### Community 82 - "json"
Cohesion: 0.36
Nodes (4): available(), _parse(), review(), load_model()

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
Cohesion: 0.29
Nodes (7): enabled, from, min_bounce_pct, min_gap_pct, targets, until, gap_recovery

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

### Community 138 - "preopen"
Cohesion: 0.50
Nodes (4): auto_trade, capital, max_open_trades, preopen

### Community 139 - "valuation"
Cohesion: 0.50
Nodes (4): valuation, against_points, agree_points, mode

### Community 141 - "Evening review: 2026-11-12"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-12, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

### Community 142 - "test_spurt.py"
Cohesion: 0.18
Nodes (9): check_market_alignment(), check_news_quarantine(), gap_setup(), Gapped, test_gap_recovery_buys_the_bounce_on_the_preopen_team(), test_gap_recovery_skips_a_gap_that_holds(), test_news_quarantine_ignores_routine_news(), test_pure_spurt_news_quarantine() (+1 more)

### Community 149 - "Evening review: 2026-11-13"
Cohesion: 0.20
Nodes (9): AI context check on spurt entries (observe only): 2 closed trades, AI helper's views (observe only): 51 closed trades, All paper trades so far, Evening review: 2026-11-13, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today (+1 more)

### Community 150 - "first_signal"
Cohesion: 0.16
Nodes (9): check_multiweek_context(), fetch(), level_note(), main(), save_snapshot(), scan(), usual_curve(), test_level_note_reports_room_and_breakout() (+1 more)

### Community 151 - "Evening review: 2026-11-05"
Cohesion: 0.22
Nodes (8): AI helper's views (observe only): 28 closed trades, All paper trades so far, Evening review: 2026-11-05, Ready to change the strategy?, Rules only vs Claude-confirmed, Team scoreboard: movers vs news vs spurt vs preopen, Today, Where it wins and loses

### Community 152 - "numpy"
Cohesion: 0.43
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
Cohesion: 0.22
Nodes (6): fetch_nse(), live_signal(), _num(), parse_nse(), test_nse_live_page_and_live_signal(), test_parse_nse_reads_numbers_with_units()

### Community 157 - "Futures Backtesting (Lot Size)"
Cohesion: 0.67
Nodes (3): Futures Backtesting (Lot Size), Futures Fee Structure, Index Futures & Options Lot Sizes (SEBI Revised, Effective 31 Dec 2025)

### Community 167 - "forecast"
Cohesion: 0.33
Nodes (5): forecast(), results_move(), results_since_last_close(), test_mover_forecast_adds_preopen_gap_fade_candidates(), test_mover_forecast_lists_results_stocks_first()

### Community 168 - "test_overnight.py"
Cohesion: 0.33
Nodes (4): label(), test_gap_labels(), test_predict_gap_uses_beta_and_oil(), test_priced_in_gap_lowers_a_backed_spurt_target()

### Community 169 - "backtest/SKILL.md"
Cohesion: 0.33
Nodes (5): Arguments, Available Strategies, Benchmark Rules, Example Usage, Instructions

### Community 171 - "check_fo_activity"
Cohesion: 0.40
Nodes (3): check_fo_activity(), check_preopen_profile(), test_pure_spurt_preopen_and_fo_activity()

## Knowledge Gaps
- **1 isolated node(s):** `python`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1302 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_config()` connect `load_config` to `probability.py`, `announcements.py`, `activity.py`, `watcher.py`, `ai_helper.py`, `news_team`, `spurt.py`, `poll_filings`, `scan`, `options.py`, `preopen.py`, `test_spurt.py`, `reaction.py`, `review.py`, `first_signal`, `plan`, `test_intel.py`, `overnight.py`, `test_teams.py`, `analyzer.py`, `candles.py`, `expectations.py`, `FakeIndMoney`, `forecast`, `pathlib`, `main`, `data.py`, `test_events.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `scan()` (e.g. with `4.1 Movers team, step by step (`watcher.scan`)` and `.candles()`) actually correct?**
  _`scan()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `python` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `probability.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09142857142857143 - nodes in this community are weakly interconnected._
- **Why does `scan()` connect `scan` to `expectations.py`, `load_config`, `watcher.py`, `Trading desk handover (updated 4 Nov 2026, end of the second long conversation)`, `FakeIndMoney`, `news_team`, `shock.py`, `poll_filings`, `check`, `read_chart`, `daymode.py`, `data.py`, `plan`, `news.py`, `commodities.py`, `analyzer.py`, `candles.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Should `announcements.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11396011396011396 - nodes in this community are weakly interconnected._
- **Why does `4. The two teams` connect `scan` to `Trading Desk: Complete Guide (27 Oct 2026)`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._