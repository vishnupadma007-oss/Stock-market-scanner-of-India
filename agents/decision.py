"""Decision agent: combines every agent's view into TRADE / WATCH / SKIP.

Evaluates:
- Market Regime permission (hard filter)
- Extra veto blocks (results day, macro shocks)
- Base Technical Score (Chart Reader)
- Fundamental, Sentiment & Macro modifiers (extras)
- AI Analyst confirmation / veto
- Risk Manager sizing & timing feasibility
"""


def decide(side: str, regime: dict, chart: dict, risk: dict, ai: dict | None, cfg: dict,
           extras: list[dict] | None = None) -> dict:
    """extras: views from Macro, News, Commodities, Psychology, and Valuation agents.
    Each extra contains {"points": int, "notes": list[str], "block": bool}.
    """
    reasons = []
    side_ok = regime["gainers_ok"] if side == "gainer" else regime["losers_ok"]
    if not side_ok:
        return {
            "verdict": "SKIP",
            "score": chart["score"],
            "reasons": ["Market regime does not favour this side today."],
            "breakdown": {"chart": chart["score"], "extras": 0, "final": chart["score"]},
        }

    for extra in extras or []:
        if extra.get("block"):
            return {
                "verdict": "SKIP",
                "score": chart["score"],
                "reasons": extra["notes"],
                "breakdown": {"chart": chart["score"], "extras": 0, "final": chart["score"]},
            }

    threshold = cfg["min_chart_score"] + regime["threshold_adj"]
    extra_points = sum(e.get("points", 0) for e in extras or [])
    score = chart["score"] + extra_points

    if extras:
        reasons.extend(n for e in extras for n in e.get("notes", []))

    if ai and ai.get("verdict") in ("TRADE", "WATCH", "SKIP"):
        if ai["verdict"] == "SKIP":
            return {
                "verdict": "SKIP",
                "score": score,
                "reasons": [f"AI analyst vetoed: {ai.get('reason', '')}"],
                "breakdown": {"chart": chart["score"], "extras": extra_points, "final": score},
            }
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

    # Confidence grade
    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

    return {
        "verdict": verdict,
        "score": score,
        "grade": grade,
        "threshold": threshold,
        "reasons": reasons,
        "breakdown": {
            "chart": chart["score"],
            "extras": extra_points,
            "final": score,
        },
    }
