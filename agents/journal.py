"""Journal agent: logs every TRADE/WATCH signal for later review (paper trading)."""
from pathlib import Path

import pandas as pd

JOURNAL = Path(__file__).resolve().parent.parent / "data" / "journal.csv"


def log(rows: list[dict]) -> None:
    if not rows:
        return
    new = pd.DataFrame(rows)
    old = load()
    if not old.empty:  # re-running the scan the same day should not log the same signal twice
        seen = set(zip(old["date"], old["contract"]))
        new = new[[(d, c) not in seen for d, c in zip(new["date"], new["contract"])]]
    if new.empty:
        return
    JOURNAL.parent.mkdir(exist_ok=True)
    new.to_csv(JOURNAL, mode="a", header=not JOURNAL.exists(), index=False)


def load() -> pd.DataFrame:
    return pd.read_csv(JOURNAL) if JOURNAL.exists() else pd.DataFrame()


def trades_on(day: str) -> int:
    df = load()
    if df.empty:
        return 0
    return int(((df["date"] == day) & (df["verdict"] == "TRADE")).sum())
