"""NSE pre-open and volume-spurt readers (free NSE pages, no INDmoney calls).

Pre-open (09:00-09:08 order collection, final at ~09:08): each F&O stock's indicative opening
price (IEP), its change vs the previous close, and the buy/sell quantities left at 09:08.
It tells where a stock will OPEN, not where it will close: on 26 Oct 2026 only 23% of the
1%+ pre-open gaps kept going after the open (Infosys's results pulled all IT stocks down
before the open; the sector then rallied). Saved daily (journal/intel/preopen-<date>.json)
so pre-open vs outcome can be measured over weeks.

Volume spurts: stocks trading far above their 1-week average volume, an early sign that
something is happening (news the readers have not seen yet, a block deal, a rumour).

    python -m agents.preopen            # today's pre-open gaps and volume spurts for our stocks
"""
import json
from datetime import date
from pathlib import Path

from .announcements import get_nse_session

PREOPEN = "https://www.nseindia.com/api/market-data-pre-open?key=FO"
SPURTS = "https://www.nseindia.com/api/live-analysis-volume-gainers"
DIR = Path(__file__).resolve().parents[1] / "journal" / "intel"  # git-ignored by day, committed each evening


def _get(url: str):
    s = get_nse_session()
    r = s.get(url, timeout=20)
    if r.status_code in (401, 403):
        s.get("https://www.nseindia.com", timeout=10)
        r = s.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_preopen(payload: dict, universe: set[str]) -> dict:
    out = {}
    for row in payload.get("data") or []:
        m, d = row.get("metadata") or {}, ((row.get("detail") or {}).get("preOpenMarket") or {})
        sym = m.get("symbol")
        if sym not in universe or not m.get("previousClose"):
            continue
        buy, sell = float(d.get("totalBuyQuantity") or 0), float(d.get("totalSellQuantity") or 0)
        out[sym] = {"iep": m.get("lastPrice"), "gap_pct": round(float(m.get("pChange") or 0), 2),
                    "prev_close": m.get("previousClose"), "volume": d.get("finalQuantity"),
                    "buy_qty": buy, "sell_qty": sell,
                    "buy_sell_ratio": round(buy / sell, 2) if sell else None, "time": d.get("lastUpdateTime")}
    return out


def parse_spurts(payload, universe: set[str], min_ratio: float = 3.0) -> list[dict]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    out = []
    for r in rows or []:
        sym, avg = r.get("symbol"), float(r.get("week1AvgVolume") or 0)
        if sym in universe and avg > 0:
            ratio = float(r.get("volume") or 0) / avg
            if ratio >= min_ratio:
                out.append({"symbol": sym, "volume_x": round(ratio, 1), "change_pct": round(float(r.get("pChange") or 0), 2)})
    return sorted(out, key=lambda r: -r["volume_x"])


def fetch_preopen(universe) -> dict:
    return parse_preopen(_get(PREOPEN), set(universe))


def fetch_spurts(universe, min_ratio: float = 3.0) -> list[dict]:
    return parse_spurts(_get(SPURTS), set(universe), min_ratio)


def path(kind: str, day: date) -> Path:
    return DIR / f"{kind}-{day.isoformat()}.json"


def save(kind: str, day: date, data) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = path(kind, day).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path(kind, day))


def load(kind: str, day: date):
    p = path(kind, day)
    return json.loads(p.read_text()) if p.exists() else None


def main() -> None:
    from .config import load_config
    universe = load_config()["universe"]
    pre = fetch_preopen(universe)
    for sym, p in sorted(pre.items(), key=lambda kv: kv[1]["gap_pct"]):
        if abs(p["gap_pct"]) >= 1:
            print(f"{sym:11} pre-open {p['gap_pct']:+.2f}%  buy/sell {p['buy_sell_ratio']}")
    for s in fetch_spurts(universe):
        print(f"{s['symbol']:11} volume {s['volume_x']}x usual, {s['change_pct']:+.2f}%")


if __name__ == "__main__":
    main()
