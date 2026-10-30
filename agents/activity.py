"""F&O Activity reader: who is building positions right now, from NSE's live OI-spurts page.

One free NSE call covers all F&O stocks: today's change in open interest (all futures and
options) and the stock's live price. Read together they say what traders are doing:
  OI up   + price up   = long build-up   (fresh buying with conviction)
  OI up   + price down = short build-up  (fresh selling with conviction)
  OI down + price up   = short covering  (shorts running, often short-lived)
  OI down + price down = long unwinding  (longs giving up)

The news team uses it to cross-check a news idea early: a build-up the news's way means
derivatives traders are already acting on it, so the team may enter before the full 0.5%
confirmation, and it counts towards the Trend Checker's score.

Why not NSE's volume-spurts page: it lists only the 25 biggest spurts in the whole market
(small caps at 20-50x volume); on 27 Oct 2026 none of our 76 F&O stocks appeared all day.

Untested on history (NSE keeps no past OI-spurt pages): every reading is saved to
journal/intel/activity-<date>.jsonl so it can be judged after a few weeks. On the monthly
expiry day OI falls as positions roll over, so readings are less reliable that day.

    python -m agents.activity          # current build-ups in our stocks
"""
import json
from datetime import date, datetime
from pathlib import Path

from .preopen import _get

URL = "https://www.nseindia.com/api/live-analysis-oi-spurts-underlyings"
DIR = Path(__file__).resolve().parents[1] / "journal" / "intel"  # git-ignored by day, committed each evening


def kind(oi_pct: float, price_pct: float) -> str:
    if oi_pct >= 0:
        return "long build-up" if price_pct >= 0 else "short build-up"
    return "short covering" if price_pct >= 0 else "long unwinding"


def parse(payload, universe: set[str], prev_close: dict[str, float]) -> dict:
    """{symbol: {oi_pct, price_pct, kind, volume, price}} for our stocks. The page has no previous
    close, so the price move is measured against the close saved with today's pre-open."""
    rows = payload.get("data") if isinstance(payload, dict) else payload
    out = {}
    for r in rows or []:
        sym, price, pc = r.get("symbol"), r.get("underlyingValue"), prev_close.get(r.get("symbol"))
        if sym not in universe or not price or not pc or r.get("avgInOI") is None:
            continue
        oi, move = round(float(r["avgInOI"]), 2), round((float(price) / float(pc) - 1) * 100, 2)
        out[sym] = {"oi_pct": oi, "price_pct": move, "kind": kind(oi, move),
                    "volume": r.get("volume"), "price": price}
    return out


def confirms(row: dict | None, direction: str, min_oi_pct: float = 5.0, min_price_pct: float = 0.2) -> bool:
    """A build-up the news's way: OI up `min_oi_pct`+ and the price already moving that way."""
    if not row:
        return False
    sign = 1 if direction == "up" else -1
    return row["oi_pct"] >= min_oi_pct and sign * row["price_pct"] >= min_price_pct


def note(row: dict) -> str:
    return f"F&O activity: {row['kind']} (OI {row['oi_pct']:+.1f}%, price {row['price_pct']:+.1f}%)"


def fetch(universe, prev_close: dict[str, float]) -> dict:
    return parse(_get(URL), set(universe), prev_close)


def save(day: date, now: datetime, rows: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    with open(DIR / f"activity-{day.isoformat()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": now.strftime("%H:%M:%S"), "rows": rows}) + "\n")


def main() -> None:
    from . import preopen
    from .config import load_config
    pre = preopen.load("preopen", date.today()) or {}
    rows = fetch(load_config()["universe"], {s: p["prev_close"] for s, p in pre.items() if p.get("prev_close")})
    for sym, r in sorted(rows.items(), key=lambda kv: -abs(kv[1]["oi_pct"]))[:20]:
        print(f"{sym:12} {note(r)}")


if __name__ == "__main__":
    main()
