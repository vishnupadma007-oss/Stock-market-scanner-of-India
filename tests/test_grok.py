from agents import grok


def test_output_text_reads_the_responses_api_shape():
    payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ok": true}'}]}]}
    assert grok.output_text(payload) == '{"ok": true}'


def test_no_key_means_no_call(monkeypatch):
    monkeypatch.setattr(grok.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert grok.ask("hi") is None and not grok.available({})


def test_results_figures_from_grok_reply(monkeypatch):
    monkeypatch.setattr(grok, "ask", lambda *a, **k:
                        'Sure: {"revenue": [38764.4, 36624.7, 37203.0], "profit": [3934.0, 3711.5, 3069.2], "basis": "consolidated"}')
    f = grok.results_figures("...text...", "MARUTI")
    assert f["revenue"]["yoy_pct"] == 4.2 and f["profit"]["quarter"] == 3934.0 and f["profit"]["source"] == "grok"
    monkeypatch.setattr(grok, "ask", lambda *a, **k: '{"revenue": [null, 1, 2], "profit": "n/a"}')
    assert grok.results_figures("x", "MARUTI") == {}  # never guessed


def test_signal_view_is_logged_not_acted_on(monkeypatch, tmp_path):
    monkeypatch.setattr(grok, "VERDICTS", tmp_path / "v.csv")
    monkeypatch.setattr(grok, "ask", lambda *a, **k: '{"verdict": "SKIP", "confidence": 70, "reason": "Late entry."}')
    grok.log_verdict({"team": "news", "symbol": "HINDUNILVR", "contract": "X"})
    rows = (tmp_path / "v.csv").read_text().splitlines()
    assert len(rows) == 2 and "SKIP" in rows[1] and "Late entry." in rows[1]


def test_daily_cap(monkeypatch):
    grok._calls.update(day=None, n=0)
    c = {**grok.DEFAULTS, "max_calls_per_day": 2}
    assert grok._budget(c) and grok._budget(c) and not grok._budget(c)
