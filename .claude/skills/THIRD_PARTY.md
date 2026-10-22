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

`earnings-preview` and `earnings-analysis` come from Anthropic's
[financial-services](https://github.com/anthropics/financial-services) plugins (Apache 2.0),
copied unchanged. The trading desk uses earnings-preview for companies reporting soon and the
beat/miss-versus-expectations checklist from earnings-analysis when results land; the full
8-12 page report format is only for when the user asks for a report.

`nlp-earnings-sentiment` comes from [gajetoso/financeskills](https://github.com/gajetoso/financeskills)
(MIT, KOMVIA), without its eval files. Its finance-lexicon ideas (negation windows, uncertainty
words) are also built into `agents/intel.py`.

Reviewed and not installed: Anthropic `financial-statements` (bookkeeping, not investing),
OctagonAI earnings-call skills (need the paid Octagon data service), tradermonty `earnings-trade-analyzer` (needs a paid US data key),
himself65 `finance-sentiment` (paid key, US social-media sentiment), `timesfm-forecasting`
(large price-forecasting model; no evidence it helps intraday reversals, heavy to run), wshobson/agents `backtesting-frameworks` (generic; covered by the above).

`trading-desk` is this project's own skill.

## analyzing-regulatory-event-impacts (CaseMark/skills, Apache-2.0)

Source: https://github.com/CaseMark/skills/tree/HEAD/skills/capital/analyzing-regulatory-event-impacts
(installed 22 Oct 2026, unmodified, LICENSE included). Reviewed: instructions only, no scripts,
downloads or file operations. Used from the `policy-impact` skill for pending decisions (drafts,
consultation papers): outcome probabilities, expected value, market-implied vs own view.
Not applicable here: its stop-loss / hedge-trigger and position-sizing advice (the user chose no
stop-loss; sizing is fixed by `config.yaml`), and US agency base rates.
