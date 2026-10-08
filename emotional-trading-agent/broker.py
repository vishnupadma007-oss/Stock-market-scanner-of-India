"""Brokers. PaperBroker (default) simulates fills, charges and P&L and keeps a ledger on disk.
ZerodhaBroker places real orders through Kite Connect and is only used with --live.

Both report P&L net of charges (charges.py)."""

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from charges import trade_charges

IST = ZoneInfo("Asia/Kolkata")


def _tick(x):
    return round(x * 20) / 20  # NSE tick size is ₹0.05


def _gross(side, qty, entry, exit_price):
    return (exit_price - entry) * qty if side == "LONG" else (entry - exit_price) * qty


def _hit(p, last):
    """'stop-loss hit', 'target hit' or None for a position at the last price."""
    if p["side"] == "LONG":
        return "stop-loss hit" if last <= p["stop_loss"] else "target hit" if last >= p["target"] else None
    return "stop-loss hit" if last >= p["stop_loss"] else "target hit" if last <= p["target"] else None


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

    def equity(self, snapshot):
        value = self.a["cash"]
        for sym, p in self.a["positions"].items():
            last = snapshot.get(sym, {}).get("last_price", p["avg_price"])
            value += p["qty"] * p["avg_price"] + _gross(p["side"], p["qty"], p["avg_price"], last)
        return round(value, 2)

    def realized_today(self):
        today = dt.datetime.now(IST).date().isoformat()
        return round(sum(t["net"] for t in self.a["closed"] if t["closed"].startswith(today)), 2)

    def ltp(self, symbols):
        return {}  # Paper trading uses the market-data snapshot.

    def open(self, o, price):
        # Capital is blocked for shorts too (no leverage), and returned with the P&L on close.
        self.a["cash"] -= o["qty"] * price
        self.a["positions"][o["symbol"]] = {
            "side": o["side"], "qty": o["qty"], "avg_price": price, "stop_loss": o["stop_loss"],
            "target": o["target"], "product": o["product"], "opened": dt.datetime.now(IST).isoformat(timespec="seconds")}
        self._save()
        return f"paper {o['action']} {o['qty']} {o['symbol']} @ ₹{price} ({o['product']})"

    def close(self, symbol, price, reason):
        p = self.a["positions"].pop(symbol)
        gross = round(_gross(p["side"], p["qty"], p["avg_price"], price), 2)
        charges = trade_charges(p["side"], p["qty"], p["avg_price"], price, p["product"])["total"]
        net = round(gross - charges, 2)
        self.a["cash"] += p["qty"] * p["avg_price"] + net
        self.a["closed"].append({"symbol": symbol, "side": p["side"], "qty": p["qty"], "entry": p["avg_price"],
                                 "exit": price, "gross": gross, "charges": charges, "net": net, "reason": reason,
                                 "product": p["product"], "opened": p["opened"],
                                 "closed": dt.datetime.now(IST).isoformat(timespec="seconds")})
        self._save()
        return net, charges

    def check_exits(self, snapshot):
        """Close positions whose stop-loss or target was hit. Returns [(symbol, net, charges, reason)]."""
        closed = []
        for sym, p in list(self.a["positions"].items()):
            if sym in snapshot and (reason := _hit(p, snapshot[sym]["last_price"])):
                closed.append((sym, *self.close(sym, snapshot[sym]["last_price"], reason), reason))
        return closed

    def square_off(self, snapshot):
        return [(sym, *self.close(sym, snapshot.get(sym, {}).get("last_price", p["avg_price"]), "intraday square-off"),
                 "intraday square-off")
                for sym, p in list(self.a["positions"].items()) if p["product"] == "MIS"]


class ZerodhaBroker:
    """Real money through Kite Connect.

    Delivery (CNC) entries get a GTT OCO order at Zerodha holding both stop-loss and target, so exits
    happen even when the agent is off. Intraday (MIS) entries get a stop-loss order at the exchange;
    the agent's loop takes the target and squares off before the close (Zerodha also auto-squares MIS
    near 15:20). Net P&L for positions that closed at the broker is estimated from the stop or target."""

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
        self.realized_log = Path("state/live_realized.json")

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.meta, indent=2))

    def _log_realized(self, symbol, net, charges, reason):
        log = json.loads(self.realized_log.read_text()) if self.realized_log.exists() else []
        log.append({"symbol": symbol, "net": net, "charges": charges, "reason": reason,
                    "closed": dt.datetime.now(IST).isoformat(timespec="seconds")})
        self.realized_log.write_text(json.dumps(log[-2000:], indent=2))

    def ltp(self, symbols):
        if not symbols:
            return {}
        data = self.kite.ltp([f"NSE:{s}" for s in symbols])
        return {k.split(":", 1)[1]: v["last_price"] for k, v in data.items()}

    def _broker_quantities(self):
        """{symbol: (signed qty, product)} from holdings and today's positions."""
        q = {}
        for h in self.kite.holdings():
            n = h["quantity"] + h.get("t1_quantity", 0)
            if n:
                q[h["tradingsymbol"]] = (n, "CNC")
        for p in self.kite.positions()["net"]:
            if p["exchange"] == "NSE" and p["quantity"]:
                prev = q.get(p["tradingsymbol"], (0, p["product"]))[0] if p["product"] == "CNC" else 0
                q[p["tradingsymbol"]] = (prev + p["quantity"], p["product"])
        return q

    def portfolio(self):
        positions = {}
        for s, (n, product) in self._broker_quantities().items():
            positions[s] = {**self.meta.get(s, {}), "qty": abs(n), "side": "LONG" if n > 0 else "SHORT",
                            "product": product}
        return {"cash": round(self.kite.margins("equity")["net"], 2), "positions": positions}

    def equity(self, snapshot):
        m = self.kite.margins("equity")
        holdings_value = sum((h["quantity"] + h.get("t1_quantity", 0)) * h["last_price"] for h in self.kite.holdings())
        return round(m["net"] + m["utilised"].get("debits", 0) + holdings_value, 2)

    def realized_today(self):
        if not self.realized_log.exists():
            return 0.0
        today = dt.datetime.now(IST).date().isoformat()
        return round(sum(t["net"] for t in json.loads(self.realized_log.read_text()) if t["closed"].startswith(today)), 2)

    def open(self, o, price):
        k = self.kite
        entry_side = k.TRANSACTION_TYPE_BUY if o["side"] == "LONG" else k.TRANSACTION_TYPE_SELL
        product = k.PRODUCT_CNC if o["product"] == "CNC" else k.PRODUCT_MIS
        order_id = k.place_order(variety=k.VARIETY_REGULAR, exchange=k.EXCHANGE_NSE, tradingsymbol=o["symbol"],
                                 transaction_type=entry_side, quantity=o["qty"], product=product,
                                 order_type=k.ORDER_TYPE_LIMIT, price=_tick(price), tag="arjun")
        meta = {"side": o["side"], "qty": o["qty"], "avg_price": price, "stop_loss": o["stop_loss"],
                "target": o["target"], "product": o["product"], "entry_order_id": order_id,
                "opened": dt.datetime.now(IST).isoformat(timespec="seconds")}
        self.meta[o["symbol"]] = meta
        self._save()
        # Protection goes in only after the entry fills: a stop order on an unfilled entry could open an
        # unintended position. Wait briefly here; otherwise the next check_exits protects it.
        for _ in range(5):
            time.sleep(1)
            if self._order_status(order_id) == "COMPLETE":
                return f"LIVE {o['action']} {o['qty']} {o['symbol']} @ ₹{_tick(price)} filled; " + self._protect(o["symbol"], meta)
        return f"LIVE {o['action']} order {order_id}: {o['qty']} {o['symbol']} @ ₹{_tick(price)} pending; protection after fill"

    def _order_status(self, order_id):
        history = self.kite.order_history(order_id)
        return history[-1]["status"] if history else None

    def _protect(self, symbol, m):
        k = self.kite
        exit_side = k.TRANSACTION_TYPE_SELL if m["side"] == "LONG" else k.TRANSACTION_TYPE_BUY
        product = k.PRODUCT_CNC if m["product"] == "CNC" else k.PRODUCT_MIS
        # The stop's limit sits 1% beyond its trigger so it still fills if the price moves fast.
        stop_limit = _tick(m["stop_loss"] * (0.99 if m["side"] == "LONG" else 1.01))
        if m["product"] == "CNC":
            legs = [{"transaction_type": exit_side, "quantity": m["qty"], "order_type": k.ORDER_TYPE_LIMIT,
                     "product": product, "price": px} for px in (stop_limit, m["target"])]
            gtt = k.place_gtt(trigger_type=k.GTT_TYPE_OCO, tradingsymbol=symbol, exchange=k.EXCHANGE_NSE,
                              trigger_values=[m["stop_loss"], m["target"]], last_price=m["avg_price"], orders=legs)
            m["gtt_id"] = gtt.get("trigger_id")
            note = f"GTT stop/target {m['gtt_id']}"
        else:
            m["sl_order_id"] = k.place_order(
                variety=k.VARIETY_REGULAR, exchange=k.EXCHANGE_NSE, tradingsymbol=symbol,
                transaction_type=exit_side, quantity=m["qty"], product=product, order_type=k.ORDER_TYPE_SL,
                trigger_price=_tick(m["stop_loss"]), price=stop_limit, tag="arjun")
            note = f"stop-loss order {m['sl_order_id']}"
        m["protected"] = True
        self._save()
        return note

    def _cancel_protection(self, m):
        k = self.kite
        try:
            if m.get("gtt_id"):
                k.delete_gtt(m["gtt_id"])
            if m.get("sl_order_id"):
                k.cancel_order(variety=k.VARIETY_REGULAR, order_id=m["sl_order_id"])
        except Exception:
            pass  # Already triggered or removed.

    def close(self, symbol, price, reason):
        k = self.kite
        m = self.meta.pop(symbol, {})
        n, product = self._broker_quantities().get(symbol, (0, m.get("product", "CNC")))
        self._cancel_protection(m)
        if n:
            side = "LONG" if n > 0 else "SHORT"
            k.place_order(variety=k.VARIETY_REGULAR, exchange=k.EXCHANGE_NSE, tradingsymbol=symbol,
                          transaction_type=k.TRANSACTION_TYPE_SELL if n > 0 else k.TRANSACTION_TYPE_BUY,
                          quantity=abs(n), product=k.PRODUCT_CNC if product == "CNC" else k.PRODUCT_MIS,
                          order_type=k.ORDER_TYPE_LIMIT, tag="arjun",
                          price=_tick(price * (0.995 if n > 0 else 1.005)))  # protected exit
            entry = m.get("avg_price", price)
            charges = trade_charges(side, abs(n), entry, price, product)["total"]
            net = round(_gross(side, abs(n), entry, price) - charges, 2)
        else:
            net, charges = 0.0, 0.0
        self._save()
        self._log_realized(symbol, net, charges, reason)
        return net, charges

    def check_exits(self, snapshot):
        """Take intraday targets, and notice positions that closed at the broker (stop order or GTT)."""
        held = self._broker_quantities()
        orders = {o["order_id"]: o for o in self.kite.orders()}
        closed = []
        for sym, m in list(self.meta.items()):
            last = snapshot.get(sym, {}).get("last_price", m["avg_price"])
            if sym in held:
                if not m.get("protected"):
                    print(f"   🛡️  {sym} filled; " + self._protect(sym, m))
                if m["product"] == "MIS" and _hit(m, last) == "target hit":
                    closed.append((sym, *self.close(sym, last, "target hit"), "target hit"))
                continue
            status = orders.get(m.get("entry_order_id"), {}).get("status")
            if status and status != "COMPLETE":  # Entry never filled: cancel it and forget it.
                try:
                    if status in ("OPEN", "TRIGGER PENDING"):
                        self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=m["entry_order_id"])
                except Exception:
                    pass
                self._cancel_protection(m)
                self.meta.pop(sym)
                continue
            exit_px = m["stop_loss"] if abs(last - m["stop_loss"]) < abs(last - m["target"]) else m["target"]
            charges = trade_charges(m["side"], m["qty"], m["avg_price"], exit_px, m["product"])["total"]
            net = round(_gross(m["side"], m["qty"], m["avg_price"], exit_px) - charges, 2)
            reason = "closed at broker (estimated)"
            self._log_realized(sym, net, charges, reason)
            closed.append((sym, net, charges, reason))
            self.meta.pop(sym)
        self._save()
        return closed

    def square_off(self, snapshot):
        out = []
        for sym, (n, product) in self._broker_quantities().items():
            if product == "MIS":
                last = snapshot.get(sym, {}).get("last_price") or self.ltp([sym])[sym]
                out.append((sym, *self.close(sym, last, "intraday square-off"), "intraday square-off"))
        return out
