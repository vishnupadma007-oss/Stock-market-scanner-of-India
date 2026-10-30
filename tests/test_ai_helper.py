from agents import ai_helper as ai


def test_output_text_reads_the_responses_api_shape():
    payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ok": true}'}]}]}
    assert ai.output_text(payload) == '{"ok": true}'


def test_no_key_means_no_call(monkeypatch):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert ai.ask("hi") is None and not ai.available({})


def test_results_figures_from_ai_reply(monkeypatch):
    monkeypatch.setattr(ai, "ask", lambda *a, **k:
                        'Sure: {"revenue": [38764.4, 36624.7, 37203.0], "profit": [3934.0, 3711.5, 3069.2], "basis": "consolidated"}')
    f = ai.results_figures("...text...", "MARUTI")
    assert f["revenue"]["yoy_pct"] == 4.2 and f["profit"]["quarter"] == 3934.0 and f["profit"]["source"] == "ai"
    monkeypatch.setattr(ai, "ask", lambda *a, **k: '{"revenue": [null, 1, 2], "profit": "n/a"}')
    assert ai.results_figures("x", "MARUTI") == {}  # never guessed


def test_signal_view_is_logged_not_acted_on(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, "VERDICTS", tmp_path / "v.csv")
    monkeypatch.setattr(ai, "ask", lambda *a, **k: '{"verdict": "SKIP", "confidence": 70, "reason": "Late entry."}')
    ai.log_verdict({"team": "news", "symbol": "HINDUNILVR", "contract": "X"})
    rows = (tmp_path / "v.csv").read_text().splitlines()
    assert len(rows) == 2 and "SKIP" in rows[1] and "Late entry." in rows[1]


def test_daily_cap(monkeypatch):
    ai._calls.update(day=None, n=0)
    c = {**ai.DEFAULTS, "max_calls_per_day": 2}
    assert ai._budget(c) and ai._budget(c) and not ai._budget(c)


def test_gemini_reply_text():
    payload = {"candidates": [{"content": {"parts": [{"text": '{"verdict": "TRADE"}'}]}}]}
    assert ai.gemini_text(payload) == '{"verdict": "TRADE"}'
