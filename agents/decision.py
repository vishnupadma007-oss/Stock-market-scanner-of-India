"""Decision agent: combines every agent's view into TRADE / WATCH / SKIP."""


def decide(side: str, regime: dict, chart: dict, risk: dict, ai: dict | None, cfg: dict,
           extras: list[dict] | None = None) -> dict:
    """extras: views from the Macro and News agents, each {"points", "notes", "block"}."""
    reasons = []
    side_ok = regime["gainers_ok"] if side == "gainer" else regime["losers_ok"]
    if not side_ok:
        return {"verdict": "SKIP", "score": chart["score"],
                "reasons": ["Market regime does not favour this side today."]}

    for extra in extras or []:
        if extra.get("block"):
            return {"verdict": "SKIP", "score": chart["score"], "reasons": extra["notes"]}

    threshold = cfg["min_chart_score"] + regime["threshold_adj"]
    score = chart["score"] + sum(e.get("points", 0) for e in extras or [])
    if extras:
        reasons.extend(n for e in extras for n in e.get("notes", []))
    if ai and ai.get("verdict") in ("TRADE", "WATCH", "SKIP"):
        if ai["verdict"] == "SKIP":
            return {"verdict": "SKIP", "score": score,
                    "reasons": [f"AI analyst vetoed: {ai.get('reason', '')}"]}
        score = round(0.6 * chart["score"] + 0.4 * ai["confidence"])
        reasons.append(f"Chart {chart['score']} + AI {ai['confidence']} -> combined {score}")

    if score >= threshold and risk["allowed"]:
        verdict = "TRADE"
    elif score >= threshold - 15:
        verdict = "WATCH"
        if score >= threshold:
            reasons.extend(risk["blocks"])
    else:
        verdict = "SKIP"
    reasons.append(f"Score {score} vs required {threshold}.")
    return {"verdict": verdict, "score": score, "reasons": reasons}
