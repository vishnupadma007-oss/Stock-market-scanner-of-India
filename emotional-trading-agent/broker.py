"""Brokers. PaperBroker (default) simulates fills and keeps a ledger on disk.
ZerodhaBroker places real orders through Kite Connect and is only used with --live."""

import datetime as dt
import json
import os
import sys
from pathlib import Path


class PaperBroker:
    name = "paper"

    def __init__(self, capital, path="state/paper_account.json"):
        self.path = Path(path)
        if self.path.exists():
            self.a = json.loads(self.path.read_text())
        else:
            self.a = {"cash": capital, "positions": {}, "closed": []}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.a, indent=2))

    def portfolio(self):
        return {"cash": round(self.a["cash"], 2), "positions": self.a["positions"]}

    def realized_today(self):
        today = dt.date.today().isoformat()
        return sum(t["pnl"] for t in self.a["closed"] if t["closed"].startswith(today))

    def buy(self, o, price):
        self.a["cash"] -= o["qty"] * price
        self.a["positions"][o["symbol"]] = {"qty": o["qty"], "avg_price": price, "stop_loss": o["stop_loss"],
                                            "target": o["target"], "opened": dt.date.today().isoformat()}
        self._save()
        return f"paper BUY {o['qty']} {o['symbol']} @ ₹{price}"

    def sell(self, symbol, price, reason):
        p = self.a["positions"].pop(symbol)
        pnl = round((price - p["avg_price"]) * p["qty"], 2)
        self.a["cash"] += p["qty"] * price
        self.a["closed"].append({"symbol": symbol, "qty": p["qty"], "entry": p["avg_price"], "exit": price,
                                 "pnl": pnl, "reason": reason, "opened": p["opened"],
                                 "closed": dt.datetime.now().isoformat(timespec="seconds")})
        self._save()
        return pnl

    def check_exits(self, snapshot):
        """Close positions whose stop-loss or target was hit. Returns [(symbol, pnl, reason)]."""
        closed = []
        for sym, p in list(self.a["positions"].items()):
            if sym not in snapshot:
                continue
            last = snapshot[sym]["last_price"]
            if last <= p["stop_loss"]:
                closed.append((sym, self.sell(sym, last, "stop-loss hit"), "stop-loss hit"))
            elif last >= p["target"]:
                closed.append((sym, self.sell(sym, last, "target hit"), "target hit"))
        return closed


class ZerodhaBroker:
    """Real money. Entries are LIMIT orders in the CNC (delivery) product; each entry gets a GTT OCO
    order at Zerodha holding both the stop-loss and the target, so exits work even if this agent
    is not running."""

    name = "zerodha (LIVE)"

    def __init__(self, path="state/live_positions.json"):
        try:
            from kiteconnect import KiteConnect
        except ImportError:
            sys.exit("pip install kiteconnect to trade live with Zerodha.")
        key, token = os.environ.get("KITE_API_KEY"), os.environ.get("KITE_ACCESS_TOKEN")
        if not key or not token:
            sys.exit("Set KITE_API_KEY and KITE_ACCESS_TOKEN (see README: the access token is created daily).")
        self.kite = KiteConnect(api_key=key)
        self.kite.set_access_token(token)
        self.path = Path(path)
        self.meta = json.loads(self.path.read_text()) if self.path.exists() else {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.meta, indent=2))

    def portfolio(self):
        qty = {}
        for h in self.kite.holdings():
            qty[h["tradingsymbol"]] = qty.get(h["tradingsymbol"], 0) + h["quantity"] + h.get("t1_quantity", 0)
        for p in self.kite.positions()["net"]:
            if p["product"] == "CNC" and p["exchange"] == "NSE":
                qty[p["tradingsymbol"]] = qty.get(p["tradingsymbol"], 0) + p["quantity"]
        positions = {s: {**self.meta.get(s, {}), "qty": q} for s, q in qty.items() if q > 0}
        cash = self.kite.margins("equity")["net"]
        return {"cash": round(cash, 2), "positions": positions}

    def realized_today(self):
        return sum(p.get("realised", 0) for p in self.kite.positions()["day"])

    def buy(self, o, price):
        k = self.kite
        order_id = k.place_order(variety=k.VARIETY_REGULAR, exchange=k.EXCHANGE_NSE, tradingsymbol=o["symbol"],
                                 transaction_type=k.TRANSACTION_TYPE_BUY, quantity=o["qty"],
                                 product=k.PRODUCT_CNC, order_type=k.ORDER_TYPE_LIMIT, price=price,
                                 tag="arjun")
        # The stop leg's limit sits 1% under its trigger so it still fills if the price falls fast.
        stop_limit = round(o["stop_loss"] * 0.99 * 20) / 20  # NSE tick size is ₹0.05
        legs = [{"transaction_type": k.TRANSACTION_TYPE_SELL, "quantity": o["qty"], "order_type": k.ORDER_TYPE_LIMIT,
                 "product": k.PRODUCT_CNC, "price": px} for px in (stop_limit, o["target"])]
        gtt = k.place_gtt(trigger_type=k.GTT_TYPE_OCO, tradingsymbol=o["symbol"], exchange=k.EXCHANGE_NSE,
                          trigger_values=[o["stop_loss"], o["target"]], last_price=price, orders=legs)
        self.meta[o["symbol"]] = {"qty": o["qty"], "avg_price": price, "stop_loss": o["stop_loss"], "target": o["target"],
                                  "opened": dt.date.today().isoformat(), "gtt_id": gtt.get("trigger_id")}
        self._save()
        return f"LIVE BUY order {order_id} for {o['qty']} {o['symbol']} @ ₹{price}; GTT stop/target {gtt.get('trigger_id')}"

    def sell(self, symbol, price, reason):
        k = self.kite
        held = self.portfolio()["positions"].get(symbol, {}).get("qty", 0)
        if held:
            k.place_order(variety=k.VARIETY_REGULAR, exchange=k.EXCHANGE_NSE, tradingsymbol=symbol,
                          transaction_type=k.TRANSACTION_TYPE_SELL, quantity=held, product=k.PRODUCT_CNC,
                          order_type=k.ORDER_TYPE_LIMIT, price=round(price * 0.995 * 20) / 20, tag="arjun")
        m = self.meta.pop(symbol, {})
        if m.get("gtt_id"):
            try:
                k.delete_gtt(m["gtt_id"])
            except Exception:
                pass  # Already triggered or removed.
        self._save()
        return round((price - m.get("avg_price", price)) * held, 2)

    def check_exits(self, snapshot):
        """Zerodha's GTT does the exiting. Here we notice positions that disappeared and estimate the
        result (stop or target, whichever the last price is nearer) so Arjun's feelings stay current."""
        held = self.portfolio()["positions"]
        closed = []
        for sym, m in list(self.meta.items()):
            if sym in held and held[sym]["qty"] > 0:
                continue
            last = snapshot.get(sym, {}).get("last_price", m["avg_price"])
            exit_px = m["stop_loss"] if abs(last - m["stop_loss"]) < abs(last - m["target"]) else m["target"]
            pnl = round((exit_px - m["avg_price"]) * m["qty"], 2)
            closed.append((sym, pnl, "closed at broker (estimated)"))
            self.meta.pop(sym)
        self._save()
        return closed
