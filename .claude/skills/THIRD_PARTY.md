# Third-party skills

`backtest`, `optimize`, `quick-stats`, `setup`, `strategy-compare` and `vectorbt-expert` come from
[marketcalls/vectorbt-backtesting-skills](https://github.com/marketcalls/vectorbt-backtesting-skills)
(MIT licence, by Marketcalls), copied unchanged. Reviewed before install: no network calls
or credential handling beyond standard package installs and a gitignored `.env`.

`quantforge-ai` comes from [abhi15724/quantforge-ai](https://github.com/abhi15724/quantforge-ai)
(MIT licence, MANIQUANT AI), via the cryptoskill mirror listed on SkillsMP. Reviewed before
install: instructions plus one offline metrics script (numpy/pandas only), no network calls.
Its generic risk advice (stops, kill switch) is overridden by this project's no-stop-loss rule in CLAUDE.md.

`market-news-analyst` comes from [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)
(MIT licence, TraderMonty), copied without its test script. Reviewed before install: instructions
and reference guides only, uses web search, no keys. US-focused: the trading-desk morning brief
applies its commodity and geopolitics guides to Indian stocks.

Reviewed and not installed: tradermonty `earnings-trade-analyzer` (needs a paid US data key),
himself65 `finance-sentiment` (paid key, US social-media sentiment), `timesfm-forecasting`
(large price-forecasting model; no evidence it helps intraday reversals, heavy to run), wshobson/agents `backtesting-frameworks` (generic; covered by the above).

`trading-desk` is this project's own skill.
