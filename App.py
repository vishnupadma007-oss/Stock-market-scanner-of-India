import os

import plotly.graph_objects as go
import streamlit as st

from agents import journal, team
from agents.config import load_config
from agents.indicators import ema, vwap

st.set_page_config(page_title="Mover Reversal Agents", page_icon="📈", layout="centered",
                   initial_sidebar_state="collapsed")

# Streamlit Cloud secrets -> environment, so the Claude SDK finds the key.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except FileNotFoundError:
    pass

st.markdown("""
<style>
.stButton>button {width:100%; border-radius:16px; height:3em; font-weight:600;}
.card {border:1px solid #e5e7eb; border-radius:12px; padding:12px; margin:6px 0;}
.TRADE {border-left:6px solid #16a34a;} .WATCH {border-left:6px solid #f59e0b;}
.SKIP {border-left:6px solid #9ca3af;}
</style>""", unsafe_allow_html=True)

cfg = load_config()

with st.sidebar:
    st.header("Settings")
    cfg["capital"] = st.number_input("Capital (₹)", value=int(cfg["capital"]), step=10000)
    cfg["max_trades_per_day"] = st.slider("Max trades per day", 1, 5, cfg["max_trades_per_day"])
    cfg["net_target_pct"] = st.slider("Net target per trade (%)", 0.5, 5.0, float(cfg["net_target_pct"]), 0.25)
    ee = st.number_input("Emergency exit (% premium loss, 0 = off)", 0, 90, int(cfg["emergency_exit_pct"] or 0))
    cfg["emergency_exit_pct"] = ee or None
    use_ai = st.toggle("Use AI analyst (Claude)", value=cfg["ai"]["enabled"])

st.title("📈 Mover Reversal Agents")
st.caption("Top gainers → buy PE on exhaustion · Top losers → buy CE on bounce · Intraday only · Signals for paper trading")


def chart(df, title):
    d = df[df.index.date >= sorted(set(df.index.date))[-2]]
    v, e9, e21 = vwap(df).loc[d.index], ema(df["Close"], 9).loc[d.index], ema(df["Close"], 21).loc[d.index]
    fig = go.Figure([
        go.Candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"], name="Price"),
        go.Scatter(x=d.index, y=v, name="VWAP", line=dict(width=1.5, color="#7c3aed")),
        go.Scatter(x=d.index, y=e9, name="EMA 9", line=dict(width=1, color="#f59e0b")),
        go.Scatter(x=d.index, y=e21, name="EMA 21", line=dict(width=1, color="#2563eb")),
    ])
    fig.update_layout(title=title, height=360, margin=dict(l=0, r=0, t=30, b=0),
                      xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=-0.15),
                      xaxis=dict(rangebreaks=[dict(bounds=[15.5, 9.25], pattern="hour"), dict(bounds=["sat", "mon"])]))
    return fig


if st.button("RUN AGENT TEAM", type="primary"):
    bar = st.progress(0.0)
    try:
        st.session_state.report = team.run(cfg, use_ai=use_ai, progress=lambda m, f: bar.progress(f, text=m))
    except Exception as e:  # network/data failures should show on the phone, not crash the app
        st.error(f"Run failed: {e}")
    bar.empty()

report = st.session_state.get("report")
if report:
    mkt = report["regime"]
    st.subheader("🧭 Market regime")
    c1, c2, c3 = st.columns(3)
    c1.metric("Nifty today", f"{mkt['nifty_1d']:+.2f}%")
    c2.metric("Nifty 1 week", f"{mkt['nifty_1w']:+.2f}%")
    c3.metric("India VIX", f"{mkt['vix']:.1f}" if mkt["vix"] else "–")
    for n in mkt["notes"]:
        st.write("• " + n)
    if not report["ai_used"]:
        st.info("AI analyst is off (no ANTHROPIC_API_KEY in secrets, or toggled off). Rule-based agents only.")

    cands = sorted(report["candidates"], key=lambda c: (["TRADE", "WATCH", "SKIP"].index(c["decision"]["verdict"]),
                                                        -c["decision"]["score"]))
    st.subheader(f"🎯 Signals ({report['scanned']} stocks scanned at {report['time']:%H:%M})")
    if not cands:
        st.warning("No stock moved enough today to qualify as a top gainer/loser.")

    for c in cands:
        d, o, r, p = c["decision"], c["option"], c["risk"], c["profile"]
        icon = {"TRADE": "🟢", "WATCH": "🟡", "SKIP": "⚪"}[d["verdict"]]
        st.markdown(f"""<div class="card {d['verdict']}">
<b>{icon} {d['verdict']} · {c['symbol']}</b> ₹{p['ltp']:,.2f} ({p['chg_1d']:+.2f}% today, {p['chg_1w']:+.1f}% 1w)<br>
<b>{o['contract']}</b> · est. premium ₹{r['entry_premium']} · {o['days_to_expiry']} days to expiry<br>
🎯 Exit at ₹{r['target_premium']} (+{r['gross_move_pct']:.2f}% gross → ₹{r['net_profit']:,.0f} net after ₹{r['charges']['total']:,.0f} charges)<br>
⏱ Square off by {r['square_off']}{f" · 🚨 emergency exit ₹{r['emergency_exit']}" if r['emergency_exit'] else ""}
</div>""", unsafe_allow_html=True)
        with st.expander("Why? (agent reports & chart)"):
            if not c["intraday"].empty:
                st.plotly_chart(chart(c["intraday"], f"{c['symbol']} 5-min"), use_container_width=True)
            st.markdown(f"**Chart Reader — score {c['chart']['score']}/100:** {c['chart']['summary']}")
            for text, pts in c["chart"]["signals"]:
                st.write(f"{'✅' if pts > 0 else '⚠️'} {text} ({pts:+d})")
            if c["ai"]:
                st.markdown(f"**AI Analyst — {c['ai']['verdict']} ({c['ai'].get('confidence', 0)}%)**")
                for key in ("chart_read", "news", "reason"):
                    if c["ai"].get(key):
                        st.write(f"{key.replace('_', ' ').title()}: {c['ai'][key]}")
            st.markdown("**Risk Manager:**")
            lots = f"{r['lots']} lot(s) × {o['lot_size']}" if r["lots"] else "lot size unknown — qty approximate"
            st.write(f"Qty {r['qty']} ({lots}) · capital ₹{r['capital_used']:,.0f} · delta {o['delta']:+.2f}")
            if r["underlying_move"]:
                st.write(f"Needs the stock to move about ₹{r['underlying_move']:.2f} your way.")
            for b in r["blocks"]:
                st.write("⛔ " + b)
            st.markdown("**Decision:** " + " ".join(d["reasons"]))
            st.caption("Premium is an estimate from historical volatility. Check the live premium and spread in your broker app before entering.")

st.divider()
with st.expander("📒 Journal (paper trades)"):
    j = journal.load()
    if j.empty:
        st.write("No signals logged yet.")
    else:
        st.dataframe(j.tail(50), use_container_width=True)
        st.download_button("Download journal CSV", j.to_csv(index=False), "journal.csv")
    st.caption("Streamlit Cloud resets files on restart — download the journal regularly.")
