"""Draws a 5-minute candlestick chart as a PNG so the AI analyst can look at it."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .indicators import ema, vwap  # noqa: E402


def candle_png(df, title: str, sessions: int = 2) -> bytes:
    days = sorted(set(df.index.date))[-sessions:]
    full = df.assign(vwap=vwap(df), ema9=ema(df["Close"], 9), ema21=ema(df["Close"], 21))
    d = full[[ts.date() in days for ts in full.index]].reset_index(drop=True)

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(10, 6), sharex=True,
                                  gridspec_kw={"height_ratios": [4, 1]})
    up = d["Close"] >= d["Open"]
    colors = ["#16a34a" if u else "#dc2626" for u in up]
    ax.vlines(d.index, d["Low"], d["High"], color=colors, linewidth=1)
    ax.bar(d.index, (d["Close"] - d["Open"]).abs().clip(lower=1e-6),
           bottom=d[["Open", "Close"]].min(axis=1), color=colors, width=0.7)
    ax.plot(d.index, d["vwap"], color="#7c3aed", linewidth=1.3, label="VWAP")
    ax.plot(d.index, d["ema9"], color="#f59e0b", linewidth=1, label="EMA 9")
    ax.plot(d.index, d["ema21"], color="#2563eb", linewidth=1, label="EMA 21")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(title)
    ax.grid(alpha=0.2)
    axv.bar(d.index, d["Volume"], color=colors, width=0.7)
    axv.set_ylabel("Vol")
    ticks = list(range(0, len(d), 12))
    axv.set_xticks(ticks)
    axv.set_xticklabels([full.index[full.index.date >= days[0]][i].strftime("%d %H:%M") for i in ticks],
                        rotation=45, fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90)
    plt.close(fig)
    return buf.getvalue()
