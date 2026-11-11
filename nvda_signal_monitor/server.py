"""
NVDA Intraday Signal Monitor (Port 9879)
========================================
Live real-time monitor for the 2026-11-11 NVDA Oversold + CRWV/SOXL Tailwind Playbook:
  - Premarket Guard (< 09:30 ET): Blocks chasing premarket below PM_VWAP (94%-100% historical morning dip rate).
  - Peer Tailwind & Safety Gates:
      * Gate T1: SOXL > $62.50 (+11.8%+ vs Nov 10 close $55.88)
      * Gate T2: CRWV > $53.50 (holding above premarket low / +9.7%+ vs $48.77 close)
      * Gate T3: NVDA > $168.40 (Hard Stop / Nov 10 $168.90 gap-integrity guard)
      * Gate T4: NYSE RTH Open (>= 09:30:00 ET, confirmed on completed 5m RTH candles)
  - Setup A (Primary, 09:30-10:45 ET / 11:30 ET ext):
      * Probe into $170.90-$172.20 confluence flush zone (or S4 -1.25% RTH open flush) while holding > $168.40
      * Completed 5m RTH green higher-low reclaim candle (Close > Open and Low > Flush_Low) while Gates T1-T3 hold
      * Stop: $168.40 hard stop (also shows tight Flush_Low - $0.25) | T1 (50%): PM_VWAP | T2 (50%): PM_High / Tue Nov 17 T0
  - Setup B (Strength Reclaim, >= 09:45 ET if NVDA refuses to flush):
      * Two consecutive completed 5m RTH bars close above max($175.50, PM_VWAP) AND RTH Session VWAP while Gates T1-T3 hold
      * Stop: max($173.40, RTH_Morning_Low) | T1 (50%): PM_High ($178.36) | T2 (50%): $180.00 (Nov 9 high)
"""
from __future__ import annotations

import concurrent.futures
import datetime
import math
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

NY_TZ = ZoneInfo("America/New_York")

CNBC_BARS_URL = "https://ts-api.cnbc.com/harmony/app/bars"
CNBC_QUOTE_URL = "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol.htm"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

SYMBOLS = ["NVDA", "CRWV", "SOXL", "SMH", "MU", "AMD", "AVGO", "QQQ", "SPY"]

# Study Strategy Constants (from nvda_premarket_crwv_soxl_study.md Section 4)
HARD_STOP_NVDA = 168.40
SETUP_A_ZONE_LOW = 170.90
SETUP_A_ZONE_HIGH = 172.20
SOXL_GATE_MIN = 62.50
SOXL_GATE_WARN = 60.00
CRWV_GATE_MIN = 53.50
CRWV_GATE_WARN = 51.50
SETUP_B_MIN_HURDLE = 175.50
SETUP_B_FALLBACK_STOP = 173.40
SETUP_B_TARGET_2 = 180.00

POLL_INTERVAL_SEC = 5.0

_state_lock = threading.Lock()
_latest_state: Dict[str, Any] = {
    "ok": False,
    "status": "INITIALIZING",
    "message": "Booting NVDA live market telemetry...",
}
_event_log: List[Dict[str, Any]] = []
_seen_event_keys: set[str] = set()
_stop_event = threading.Event()


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return None if math.isnan(val) else float(val)
    s = str(val).strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s.upper() in ("UNCH", "N/A", "NULL", "NONE", "--"):
        return 0.0 if s.upper() == "UNCH" else None
    try:
        return float(s)
    except ValueError:
        return None


def _log_event(key: str, ts_str: str, level: str, title: str, detail: str) -> None:
    if key in _seen_event_keys:
        return
    _seen_event_keys.add(key)
    _event_log.insert(
        0,
        {
            "key": key,
            "ts": ts_str,
            "level": level,
            "title": title,
            "detail": detail,
        },
    )
    del _event_log[60:]


def _fetch_symbol_5m(client: httpx.Client, symbol: str, start_str: str, end_str: str) -> List[Dict[str, Any]]:
    url = f"{CNBC_BARS_URL}/{symbol}/5M/{start_str}/{end_str}/adjusted/EST5EDT.json"
    resp = client.get(url)
    if resp.status_code != 200:
        return []
    raw_bars = resp.json().get("barData", {}).get("priceBars", []) or []
    parsed: List[Dict[str, Any]] = []
    for b in raw_bars:
        tt = str(b.get("tradeTime", ""))
        if len(tt) < 14:
            continue
        o = _safe_float(b.get("open"))
        h = _safe_float(b.get("high"))
        l = _safe_float(b.get("low"))
        c = _safe_float(b.get("close"))
        v = _safe_float(b.get("volume")) or 0.0
        if o is None or h is None or l is None or c is None:
            continue
        dt_et = datetime.datetime.strptime(tt[:14], "%Y%m%d%H%M%S").replace(tzinfo=NY_TZ)
        parsed.append(
            {
                "dt": dt_et,
                "date": dt_et.date(),
                "hm": dt_et.hour * 100 + dt_et.minute,
                "ts_label": dt_et.strftime("%H:%M"),
                "epoch_ms": int(dt_et.timestamp() * 1000),
                "o": round(o, 4),
                "h": round(h, 4),
                "l": round(l, 4),
                "c": round(c, 4),
                "v": float(v),
            }
        )
    parsed.sort(key=lambda x: x["epoch_ms"])
    return parsed


def _fetch_live_quotes(client: httpx.Client, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    params = {
        "symbols": "|".join(symbols),
        "requestMethod": "itv",
        "noform": "1",
        "partnerId": "2",
        "fund": "1",
        "exthrs": "1",
        "output": "json",
        "events": "1",
    }
    out: Dict[str, Dict[str, Any]] = {}
    try:
        resp = client.get(CNBC_QUOTE_URL, params=params)
        if resp.status_code != 200 or not resp.text.strip():
            return out
        qlist = resp.json().get("FormattedQuoteResult", {}).get("FormattedQuote", [])
        if isinstance(qlist, dict):
            qlist = [qlist]
        for q in qlist:
            sym = str(q.get("symbol", "")).upper().strip()
            if not sym:
                continue
            rth_last = _safe_float(q.get("last"))
            prev_close = _safe_float(q.get("previous_day_closing"))
            ext = q.get("ExtendedMktQuote") or {}
            ext_last = _safe_float(ext.get("last")) if isinstance(ext, dict) else None
            cur_mkt = str(q.get("curmktstatus", "")).upper()
            # In premarket/afterhours CNBC updates ExtendedMktQuote.last; during REG_MKT it updates last
            active_last = rth_last if cur_mkt == "REG_MKT" and rth_last is not None else (ext_last or rth_last)
            out[sym] = {
                "active_last": active_last,
                "rth_last": rth_last,
                "ext_last": ext_last,
                "prev_close": prev_close,
                "mkt_status": cur_mkt,
            }
    except Exception:
        return out
    return out


def _compute_vwap(bars: List[Dict[str, Any]]) -> Optional[float]:
    if not bars:
        return None
    pv = 0.0
    vv = 0.0
    for b in bars:
        vol = max(float(b["v"]), 0.0)
        typ = (float(b["h"]) + float(b["l"]) + float(b["c"])) / 3.0
        pv += typ * vol
        vv += vol
    if vv <= 0:
        return round(sum((b["h"] + b["l"] + b["c"]) / 3.0 for b in bars) / len(bars), 4)
    return round(pv / vv, 4)


def _lookup_bar_close_at_or_before(bars: List[Dict[str, Any]], target_epoch_ms: int) -> Optional[float]:
    val: Optional[float] = None
    for b in bars:
        if b["epoch_ms"] <= target_epoch_ms:
            val = float(b["c"])
        else:
            break
    return val


def _poll_once() -> Dict[str, Any]:
    now_et = datetime.datetime.now(NY_TZ)
    today_date = now_et.date()
    start_dt = today_date - datetime.timedelta(days=5)
    end_dt = today_date + datetime.timedelta(days=1)
    start_str = start_dt.strftime("%Y%m%d") + "040000"
    end_str = end_dt.strftime("%Y%m%d") + "200000"

    bars_by_sym: Dict[str, List[Dict[str, Any]]] = {}
    with httpx.Client(timeout=6.5, headers=HTTP_HEADERS) as client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            fut_bars = {
                pool.submit(_fetch_symbol_5m, client, sym, start_str, end_str): sym
                for sym in SYMBOLS
            }
            fut_quotes = pool.submit(_fetch_live_quotes, client, SYMBOLS)
            for fut, sym in fut_bars.items():
                try:
                    bars_by_sym[sym] = fut.result()
                except Exception:
                    bars_by_sym[sym] = []
            quotes_by_sym = fut_quotes.result()

    nvda_all = bars_by_sym.get("NVDA", [])
    if not nvda_all:
        raise RuntimeError("CNBC 5M feed returned empty bars for NVDA.")

    # Determine active session date (today if bars exist today, else latest date in feed)
    available_dates = sorted({b["date"] for b in nvda_all})
    session_date = today_date if today_date in available_dates else available_dates[-1]
    prior_rth_dates = [
        d for d in available_dates
        if d < session_date and any(930 <= b["hm"] <= 1555 for b in nvda_all if b["date"] == d)
    ]
    prev_session_date = prior_rth_dates[-1] if prior_rth_dates else None

    # Build peer summary strip
    peers: Dict[str, Dict[str, Any]] = {}
    for sym in SYMBOLS:
        sbars = bars_by_sym.get(sym, [])
        qinfo = quotes_by_sym.get(sym, {})
        prev_rth = [
            b for b in sbars
            if prev_session_date is not None and b["date"] == prev_session_date and 930 <= b["hm"] <= 1555
        ]
        prev_close = float(prev_rth[-1]["c"]) if prev_rth else (qinfo.get("prev_close") or 0.0)

        pm_bars = [b for b in sbars if b["date"] == session_date and 400 <= b["hm"] < 930]
        rth_bars = [b for b in sbars if b["date"] == session_date and 930 <= b["hm"] <= 1555]
        session_bars = pm_bars + rth_bars

        bar_last = float(session_bars[-1]["c"]) if session_bars else prev_close
        q_last = qinfo.get("active_last")
        # Trust quote tick if within reasonable sanity range (5% of latest 5m bar), else bar_last
        if q_last is not None and bar_last > 0 and abs(q_last / bar_last - 1.0) < 0.05:
            live_px = float(q_last)
        else:
            live_px = bar_last

        pm_vwap = _compute_vwap(pm_bars)
        rth_vwap = _compute_vwap(rth_bars)
        pm_hi = max((float(b["h"]) for b in pm_bars), default=None)
        pm_lo = min((float(b["l"]) for b in pm_bars), default=None)
        rth_hi = max((float(b["h"]) for b in rth_bars), default=None)
        rth_lo = min((float(b["l"]) for b in rth_bars), default=None)
        if rth_bars and now_et.date() == session_date and 930 <= (now_et.hour * 100 + now_et.minute) < 1600:
            rth_hi = max(rth_hi, live_px) if rth_hi is not None else live_px
            rth_lo = min(rth_lo, live_px) if rth_lo is not None else live_px
        elif pm_bars and now_et.date() == session_date and (now_et.hour * 100 + now_et.minute) < 930:
            pm_hi = max(pm_hi, live_px) if pm_hi is not None else live_px
            pm_lo = min(pm_lo, live_px) if pm_lo is not None else live_px

        pm_vol = sum(float(b["v"]) for b in pm_bars)
        rth_vol = sum(float(b["v"]) for b in rth_bars)
        chg_pct = ((live_px / prev_close) - 1.0) * 100.0 if prev_close > 0 else 0.0
        vs_pm_vwap_pct = ((live_px / pm_vwap) - 1.0) * 100.0 if pm_vwap else None

        peers[sym] = {
            "symbol": sym,
            "prev_close": round(prev_close, 2),
            "last": round(live_px, 2),
            "chg_pct": round(chg_pct, 2),
            "pm_high": round(pm_hi, 2) if pm_hi is not None else None,
            "pm_low": round(pm_lo, 2) if pm_lo is not None else None,
            "pm_vwap": round(pm_vwap, 2) if pm_vwap is not None else None,
            "vs_pm_vwap_pct": round(vs_pm_vwap_pct, 2) if vs_pm_vwap_pct is not None else None,
            "rth_high": round(rth_hi, 2) if rth_hi is not None else None,
            "rth_low": round(rth_lo, 2) if rth_lo is not None else None,
            "rth_vwap": round(rth_vwap, 2) if rth_vwap is not None else None,
            "pm_vol_m": round(pm_vol / 1e6, 2),
            "rth_vol_m": round(rth_vol / 1e6, 2),
            "last_bar_ts": session_bars[-1]["ts_label"] if session_bars else "--:--",
        }

    # Detailed NVDA Session Partitioning
    nvda_peer = peers["NVDA"]
    soxl_peer = peers["SOXL"]
    crwv_peer = peers["CRWV"]

    nvda_pm_bars = [b for b in nvda_all if b["date"] == session_date and 400 <= b["hm"] < 930]
    nvda_rth_raw = [b for b in nvda_all if b["date"] == session_date and 930 <= b["hm"] <= 1555]
    soxl_session_bars = [b for b in bars_by_sym.get("SOXL", []) if b["date"] == session_date]
    crwv_session_bars = [b for b in bars_by_sym.get("CRWV", []) if b["date"] == session_date]

    now_epoch_ms = int(now_et.timestamp() * 1000)
    five_min_ms = 5 * 60 * 1000

    # Patch latest forming bar with live quote price if inside its 5m window
    nvda_live_px = nvda_peer["last"]
    nvda_prev_close = nvda_peer["prev_close"] or 168.90
    pm_high = nvda_peer["pm_high"] or 178.36
    pm_low = nvda_peer["pm_low"] or 171.25
    pm_vwap = nvda_peer["pm_vwap"] or 175.47
    pm_last_anchor = float(nvda_pm_bars[-1]["c"]) if nvda_pm_bars else nvda_live_px

    completed_rth: List[Dict[str, Any]] = []
    forming_rth: Optional[Dict[str, Any]] = None
    for b in nvda_rth_raw:
        b_copy = dict(b)
        if b_copy["epoch_ms"] + five_min_ms <= now_epoch_ms:
            completed_rth.append(b_copy)
        elif b_copy["epoch_ms"] <= now_epoch_ms < b_copy["epoch_ms"] + five_min_ms:
            b_copy["c"] = nvda_live_px
            b_copy["h"] = max(float(b_copy["h"]), nvda_live_px)
            b_copy["l"] = min(float(b_copy["l"]), nvda_live_px)
            forming_rth = b_copy

    is_premarket = (
        session_date == now_et.date()
        and (now_et.hour * 100 + now_et.minute) < 930
    )
    is_rth_open = (
        session_date == now_et.date()
        and 930 <= (now_et.hour * 100 + now_et.minute) < 1600
    )
    is_after_hours = (
        session_date == now_et.date()
        and (now_et.hour * 100 + now_et.minute) >= 1600
    )

    rth_open = float(nvda_rth_raw[0]["o"]) if nvda_rth_raw else None
    gap_ref_px = rth_open if rth_open is not None else pm_last_anchor
    gap_fill_50 = round(0.5 * (nvda_prev_close + gap_ref_px), 2)
    s4_open_flush_px = round((rth_open if rth_open is not None else pm_last_anchor) * 0.9875, 2)

    # Seconds until 09:30:00 ET opening bell & seconds until next 5m bar close
    bell_dt = datetime.datetime.combine(session_date, datetime.time(9, 30, 0), tzinfo=NY_TZ)
    sec_to_bell = max(0, int((bell_dt - now_et).total_seconds()))
    sec_into_5m = (now_et.minute % 5) * 60 + now_et.second
    sec_to_next_5m_close = max(0, 300 - sec_into_5m)

    # Evaluate Live Gates
    soxl_live = soxl_peer["last"]
    crwv_live = crwv_peer["last"]
    rth_all_so_far = completed_rth + ([forming_rth] if forming_rth else [])
    rth_low_live = min((float(b["l"]) for b in rth_all_so_far), default=None)
    rth_high_live = max((float(b["h"]) for b in rth_all_so_far), default=None)
    rth_vwap_live = _compute_vwap(rth_all_so_far)

    hard_stop_breached = (nvda_live_px <= HARD_STOP_NVDA) or (
        rth_low_live is not None and rth_low_live <= HARD_STOP_NVDA
    )

    gate_t1_state = (
        "PASS" if soxl_live >= SOXL_GATE_MIN else ("WARN" if soxl_live >= SOXL_GATE_WARN else "FAIL")
    )
    gate_t2_state = (
        "PASS" if crwv_live >= CRWV_GATE_MIN else ("WARN" if crwv_live >= CRWV_GATE_WARN else "FAIL")
    )
    gate_t3_state = "FAIL" if hard_stop_breached else "PASS"
    gate_t4_state = "STANDBY" if is_premarket else ("PASS" if (is_rth_open or completed_rth) else "CLOSED")

    gates = [
        {
            "id": "T4",
            "name": "Premarket Guard / RTH Bell",
            "state": gate_t4_state,
            "current": f"{'PREMARKET' if is_premarket else ('RTH LIVE' if is_rth_open else 'POST-RTH')} ({now_et.strftime('%H:%M:%S')})",
            "threshold": ">= 09:30:00 ET (5m Close)",
            "note": (
                f"Do NOT buy ${nvda_live_px:.2f} premarket (94-100% morning dip rate). Bell in {sec_to_bell // 60}m {sec_to_bell % 60:02d}s."
                if is_premarket
                else f"{len(completed_rth)} completed 5m RTH bars | next 5m close in {sec_to_next_5m_close}s"
            ),
        },
        {
            "id": "T1",
            "name": "SOXL Semi Tailwind",
            "state": gate_t1_state,
            "current": f"${soxl_live:.2f} ({soxl_peer['chg_pct']:+.2f}%)",
            "threshold": f"> ${SOXL_GATE_MIN:.2f} (PM_VWAP ${soxl_peer['pm_vwap'] or 0:.2f})",
            "note": "Confirms broad 3x semiconductor rally remains intact.",
        },
        {
            "id": "T2",
            "name": "CRWV Q3 Backlog Catalyst",
            "state": gate_t2_state,
            "current": f"${crwv_live:.2f} ({crwv_peer['chg_pct']:+.2f}%)",
            "threshold": f"> ${CRWV_GATE_MIN:.2f} (PM Low)",
            "note": "Confirms CoreWeave $132.5B backlog / $37B-$39B CapEx bid is holding.",
        },
        {
            "id": "T3",
            "name": "NVDA Gap-Integrity Guard",
            "state": gate_t3_state,
            "current": f"${nvda_live_px:.2f} (RTH Low {f'${rth_low_live:.2f}' if rth_low_live else 'N/A'})",
            "threshold": f"> ${HARD_STOP_NVDA:.2f} (Nov 10 Close ${nvda_prev_close:.2f})",
            "note": "Full gap-fill below $168.40 invalidates the oversold bounce.",
        },
    ]

    # Deterministic Bar-by-Bar Replay of Completed RTH 5m Bars for Setup A & Setup B
    # Attach running RTH VWAP to each completed bar for chart & causal Setup B evaluation
    running_bars: List[Dict[str, Any]] = []
    setup_a_probed = False
    setup_a_probe_bar: Optional[Dict[str, Any]] = None
    setup_a_flush_low: Optional[float] = None
    setup_a_s4_probed = False
    setup_a_signal: Optional[Dict[str, Any]] = None

    setup_b_consec_count = 0
    setup_b_signal: Optional[Dict[str, Any]] = None

    for idx, b in enumerate(completed_rth):
        running_bars.append(b)
        rv = _compute_vwap(running_bars) or b["c"]
        b["rth_vwap"] = rv

        bar_low = float(b["l"])
        bar_close = float(b["c"])
        bar_open = float(b["o"])
        bar_hm = int(b["hm"])
        soxl_at_bar = _lookup_bar_close_at_or_before(soxl_session_bars, b["epoch_ms"]) or soxl_live
        crwv_at_bar = _lookup_bar_close_at_or_before(crwv_session_bars, b["epoch_ms"]) or crwv_live
        min_low_thru_bar = min(float(x["l"]) for x in running_bars)

        if min_low_thru_bar <= HARD_STOP_NVDA:
            _log_event(
                f"invalid_{session_date}",
                b["ts_label"],
                "DANGER",
                "HARD STOP / INVALIDATION ($168.40 BREACHED)",
                f"NVDA 5m bar {b['ts_label']} traded down to ${bar_low:.2f} (<= $168.40). Stand down.",
            )
            break

        # --- Setup A Causal Check (Primary window 09:30-10:45, tracked thru 11:30 ET) ---
        if bar_hm <= 1130:
            # First check if a PRIOR bar already probed the flush zone and THIS bar prints the higher-low green reclaim
            if (
                setup_a_probed
                and setup_a_signal is None
                and setup_a_flush_low is not None
                and bar_close > bar_open
                and bar_low > setup_a_flush_low
                and bar_close < (pm_vwap - 0.15)
                and soxl_at_bar >= SOXL_GATE_MIN
                and crwv_at_bar >= CRWV_GATE_MIN
            ):
                confirm_dt = b["dt"] + datetime.timedelta(minutes=5)
                setup_a_signal = {
                    "setup": "SETUP_A",
                    "bar_open_ts": b["ts_label"],
                    "confirmed_at": confirm_dt.strftime("%H:%M:%S ET"),
                    "bar_epoch_ms": b["epoch_ms"],
                    "entry_price": round(bar_close, 2),
                    "flush_low": round(setup_a_flush_low, 2),
                    "hard_stop": HARD_STOP_NVDA,
                    "tight_stop": round(max(HARD_STOP_NVDA, setup_a_flush_low - 0.25), 2),
                    "target_1": round(pm_vwap, 2),
                    "target_2": round(pm_high, 2),
                    "soxl_at_signal": round(soxl_at_bar, 2),
                    "crwv_at_signal": round(crwv_at_bar, 2),
                    "in_primary_window": bar_hm <= 1045,
                }
                _log_event(
                    f"sig_a_{session_date}_{b['ts_label']}",
                    confirm_dt.strftime("%H:%M:%S"),
                    "SIGNAL",
                    f"SIGNAL FLASH — SETUP A RECLAIM @ ${bar_close:.2f}",
                    (
                        f"5m bar {b['ts_label']} closed green (${bar_open:.2f} -> ${bar_close:.2f}) with higher low "
                        f"${bar_low:.2f} above flush low ${setup_a_flush_low:.2f} | SOXL ${soxl_at_bar:.2f}, CRWV ${crwv_at_bar:.2f}."
                    ),
                )

            # Update flush probe state if this bar dipped into $170.90-$172.20 (or made a deeper low before signal)
            if bar_low <= SETUP_A_ZONE_HIGH and bar_hm <= 1115:
                if not setup_a_probed:
                    setup_a_probed = True
                    setup_a_probe_bar = b
                    setup_a_flush_low = bar_low
                    _log_event(
                        f"arm_a_{session_date}_{b['ts_label']}",
                        b["ts_label"],
                        "ARMED",
                        f"SETUP A ARMED — NVDA Probed Flush Zone (${bar_low:.2f})",
                        f"NVDA entered $170.90-$172.20 confluence zone on {b['ts_label']} bar. Waiting for 5m green higher-low reclaim.",
                    )
                elif setup_a_flush_low is None or bar_low < setup_a_flush_low:
                    setup_a_flush_low = bar_low

            if bar_low <= s4_open_flush_px:
                setup_a_s4_probed = True

        # --- Setup B Causal Check (>= 09:45 ET, 2 consecutive 5m closes > max($175.50, PM_VWAP, RTH_VWAP)) ---
        if bar_hm >= 945 and bar_hm <= 1430:
            hurdle = max(SETUP_B_MIN_HURDLE, pm_vwap, rv)
            if bar_close > hurdle:
                setup_b_consec_count += 1
                if setup_b_consec_count == 1 and setup_b_signal is None:
                    confirm_dt = b["dt"] + datetime.timedelta(minutes=5)
                    _log_event(
                        f"arm_b1_{session_date}_{b['ts_label']}",
                        confirm_dt.strftime("%H:%M:%S"),
                        "ARMED",
                        f"SETUP B BAR 1/2 CLOSED ABOVE VWAP (${bar_close:.2f} > ${hurdle:.2f})",
                        "1st 5m RTH bar closed above PM_VWAP & RTH_VWAP. Need 1 more consecutive 5m close above hurdle.",
                    )
                elif (
                    setup_b_consec_count >= 2
                    and setup_b_signal is None
                    and bar_close >= bar_open
                    and soxl_at_bar >= SOXL_GATE_MIN
                    and crwv_at_bar >= CRWV_GATE_MIN
                ):
                    confirm_dt = b["dt"] + datetime.timedelta(minutes=5)
                    rth_morning_low = min(float(x["l"]) for x in running_bars)
                    b_stop = round(min(bar_close - 0.75, max(SETUP_B_FALLBACK_STOP, rth_morning_low)), 2)
                    setup_b_signal = {
                        "setup": "SETUP_B",
                        "bar_open_ts": b["ts_label"],
                        "confirmed_at": confirm_dt.strftime("%H:%M:%S ET"),
                        "bar_epoch_ms": b["epoch_ms"],
                        "entry_price": round(bar_close, 2),
                        "hurdle_cleared": round(hurdle, 2),
                        "hard_stop": b_stop,
                        "tight_stop": b_stop,
                        "target_1": round(pm_high, 2),
                        "target_2": SETUP_B_TARGET_2,
                        "soxl_at_signal": round(soxl_at_bar, 2),
                        "crwv_at_signal": round(crwv_at_bar, 2),
                    }
                    _log_event(
                        f"sig_b_{session_date}_{b['ts_label']}",
                        confirm_dt.strftime("%H:%M:%S"),
                        "SIGNAL",
                        f"SIGNAL FLASH — SETUP B VWAP RECLAIM @ ${bar_close:.2f}",
                        (
                            f"2nd consecutive 5m RTH bar ({b['ts_label']}) closed at ${bar_close:.2f} above "
                            f"PM_VWAP (${pm_vwap:.2f}) & RTH_VWAP (${rv:.2f}) | Stop ${b_stop:.2f}."
                        ),
                    )
            else:
                setup_b_consec_count = 0

    if forming_rth is not None:
        forming_rth["rth_vwap"] = rth_vwap_live or forming_rth["c"]

    # Check live intra-bar forming status for Setup A & Setup B
    forming_in_flush_zone = (
        forming_rth is not None
        and float(forming_rth["l"]) <= SETUP_A_ZONE_HIGH
        and not hard_stop_breached
    )
    if forming_in_flush_zone and not setup_a_probed:
        _log_event(
            f"live_probe_a_{session_date}_{forming_rth['ts_label']}",
            now_et.strftime("%H:%M:%S"),
            "ARMED",
            f"LIVE INTRA-BAR PROBE INTO FLUSH ZONE (${float(forming_rth['l']):.2f})",
            f"NVDA dipped <= ${SETUP_A_ZONE_HIGH:.2f} on live {forming_rth['ts_label']} candle. Watch next 5m green higher-low close!",
        )

    effective_flush_low = setup_a_flush_low
    if forming_rth is not None and float(forming_rth["l"]) <= SETUP_A_ZONE_HIGH:
        effective_flush_low = (
            min(effective_flush_low, float(forming_rth["l"]))
            if effective_flush_low is not None
            else float(forming_rth["l"])
        )

    forming_a_reclaim_preview = (
        setup_a_probed
        and setup_a_signal is None
        and forming_rth is not None
        and setup_a_flush_low is not None
        and float(forming_rth["c"]) > float(forming_rth["o"])
        and float(forming_rth["l"]) > setup_a_flush_low
        and gate_t1_state == "PASS"
        and gate_t2_state == "PASS"
        and not hard_stop_breached
    )

    setup_b_live_hurdle = round(max(SETUP_B_MIN_HURDLE, pm_vwap, rth_vwap_live or pm_vwap), 2)
    forming_b_bar2_preview = (
        setup_b_consec_count >= 1
        and setup_b_signal is None
        and forming_rth is not None
        and int(forming_rth["hm"]) >= 950
        and float(forming_rth["c"]) > setup_b_live_hurdle
        and float(forming_rth["c"]) >= float(forming_rth["o"])
        and gate_t1_state == "PASS"
        and gate_t2_state == "PASS"
        and not hard_stop_breached
    )

    # Determine Master Banner Status
    active_signal = setup_a_signal or setup_b_signal
    if hard_stop_breached:
        banner = {
            "code": "INVALIDATED",
            "severity": "danger",
            "headline": f"STAND DOWN — NVDA BREACHED ${HARD_STOP_NVDA:.2f} HARD GUARD",
            "subtext": (
                f"NVDA traded down to ${min(nvda_live_px, rth_low_live or nvda_live_px):.2f}, filling yesterday's "
                f"${nvda_prev_close:.2f} close. Oversold gap-and-hold thesis is invalidated."
            ),
        }
    elif active_signal is not None:
        sig_name = (
            "SETUP A (RTH FLUSH & HIGHER-LOW RECLAIM)"
            if active_signal["setup"] == "SETUP_A"
            else "SETUP B (2-BAR PM_VWAP + RTH_VWAP BREAKOUT)"
        )
        pnl_vs_entry = ((nvda_live_px / active_signal["entry_price"]) - 1.0) * 100.0
        banner = {
            "code": f"SIGNAL_FLASH_{active_signal['setup']}",
            "severity": "signal",
            "headline": f"SIGNAL FLASH — {sig_name} CONFIRMED @ ${active_signal['entry_price']:.2f}",
            "subtext": (
                f"Confirmed at {active_signal['confirmed_at']} on {active_signal['bar_open_ts']} 5m bar | "
                f"Live ${nvda_live_px:.2f} ({pnl_vs_entry:+.2f}% vs signal) | "
                f"Hard Stop ${active_signal['hard_stop']:.2f} | T1 ${active_signal['target_1']:.2f} | T2 ${active_signal['target_2']:.2f}"
            ),
        }
    elif is_premarket:
        banner = {
            "code": "PREMARKET_STANDBY",
            "severity": "standby",
            "headline": f"PREMARKET GUARD ACTIVE — DO NOT CHASE ${nvda_live_px:.2f} BEFORE 09:30 BELL",
            "subtext": (
                f"NVDA is {'below' if nvda_live_px < pm_vwap else 'near'} PM_VWAP (${pm_vwap:.2f}). "
                f"94%-100% of historical analogs dip after the bell. Waiting {sec_to_bell // 60}m {sec_to_bell % 60:02d}s "
                f"for RTH flush into ${SETUP_A_ZONE_LOW:.2f}-${SETUP_A_ZONE_HIGH:.2f} (or post-09:45 VWAP reclaim)."
            ),
        }
    elif forming_a_reclaim_preview:
        banner = {
            "code": "SETUP_A_FORMING_TRIGGER",
            "severity": "armed",
            "headline": f"GET READY — SETUP A GREEN HIGHER-LOW CANDLE FORMING (${nvda_live_px:.2f})",
            "subtext": (
                f"Flush low ${setup_a_flush_low:.2f} is in! Current 5m bar holds higher low (${float(forming_rth['l']):.2f}) "
                f"and is green. Signal confirms if still green + gates hold at 5m close in {sec_to_next_5m_close}s!"
            ),
        }
    elif forming_b_bar2_preview:
        banner = {
            "code": "SETUP_B_FORMING_TRIGGER",
            "severity": "armed",
            "headline": f"GET READY — SETUP B BAR 2/2 HOLDING ABOVE ${setup_b_live_hurdle:.2f} (${nvda_live_px:.2f})",
            "subtext": (
                f"Bar 1 already closed above PM_VWAP & RTH_VWAP. Current 5m bar confirms Setup B breakout "
                f"if it closes > ${setup_b_live_hurdle:.2f} in {sec_to_next_5m_close}s!"
            ),
        }
    elif setup_a_probed or forming_in_flush_zone:
        banner = {
            "code": "SETUP_A_ARMED",
            "severity": "armed",
            "headline": f"SETUP A ARMED — NVDA IN FLUSH ZONE (LOW ${effective_flush_low:.2f})",
            "subtext": (
                f"Confluence zone (${SETUP_A_ZONE_LOW:.2f}-${SETUP_A_ZONE_HIGH:.2f}) reached! Do NOT catch falling knife—waiting "
                f"for a completed 5m green higher-low candle above ${effective_flush_low:.2f} (next close in {sec_to_next_5m_close}s)."
            ),
        }
    elif setup_b_consec_count == 1:
        banner = {
            "code": "SETUP_B_ARMED_BAR1",
            "severity": "armed",
            "headline": f"SETUP B ARMED (1/2 BARS) — WATCHING FOR 2ND 5M CLOSE > ${setup_b_live_hurdle:.2f}",
            "subtext": (
                f"1st 5m RTH candle closed above PM_VWAP (${pm_vwap:.2f}) & RTH_VWAP (${rth_vwap_live or 0:.2f}). "
                f"Next 5m bar close in {sec_to_next_5m_close}s."
            ),
        }
    else:
        banner = {
            "code": "RTH_WATCHING",
            "severity": "watching",
            "headline": f"RTH MONITORING — WAITING FOR FLUSH <= ${SETUP_A_ZONE_HIGH:.2f} OR VWAP RECLAIM > ${setup_b_live_hurdle:.2f}",
            "subtext": (
                f"NVDA Live ${nvda_live_px:.2f} | RTH Range ${rth_low_live or nvda_live_px:.2f}-${rth_high_live or nvda_live_px:.2f} | "
                f"PM_VWAP ${pm_vwap:.2f} | RTH_VWAP ${rth_vwap_live or nvda_live_px:.2f} | Next 5m close in {sec_to_next_5m_close}s."
            ),
        }

    # Log initial startup snapshot once
    _log_event(
        f"boot_{session_date}",
        now_et.strftime("%H:%M:%S"),
        "INFO",
        "NVDA Signal Monitor Online (Port 9879)",
        (
            f"Locked anchors: Nov 10 Close ${nvda_prev_close:.2f} | PM Low ${pm_low:.2f} | PM VWAP ${pm_vwap:.2f} | "
            f"PM High ${pm_high:.2f} | 50% Gap-Fill ${gap_fill_50:.2f}."
        ),
    )

    # Setup A & Setup B Structured Cards + Order Plans
    setup_a_entry_est = (
        setup_a_signal["entry_price"]
        if setup_a_signal
        else round(
            nvda_live_px
            if forming_a_reclaim_preview
            else max(SETUP_A_ZONE_LOW + 0.55, min(SETUP_A_ZONE_HIGH, gap_fill_50 + 0.35)),
            2,
        )
    )
    setup_a_tight_stop_est = (
        setup_a_signal["tight_stop"]
        if setup_a_signal
        else round((effective_flush_low - 0.25) if effective_flush_low else (pm_low - 0.35), 2)
    )
    setup_a_card = {
        "name": "Setup A — RTH Morning Shakeout & 5m Higher-Low Reclaim",
        "window": "09:30 – 10:45 AM ET (tracked thru 11:30 AM)",
        "status": (
            "TRIGGERED"
            if setup_a_signal
            else (
                "FORMING RECLAIM"
                if forming_a_reclaim_preview
                else ("ARMED IN ZONE" if (setup_a_probed or forming_in_flush_zone) else "WATCHING")
            )
        ),
        "signal": setup_a_signal,
        "checklist": [
            {
                "label": f"1. RTH Open >= 09:30 ET (No Premarket Chasing)",
                "done": not is_premarket,
                "detail": "LIVE" if not is_premarket else f"Wait {sec_to_bell // 60}m {sec_to_bell % 60:02d}s",
            },
            {
                "label": f"2. NVDA RTH Low Probes ${SETUP_A_ZONE_LOW:.2f}–${SETUP_A_ZONE_HIGH:.2f} (and > ${HARD_STOP_NVDA:.2f})",
                "done": bool(setup_a_probed or forming_in_flush_zone),
                "detail": (
                    f"Flush Low ${effective_flush_low:.2f}"
                    if effective_flush_low is not None
                    else (
                        f"RTH Low ${rth_low_live:.2f} (need <= ${SETUP_A_ZONE_HIGH:.2f}; S4 -1.25% = ${s4_open_flush_px:.2f})"
                        if rth_low_live is not None
                        else f"PM Low ${pm_low:.2f} | 50% Gap ${gap_fill_50:.2f}"
                    )
                ),
            },
            {
                "label": "3. Completed 5m Green Higher-Low Reclaim Candle",
                "done": setup_a_signal is not None,
                "detail": (
                    f"Confirmed @ ${setup_a_signal['entry_price']:.2f} ({setup_a_signal['bar_open_ts']} bar)"
                    if setup_a_signal
                    else (
                        f"FORMING NOW (${nvda_live_px:.2f}, {sec_to_next_5m_close}s left)"
                        if forming_a_reclaim_preview
                        else "Awaiting flush probe + 5m green higher-low close"
                    )
                ),
            },
            {
                "label": f"4. Tailwinds Hold (SOXL > ${SOXL_GATE_MIN:.2f} & CRWV > ${CRWV_GATE_MIN:.2f})",
                "done": gate_t1_state == "PASS" and gate_t2_state == "PASS",
                "detail": f"SOXL ${soxl_live:.2f} | CRWV ${crwv_live:.2f}",
            },
        ],
        "plan": {
            "is_confirmed": setup_a_signal is not None,
            "entry": setup_a_entry_est,
            "limit_cap": round(setup_a_entry_est + 0.10, 2),
            "hard_stop": HARD_STOP_NVDA,
            "tight_stop": setup_a_tight_stop_est,
            "target_1": round(pm_vwap, 2),
            "target_2": round(pm_high, 2),
            "swing_note": "Optional Tranche 2 hold T-4 -> T0 into Tue Nov 17 pre-earnings close (exit before 4:20 PM AMC).",
        },
    }

    setup_b_entry_est = (
        setup_b_signal["entry_price"]
        if setup_b_signal
        else round(max(nvda_live_px if forming_b_bar2_preview else 0.0, setup_b_live_hurdle + 0.15), 2)
    )
    setup_b_stop_est = (
        setup_b_signal["hard_stop"]
        if setup_b_signal
        else round(
            min(
                setup_b_entry_est - 0.75,
                max(SETUP_B_FALLBACK_STOP, rth_low_live if rth_low_live is not None else SETUP_B_FALLBACK_STOP),
            ),
            2,
        )
    )
    setup_b_card = {
        "name": "Setup B — Post-09:45 PM_VWAP + RTH_VWAP Strength Reclaim",
        "window": ">= 09:45 AM ET (if NVDA refuses to flush deeply)",
        "status": (
            "TRIGGERED"
            if setup_b_signal
            else (
                "FORMING BAR 2/2"
                if forming_b_bar2_preview
                else ("ARMED (BAR 1/2)" if setup_b_consec_count >= 1 else "WATCHING")
            )
        ),
        "signal": setup_b_signal,
        "checklist": [
            {
                "label": "1. Opening Shakeout Window >= 09:45 AM ET",
                "done": not is_premarket and (now_et.hour * 100 + now_et.minute) >= 945,
                "detail": f"Current {now_et.strftime('%H:%M ET')}",
            },
            {
                "label": f"2. Bar 1/2 Closes Above PM_VWAP & RTH_VWAP (> ${setup_b_live_hurdle:.2f})",
                "done": setup_b_consec_count >= 1 or setup_b_signal is not None,
                "detail": f"Consecutive closes above hurdle: {2 if setup_b_signal else setup_b_consec_count}/2",
            },
            {
                "label": f"3. Bar 2/2 Green Follow-Through Close (> ${setup_b_live_hurdle:.2f})",
                "done": setup_b_signal is not None,
                "detail": (
                    f"Confirmed @ ${setup_b_signal['entry_price']:.2f} ({setup_b_signal['bar_open_ts']} bar)"
                    if setup_b_signal
                    else (
                        f"FORMING BAR 2/2 (${nvda_live_px:.2f}, {sec_to_next_5m_close}s left)"
                        if forming_b_bar2_preview
                        else "Waiting for 2 consecutive 5m closes"
                    )
                ),
            },
            {
                "label": f"4. Tailwinds Hold (SOXL > ${SOXL_GATE_MIN:.2f} & CRWV > ${CRWV_GATE_MIN:.2f})",
                "done": gate_t1_state == "PASS" and gate_t2_state == "PASS",
                "detail": f"SOXL ${soxl_live:.2f} | CRWV ${crwv_live:.2f}",
            },
        ],
        "plan": {
            "is_confirmed": setup_b_signal is not None,
            "entry": setup_b_entry_est,
            "limit_cap": round(setup_b_entry_est + 0.10, 2),
            "hard_stop": setup_b_stop_est,
            "tight_stop": setup_b_stop_est,
            "target_1": round(pm_high, 2),
            "target_2": SETUP_B_TARGET_2,
            "swing_note": "Momentum reclaim toward PM High ($178.36) and Nov 9 breakdown high ($179.92/$180.00).",
        },
    }

    # Assemble intraday chart bars (04:00 PM + 09:30 RTH)
    chart_bars: List[Dict[str, Any]] = []
    for b in nvda_pm_bars:
        chart_bars.append(
            {
                "ts": b["ts_label"],
                "epoch_ms": b["epoch_ms"],
                "session": "PM",
                "o": round(float(b["o"]), 2),
                "h": round(float(b["h"]), 2),
                "l": round(float(b["l"]), 2),
                "c": round(float(b["c"]), 2),
                "v": int(b["v"]),
                "rth_vwap": None,
                "forming": False,
            }
        )
    for b in completed_rth:
        chart_bars.append(
            {
                "ts": b["ts_label"],
                "epoch_ms": b["epoch_ms"],
                "session": "RTH",
                "o": round(float(b["o"]), 2),
                "h": round(float(b["h"]), 2),
                "l": round(float(b["l"]), 2),
                "c": round(float(b["c"]), 2),
                "v": int(b["v"]),
                "rth_vwap": round(float(b["rth_vwap"]), 2) if b.get("rth_vwap") else None,
                "forming": False,
            }
        )
    if forming_rth is not None:
        chart_bars.append(
            {
                "ts": forming_rth["ts_label"],
                "epoch_ms": forming_rth["epoch_ms"],
                "session": "RTH",
                "o": round(float(forming_rth["o"]), 2),
                "h": round(float(forming_rth["h"]), 2),
                "l": round(float(forming_rth["l"]), 2),
                "c": round(float(forming_rth["c"]), 2),
                "v": int(forming_rth["v"]),
                "rth_vwap": round(float(forming_rth["rth_vwap"]), 2) if forming_rth.get("rth_vwap") else None,
                "forming": True,
            }
        )

    return {
        "ok": True,
        "updated_at_et": now_et.strftime("%Y-%m-%d %H:%M:%S ET"),
        "session_date": str(session_date),
        "prev_session_date": str(prev_session_date) if prev_session_date else "2026-11-10",
        "market_phase": "PREMARKET" if is_premarket else ("RTH" if is_rth_open else ("AFTER_HOURS" if is_after_hours else "HISTORICAL")),
        "sec_to_bell": sec_to_bell,
        "sec_to_next_5m_close": sec_to_next_5m_close,
        "banner": banner,
        "levels": {
            "prev_close": round(nvda_prev_close, 2),
            "hard_stop": HARD_STOP_NVDA,
            "flush_zone_low": SETUP_A_ZONE_LOW,
            "flush_zone_high": SETUP_A_ZONE_HIGH,
            "pm_low": round(pm_low, 2),
            "gap_fill_50": gap_fill_50,
            "s4_open_flush": s4_open_flush_px,
            "rth_open": round(rth_open, 2) if rth_open is not None else None,
            "rth_low": round(rth_low_live, 2) if rth_low_live is not None else None,
            "rth_high": round(rth_high_live, 2) if rth_high_live is not None else None,
            "rth_vwap": round(rth_vwap_live, 2) if rth_vwap_live is not None else None,
            "pm_vwap": round(pm_vwap, 2),
            "setup_b_hurdle": setup_b_live_hurdle,
            "pm_high": round(pm_high, 2),
            "target_180": SETUP_B_TARGET_2,
        },
        "nvda": nvda_peer,
        "gates": gates,
        "setup_a": setup_a_card,
        "setup_b": setup_b_card,
        "peers": [peers[s] for s in SYMBOLS if s in peers],
        "chart_bars": chart_bars,
        "signals": [s for s in (setup_a_signal, setup_b_signal) if s is not None],
        "events": list(_event_log[:25]),
    }


def _background_worker() -> None:
    while not _stop_event.is_set():
        try:
            snap = _poll_once()
            with _state_lock:
                _latest_state.clear()
                _latest_state.update(snap)
        except Exception as exc:
            now_str = datetime.datetime.now(NY_TZ).strftime("%H:%M:%S ET")
            with _state_lock:
                _latest_state["last_error"] = f"{now_str}: {exc}"
                if not _latest_state.get("ok"):
                    _latest_state["status"] = "FEED_RETRYING"
                    _latest_state["message"] = f"Feed retry ({exc})"
        _stop_event.wait(POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Prime initial state synchronously so the very first HTTP request gets live data immediately
    try:
        snap = _poll_once()
        with _state_lock:
            _latest_state.clear()
            _latest_state.update(snap)
    except Exception as exc:
        with _state_lock:
            _latest_state["last_error"] = str(exc)
    worker = threading.Thread(target=_background_worker, name="nvda-poller", daemon=True)
    worker.start()
    yield
    _stop_event.set()


app = FastAPI(title="NVDA Signal Monitor (Port 9879)", lifespan=lifespan)


@app.get("/api/state")
def get_state() -> JSONResponse:
    with _state_lock:
        payload = dict(_latest_state)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>NVDA Signal Monitor — Port 9879</title>
<style>
  :root {
    --bg: #080c14;
    --panel: #0f1623;
    --panel-2: #141d2e;
    --border: #1f2d46;
    --text: #e6edf7;
    --muted: #8b9bb4;
    --green: #10b981;
    --green-bright: #34d399;
    --amber: #f59e0b;
    --red: #ef4444;
    --blue: #3b82f6;
    --cyan: #06b6d4;
    --purple: #a855f7;
    --gold: #facc15;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", Segoe UI, Roboto, sans-serif;
    line-height: 1.4;
    padding: 14px 18px 32px;
  }
  .mono { font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }

  /* Top Bar */
  .topbar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .live-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 10px var(--green);
    animation: pulseDot 1.8s infinite;
  }
  @keyframes pulseDot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.85); }
  }
  .brand h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }
  .phase-pill {
    font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px;
    background: #1e293b; color: #93c5fd; border: 1px solid #334155;
  }
  .controls {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  }
  button.btn {
    background: var(--panel-2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 11px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  button.btn:hover { border-color: #3b82f6; background: #19253b; }
  button.btn.active {
    background: rgba(16, 185, 129, 0.18);
    border-color: var(--green);
    color: var(--green-bright);
  }
  .meta-clock { font-size: 12px; color: var(--muted); }

  /* Master Signal Banner */
  .banner {
    border-radius: 10px;
    padding: 15px 18px;
    margin-bottom: 14px;
    border: 2px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .banner.standby {
    background: linear-gradient(90deg, rgba(59,130,246,0.16), rgba(15,22,35,0.95));
    border-color: #2563eb;
  }
  .banner.watching {
    background: linear-gradient(90deg, rgba(6,182,212,0.14), rgba(15,22,35,0.95));
    border-color: #0891b2;
  }
  .banner.armed {
    background: linear-gradient(90deg, rgba(245,158,11,0.24), rgba(15,22,35,0.95));
    border-color: var(--amber);
    animation: pulseAmber 1.6s infinite;
  }
  .banner.signal {
    background: linear-gradient(90deg, rgba(16,185,129,0.32), rgba(6,78,59,0.55));
    border-color: var(--green-bright);
    box-shadow: 0 0 28px rgba(16,185,129,0.35);
    animation: pulseGreen 1.2s infinite;
  }
  .banner.danger {
    background: linear-gradient(90deg, rgba(239,68,68,0.28), rgba(15,22,35,0.95));
    border-color: var(--red);
  }
  @keyframes pulseAmber {
    0%, 100% { box-shadow: 0 0 0 rgba(245,158,11,0); }
    50% { box-shadow: 0 0 22px rgba(245,158,11,0.35); }
  }
  @keyframes pulseGreen {
    0%, 100% { box-shadow: 0 0 12px rgba(16,185,129,0.25); }
    50% { box-shadow: 0 0 34px rgba(52,211,153,0.65); }
  }
  .banner-title { font-size: 19px; font-weight: 800; letter-spacing: -0.01em; margin-bottom: 4px; }
  .banner-sub { font-size: 13px; color: #cbd5e1; }
  .hero-quote {
    text-align: right;
    min-width: 195px;
  }
  .hero-price { font-size: 30px; font-weight: 800; line-height: 1.05; }
  .hero-chg { font-size: 13px; font-weight: 700; margin-top: 2px; }
  .pos { color: var(--green-bright); }
  .neg { color: var(--red); }
  .warn-txt { color: var(--amber); }

  /* Peer Tailwind Strip */
  .peer-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(122px, 1fr));
    gap: 8px;
    margin-bottom: 14px;
  }
  .peer-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
  }
  .peer-card.highlight { border-color: #2c4268; background: #121c2e; }
  .peer-top { display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; font-weight: 700; }
  .peer-px { font-size: 16px; font-weight: 800; margin: 2px 0; }
  .peer-sub { font-size: 10.5px; color: var(--muted); }

  /* Main Grid */
  .grid-main {
    display: grid;
    grid-template-columns: 1.55fr 1fr;
    gap: 14px;
    margin-bottom: 14px;
  }
  @media (max-width: 1120px) {
    .grid-main { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 13px 15px;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    gap: 8px;
  }
  .card-title { font-size: 13.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #cbd5e1; }

  /* Chart + Level Ladder */
  .chart-wrap {
    width: 100%;
    height: 350px;
    position: relative;
  }
  canvas#nvdaChart {
    width: 100%;
    height: 100%;
    display: block;
    border-radius: 6px;
    background: #090e18;
  }
  .legend-row {
    display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; font-size: 11px; color: var(--muted);
  }
  .leg-item { display: flex; align-items: center; gap: 5px; }
  .leg-swatch { width: 12px; height: 3px; border-radius: 2px; }

  /* Gates Grid */
  .gates-list { display: grid; gap: 8px; }
  .gate-row {
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px 11px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }
  .gate-badge {
    font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 5px; white-space: nowrap;
  }
  .badge-PASS { background: rgba(16,185,129,0.18); color: var(--green-bright); border: 1px solid rgba(16,185,129,0.45); }
  .badge-WARN, .badge-STANDBY, .badge-ARMED { background: rgba(245,158,11,0.18); color: #fbbf24; border: 1px solid rgba(245,158,11,0.45); }
  .badge-FAIL { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.45); }
  .badge-CLOSED { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }

  /* Setups + Order Sizer */
  .grid-setups {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 14px;
  }
  @media (max-width: 980px) {
    .grid-setups { grid-template-columns: 1fr; }
  }
  .setup-card.triggered { border: 2px solid var(--green-bright); box-shadow: 0 0 20px rgba(16,185,129,0.2); }
  .setup-card.armed { border: 1.5px solid var(--amber); }
  .checklist { list-style: none; display: grid; gap: 7px; margin: 10px 0 12px; }
  .check-item {
    display: flex; justify-content: space-between; align-items: center; gap: 10px;
    font-size: 12.5px; padding: 7px 9px; border-radius: 6px; background: var(--panel-2);
    border: 1px solid #1b273d;
  }
  .check-item.done { border-color: rgba(16,185,129,0.4); background: rgba(16,185,129,0.07); }
  .check-left { display: flex; align-items: center; gap: 7px; }
  .check-icon { font-weight: 800; font-size: 13px; }
  .check-detail { font-size: 11.5px; color: var(--muted); text-align: right; }

  .plan-box {
    background: #0a101b;
    border: 1px solid #22324f;
    border-radius: 8px;
    padding: 10px 12px;
  }
  .plan-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 8px;
  }
  .plan-kv .k { font-size: 10.5px; color: var(--muted); text-transform: uppercase; }
  .plan-kv .v { font-size: 14.5px; font-weight: 800; margin-top: 2px; }

  /* Sizer & Log Bottom Row */
  .grid-bottom {
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 14px;
  }
  @media (max-width: 980px) {
    .grid-bottom { grid-template-columns: 1fr; }
  }
  .sizer-controls {
    display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin-bottom: 10px;
  }
  input.num-input {
    background: #090e18; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 9px; width: 115px; font-size: 13px; font-weight: 700;
  }
  .ticket-table {
    width: 100%; border-collapse: collapse; font-size: 12.5px;
  }
  .ticket-table th, .ticket-table td {
    padding: 7px 8px; border-bottom: 1px solid #1a253a; text-align: left;
  }
  .ticket-table th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; }

  .event-list {
    max-height: 230px; overflow-y: auto; display: grid; gap: 6px;
  }
  .ev-item {
    font-size: 12px; padding: 7px 9px; border-radius: 6px; background: var(--panel-2);
    border-left: 3px solid #3b82f6;
  }
  .ev-item.SIGNAL { border-left-color: var(--green-bright); background: rgba(16,185,129,0.11); }
  .ev-item.ARMED { border-left-color: var(--amber); background: rgba(245,158,11,0.09); }
  .ev-item.DANGER { border-left-color: var(--red); background: rgba(239,68,68,0.12); }
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <div class="live-dot" id="liveDot"></div>
    <h1>NVDA Signal Monitor <span style="color:var(--muted);font-weight:500;">| CRWV &amp; SOXL Tailwind Playbook</span></h1>
    <span class="phase-pill mono" id="phasePill">BOOTING</span>
  </div>
  <div class="controls">
    <span class="meta-clock mono" id="clockText">--:--:-- ET</span>
    <button class="btn" id="audioBtn" onclick="toggleAudio()">🔔 Enable Audio + Desktop Alerts</button>
    <button class="btn" onclick="playAlertChime('SIGNAL')">🔊 Test Chime</button>
    <button class="btn" onclick="fetchState()">↻ Refresh Now</button>
  </div>
</div>

<div class="banner standby" id="masterBanner">
  <div style="max-width: 74%;">
    <div class="banner-title" id="bannerHeadline">Connecting to real-time CNBC 5M feed...</div>
    <div class="banner-sub" id="bannerSubtext">Evaluating NVDA, CRWV, SOXL, and Premarket VWAP anchors...</div>
  </div>
  <div class="hero-quote mono">
    <div class="hero-price" id="nvdaHeroPx">$---.--</div>
    <div class="hero-chg" id="nvdaHeroChg">--% vs Prev Close</div>
    <div style="font-size:11px;color:var(--muted);margin-top:3px;" id="timerSub">5m close: --s</div>
  </div>
</div>

<div class="peer-strip" id="peerStrip"></div>

<div class="grid-main">
  <div class="card">
    <div class="card-header">
      <div class="card-title">NVDA 5-Minute Extended + RTH Chart &amp; Key Levels</div>
      <div class="mono" style="font-size:11.5px;color:var(--muted);" id="chartMeta">--</div>
    </div>
    <div class="chart-wrap">
      <canvas id="nvdaChart"></canvas>
    </div>
    <div class="legend-row">
      <div class="leg-item"><span class="leg-swatch" style="background:#facc15;"></span>PM VWAP (T1)</div>
      <div class="leg-item"><span class="leg-swatch" style="background:#a855f7;"></span>Live RTH VWAP</div>
      <div class="leg-item"><span class="leg-swatch" style="background:#06b6d4;"></span>PM High (T2)</div>
      <div class="leg-item"><span class="leg-swatch" style="background:#10b981;height:8px;opacity:0.45;"></span>Setup A Flush Zone ($170.90–$172.20)</div>
      <div class="leg-item"><span class="leg-swatch" style="background:#ef4444;"></span>Hard Stop ($168.40)</div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="card-title">Live Tailwind &amp; Safety Gates</div>
      <div class="mono" style="font-size:11.5px;color:var(--muted);" id="levelSummaryTag">--</div>
    </div>
    <div class="gates-list" id="gatesList"></div>
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border);font-size:12px;">
      <div style="font-weight:700;color:#cbd5e1;margin-bottom:6px;">LOCKED REFERENCE LADDER</div>
      <div id="ladderGrid" class="mono" style="display:grid;grid-template-columns:1fr 1fr;gap:5px 14px;font-size:11.5px;"></div>
    </div>
  </div>
</div>

<div class="grid-setups">
  <div class="card setup-card" id="setupACard"></div>
  <div class="card setup-card" id="setupBCard"></div>
</div>

<div class="grid-bottom">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Position Sizer &amp; Execution Order Ticket</div>
      <button class="btn" onclick="copyOrderTicket()" id="copyBtn">📋 Copy Order Plan</button>
    </div>
    <div class="sizer-controls">
      <span style="font-size:12px;color:var(--muted);">Capital:</span>
      <button class="btn" onclick="setNotional(25000)">$25k</button>
      <button class="btn" onclick="setNotional(50000)">$50k</button>
      <button class="btn active" id="cap100" onclick="setNotional(100000)">$100k</button>
      <button class="btn" onclick="setNotional(150000)">$150k</button>
      <input type="number" id="notionalInput" class="num-input mono" value="100000" step="5000" oninput="renderSizer()" />
      <select id="setupSelect" class="num-input" style="width:auto;" onchange="renderSizer()">
        <option value="AUTO">Auto (Active / Setup A)</option>
        <option value="A">Setup A (Flush-Reclaim)</option>
        <option value="B">Setup B (VWAP Breakout)</option>
      </select>
    </div>
    <div id="ticketContainer"></div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="card-title">Real-Time Signal &amp; Condition Log</div>
      <span class="mono" style="font-size:11px;color:var(--muted);">5s poll / causal 5m replay</span>
    </div>
    <div class="event-list" id="eventList"></div>
  </div>
</div>

<script>
let latestState = null;
let audioEnabled = false;
let audioCtx = null;
let lastAlertedBannerCode = null;
let lastTicketCopyText = "";

function ensureAudioCtx() {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) audioCtx = new AC();
  }
  if (audioCtx && audioCtx.state === "suspended") {
    audioCtx.resume();
  }
}

function toggleAudio() {
  ensureAudioCtx();
  audioEnabled = !audioEnabled;
  const btn = document.getElementById("audioBtn");
  if (audioEnabled) {
    btn.classList.add("active");
    btn.textContent = "🔔 Alerts ARMED (Audio + Desktop)";
    playAlertChime("ARMED");
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  } else {
    btn.classList.remove("active");
    btn.textContent = "🔔 Enable Audio + Desktop Alerts";
  }
}

function playAlertChime(kind) {
  ensureAudioCtx();
  if (!audioCtx) return;
  const now = audioCtx.currentTime;
  const notes = kind === "SIGNAL" ? [587.33, 783.99, 1046.5, 1318.5] : (kind === "DANGER" ? [330, 246.94] : [523.25, 659.25]);
  notes.forEach((freq, idx) => {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = kind === "DANGER" ? "sawtooth" : "triangle";
    osc.frequency.setValueAtTime(freq, now + idx * 0.13);
    gain.gain.setValueAtTime(0.0001, now + idx * 0.13);
    gain.gain.exponentialRampToValueAtTime(0.22, now + idx * 0.13 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.13 + 0.24);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(now + idx * 0.13);
    osc.stop(now + idx * 0.13 + 0.25);
  });
}

function maybeNotifyTransition(banner) {
  if (!banner || !banner.code) return;
  if (lastAlertedBannerCode === null) {
    lastAlertedBannerCode = banner.code;
    return;
  }
  if (banner.code !== lastAlertedBannerCode) {
    lastAlertedBannerCode = banner.code;
    const isSig = banner.severity === "signal";
    const isArm = banner.severity === "armed";
    const isDanger = banner.severity === "danger";
    if (audioEnabled && (isSig || isArm || isDanger)) {
      playAlertChime(isSig ? "SIGNAL" : (isDanger ? "DANGER" : "ARMED"));
    }
    if (audioEnabled && "Notification" in window && Notification.permission === "granted" && (isSig || isArm || isDanger)) {
      new Notification(banner.headline, { body: banner.subtext });
    }
  }
}

function fmtPct(v) {
  if (v === null || v === undefined) return "--";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

function setNotional(val) {
  document.getElementById("notionalInput").value = val;
  document.querySelectorAll(".sizer-controls .btn").forEach(b => b.classList.remove("active"));
  renderSizer();
}

function renderSetupCard(elId, card, badgePrefix) {
  const el = document.getElementById(elId);
  const st = card.status;
  el.className = "card setup-card" + (st === "TRIGGERED" ? " triggered" : (st.includes("ARMED") || st.includes("FORMING") ? " armed" : ""));
  const badgeCls = st === "TRIGGERED" ? "badge-PASS" : (st === "WATCHING" ? "badge-CLOSED" : "badge-ARMED");
  const checksHtml = card.checklist.map(c => `
    <li class="check-item ${c.done ? 'done' : ''}">
      <div class="check-left">
        <span class="check-icon ${c.done ? 'pos' : 'warn-txt'}">${c.done ? '✓' : '○'}</span>
        <span>${c.label}</span>
      </div>
      <span class="check-detail mono">${c.detail}</span>
    </li>
  `).join("");

  const p = card.plan;
  el.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-title">${card.name}</div>
        <div style="font-size:11.5px;color:var(--muted);margin-top:2px;">Window: ${card.window}</div>
      </div>
      <span class="gate-badge ${badgeCls} mono">${st}</span>
    </div>
    <ul class="checklist">${checksHtml}</ul>
    <div class="plan-box">
      <div style="font-size:11px;font-weight:700;color:${p.is_confirmed ? 'var(--green-bright)' : 'var(--muted)'};margin-bottom:6px;">
        ${p.is_confirmed ? 'CONFIRMED SIGNAL PARAMETERS' : 'PROJECTED EXECUTION PARAMETERS (WAITING FOR TRIGGER)'}
      </div>
      <div class="plan-grid mono">
        <div class="plan-kv"><div class="k">${p.is_confirmed ? 'Signal Px' : 'Est Entry'}</div><div class="v">$${p.entry.toFixed(2)}</div></div>
        <div class="plan-kv"><div class="k">Hard Stop</div><div class="v neg">$${p.hard_stop.toFixed(2)}</div></div>
        <div class="plan-kv"><div class="k">Tranche 1 (50%)</div><div class="v pos">$${p.target_1.toFixed(2)}</div></div>
        <div class="plan-kv"><div class="k">Tranche 2 (50%)</div><div class="v pos">$${p.target_2.toFixed(2)}</div></div>
      </div>
      <div style="font-size:11.5px;color:var(--muted);">
        Tight structural stop ref: <span class="mono" style="color:var(--text);">$${p.tight_stop.toFixed(2)}</span> &bull; ${p.swing_note}
      </div>
    </div>
  `;
}

function renderSizer() {
  if (!latestState || !latestState.ok) return;
  const notional = Math.max(1000, parseFloat(document.getElementById("notionalInput").value || "100000"));
  const mode = document.getElementById("setupSelect").value;
  let chosen = latestState.setup_a;
  if (mode === "B") {
    chosen = latestState.setup_b;
  } else if (mode === "AUTO") {
    if (latestState.setup_b.status === "TRIGGERED" && latestState.setup_a.status !== "TRIGGERED") {
      chosen = latestState.setup_b;
    } else if (latestState.setup_b.status.includes("FORMING") && latestState.setup_a.status === "WATCHING") {
      chosen = latestState.setup_b;
    }
  }
  const p = chosen.plan;
  const shares = Math.max(1, Math.floor(notional / p.entry));
  const t1Shares = Math.floor(shares / 2);
  const t2Shares = shares - t1Shares;
  const deployed = shares * p.entry;

  const riskHard = shares * Math.max(0.01, p.entry - p.hard_stop);
  const riskTight = shares * Math.max(0.01, p.entry - p.tight_stop);
  const gainT1 = t1Shares * (p.target_1 - p.entry);
  const gainT2 = t2Shares * (p.target_2 - p.entry);
  const totalBlendedGain = gainT1 + gainT2;
  const rMultHard = totalBlendedGain / riskHard;
  const rMultTight = totalBlendedGain / riskTight;

  lastTicketCopyText = [
    `NVDA Trade Plan (${chosen.name}) — ${p.is_confirmed ? 'CONFIRMED SIGNAL' : 'STANDBY / PROJECTED'}`,
    `Buy ${shares} sh NVDA Limit @ $${p.limit_cap.toFixed(2)} (Ref $${p.entry.toFixed(2)}, Deployed $${deployed.toLocaleString(undefined,{maximumFractionDigits:0})})`,
    `Hard Stop: ${shares} sh @ $${p.hard_stop.toFixed(2)} (-$${riskHard.toFixed(0)} | Tight Stop $${p.tight_stop.toFixed(2)} = -$${riskTight.toFixed(0)})`,
    `Tranche 1 Sell (50% = ${t1Shares} sh): Limit @ $${p.target_1.toFixed(2)} (+$${gainT1.toFixed(0)})`,
    `Tranche 2 Sell (50% = ${t2Shares} sh): Limit @ $${p.target_2.toFixed(2)} (+$${gainT2.toFixed(0)}) or hold T-4->T0 into Tue Nov 17 close`
  ].join("\n");

  document.getElementById("ticketContainer").innerHTML = `
    <table class="ticket-table mono">
      <thead>
        <tr>
          <th>Leg</th>
          <th>Action / Shares</th>
          <th>Price</th>
          <th>$ Impact</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>ENTRY</strong></td>
          <td>BUY <strong>${shares}</strong> sh</td>
          <td><strong>$${p.entry.toFixed(2)}</strong> (Lmt $${p.limit_cap.toFixed(2)})</td>
          <td>$${deployed.toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
          <td>${p.is_confirmed ? '<span class="pos">SIGNAL ACTIVE</span>' : '<span class="warn-txt">WAIT FOR SIGNAL</span>'}</td>
        </tr>
        <tr>
          <td><strong>HARD STOP</strong></td>
          <td class="neg">STOP ${shares} sh</td>
          <td class="neg">$${p.hard_stop.toFixed(2)}</td>
          <td class="neg">-$${riskHard.toLocaleString(undefined, {maximumFractionDigits: 0})} (-${((riskHard/deployed)*100).toFixed(2)}%)</td>
          <td>Tight stop $${p.tight_stop.toFixed(2)} (-$${riskTight.toFixed(0)})</td>
        </tr>
        <tr>
          <td><strong>TRANCHE 1</strong></td>
          <td class="pos">SELL ${t1Shares} sh (50%)</td>
          <td class="pos">$${p.target_1.toFixed(2)}</td>
          <td class="pos">+$${gainT1.toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
          <td>Move stop to breakeven on fill</td>
        </tr>
        <tr>
          <td><strong>TRANCHE 2</strong></td>
          <td class="pos">SELL ${t2Shares} sh (50%)</td>
          <td class="pos">$${p.target_2.toFixed(2)}</td>
          <td class="pos">+$${gainT2.toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
          <td>Blended +$${totalBlendedGain.toFixed(0)} (${rMultHard.toFixed(2)}R hard / ${rMultTight.toFixed(2)}R tight)</td>
        </tr>
      </tbody>
    </table>
  `;
}

function copyOrderTicket() {
  if (!lastTicketCopyText) return;
  navigator.clipboard.writeText(lastTicketCopyText).then(() => {
    const btn = document.getElementById("copyBtn");
    btn.textContent = "✓ Copied!";
    setTimeout(() => { btn.textContent = "📋 Copy Order Plan"; }, 1600);
  });
}

function drawChart(state) {
  const canvas = document.getElementById("nvdaChart");
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  ctx.clearRect(0, 0, W, H);

  const bars = state.chart_bars || [];
  if (!bars.length) return;

  const lv = state.levels;
  const padL = 10, padR = 68, padT = 14, padB = 24;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  let minP = Math.min(lv.hard_stop - 0.4, ...bars.map(b => b.l));
  let maxP = Math.max(lv.pm_high + 0.5, ...bars.map(b => b.h));
  const rangeP = Math.max(1.0, maxP - minP);
  const yOf = (p) => padT + ((maxP - p) / rangeP) * plotH;
  const stepX = plotW / Math.max(bars.length, 1);
  const xOf = (i) => padL + (i + 0.5) * stepX;

  // Shade Premarket vs RTH background
  const firstRthIdx = bars.findIndex(b => b.session === "RTH");
  if (firstRthIdx === -1) {
    ctx.fillStyle = "rgba(30, 41, 59, 0.26)";
    ctx.fillRect(padL, padT, plotW, plotH);
  } else if (firstRthIdx > 0) {
    const splitX = padL + firstRthIdx * stepX;
    ctx.fillStyle = "rgba(30, 41, 59, 0.28)";
    ctx.fillRect(padL, padT, splitX - padL, plotH);
    ctx.strokeStyle = "#475569";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(splitX, padT);
    ctx.lineTo(splitX, padT + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 10px -apple-system, sans-serif";
    ctx.fillText("09:30 BELL", splitX + 4, padT + 11);
  }

  // Setup A Confluence Flush Zone Band ($170.90 - $172.20)
  const yZTop = yOf(lv.flush_zone_high);
  const yZBot = yOf(lv.flush_zone_low);
  ctx.fillStyle = "rgba(16, 185, 129, 0.13)";
  ctx.fillRect(padL, yZTop, plotW, Math.max(2, yZBot - yZTop));
  ctx.strokeStyle = "rgba(16, 185, 129, 0.45)";
  ctx.lineWidth = 1;
  ctx.strokeRect(padL, yZTop, plotW, Math.max(2, yZBot - yZTop));

  // Horizontal Reference Lines
  const hLines = [
    { p: lv.pm_high, color: "#06b6d4", label: `PM Hi ${lv.pm_high.toFixed(2)}`, dash: [4, 3] },
    { p: lv.pm_vwap, color: "#facc15", label: `PM VWAP ${lv.pm_vwap.toFixed(2)}`, dash: [5, 3] },
    { p: lv.flush_zone_high, color: "#10b981", label: `Zone ${lv.flush_zone_high.toFixed(2)}`, dash: [2, 3] },
    { p: lv.prev_close, color: "#64748b", label: `Cls ${lv.prev_close.toFixed(2)}`, dash: [3, 3] },
    { p: lv.hard_stop, color: "#ef4444", label: `Stop ${lv.hard_stop.toFixed(2)}`, dash: [] },
  ];
  ctx.font = "10.5px SF Mono, Menlo, monospace";
  hLines.forEach(hl => {
    if (hl.p < minP || hl.p > maxP) return;
    const y = yOf(hl.p);
    ctx.strokeStyle = hl.color;
    ctx.lineWidth = hl.dash.length ? 1 : 1.4;
    ctx.setLineDash(hl.dash);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(padL + plotW, y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = hl.color;
    ctx.fillText(hl.label, padL + plotW + 4, y + 3);
  });

  // Candlesticks
  const bodyW = Math.max(2, Math.min(9, stepX * 0.68));
  bars.forEach((b, i) => {
    const x = xOf(i);
    const up = b.c >= b.o;
    const color = up ? "#10b981" : "#ef4444";
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.moveTo(x, yOf(b.h));
    ctx.lineTo(x, yOf(b.l));
    ctx.stroke();

    const yTop = yOf(Math.max(b.o, b.c));
    const yBot = yOf(Math.min(b.o, b.c));
    const bh = Math.max(1.5, yBot - yTop);
    ctx.fillStyle = b.forming ? (up ? "rgba(16,185,129,0.45)" : "rgba(239,68,68,0.45)") : color;
    ctx.fillRect(x - bodyW / 2, yTop, bodyW, bh);
    if (b.forming) {
      ctx.strokeRect(x - bodyW / 2, yTop, bodyW, bh);
    }
  });

  // RTH Running VWAP Curve
  ctx.strokeStyle = "#a855f7";
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  let started = false;
  bars.forEach((b, i) => {
    if (b.rth_vwap !== null && b.rth_vwap !== undefined) {
      const x = xOf(i);
      const y = yOf(b.rth_vwap);
      if (!started) { ctx.moveTo(x, y); started = true; }
      else { ctx.lineTo(x, y); }
    }
  });
  if (started) ctx.stroke();

  // Plot Confirmed Signal Arrows
  (state.signals || []).forEach(sig => {
    const idx = bars.findIndex(b => b.epoch_ms === sig.bar_epoch_ms);
    if (idx >= 0) {
      const x = xOf(idx);
      const y = yOf(bars[idx].l) + 14;
      ctx.fillStyle = "#34d399";
      ctx.beginPath();
      ctx.moveTo(x, y - 10);
      ctx.lineTo(x - 6, y);
      ctx.lineTo(x + 6, y);
      ctx.closePath();
      ctx.fill();
      ctx.font = "bold 10px SF Mono, monospace";
      ctx.fillText(sig.setup === "SETUP_A" ? "BUY A" : "BUY B", x - 16, y + 11);
    }
  });

  // Time X-Axis Labels
  ctx.fillStyle = "#64748b";
  ctx.font = "10px SF Mono, Menlo, monospace";
  const labelStride = Math.max(1, Math.floor(bars.length / 8));
  bars.forEach((b, i) => {
    if (i % labelStride === 0 || i === bars.length - 1) {
      ctx.fillText(b.ts, xOf(i) - 14, H - 6);
    }
  });
}

function renderAll(state) {
  latestState = state;
  if (!state.ok) return;

  maybeNotifyTransition(state.banner);

  // Titlebar for quick glance from another tab
  const nv = state.nvda;
  const pfx = state.banner.severity === "signal" ? "🚨 [BUY SIGNAL]" : (state.banner.severity === "armed" ? "⚡ [ARMED]" : "[WATCH]");
  document.title = `${pfx} NVDA $${nv.last.toFixed(2)} (${fmtPct(nv.chg_pct)})`;

  document.getElementById("phasePill").textContent = state.market_phase;
  document.getElementById("clockText").textContent = state.updated_at_et;

  const bEl = document.getElementById("masterBanner");
  bEl.className = "banner " + state.banner.severity;
  document.getElementById("bannerHeadline").textContent = state.banner.headline;
  document.getElementById("bannerSubtext").textContent = state.banner.subtext;

  document.getElementById("nvdaHeroPx").textContent = "$" + nv.last.toFixed(2);
  const chgEl = document.getElementById("nvdaHeroChg");
  chgEl.textContent = `${fmtPct(nv.chg_pct)} vs $${nv.prev_close.toFixed(2)} | ${fmtPct(nv.vs_pm_vwap_pct)} vs PM_VWAP`;
  chgEl.className = "hero-chg " + (nv.chg_pct >= 0 ? "pos" : "neg");

  document.getElementById("timerSub").textContent = state.market_phase === "PREMARKET"
    ? `09:30 Bell in ${Math.floor(state.sec_to_bell/60)}m ${String(state.sec_to_bell%60).padStart(2,'0')}s`
    : `Next 5m bar close in ${state.sec_to_next_5m_close}s`;

  // Peer Strip
  document.getElementById("peerStrip").innerHTML = state.peers.map(p => {
    const hi = (p.symbol === "NVDA" || p.symbol === "CRWV" || p.symbol === "SOXL") ? "highlight" : "";
    return `
      <div class="peer-card ${hi} mono">
        <div class="peer-top">
          <span>${p.symbol}</span>
          <span class="${p.chg_pct >= 0 ? 'pos' : 'neg'}">${fmtPct(p.chg_pct)}</span>
        </div>
        <div class="peer-px">$${p.last.toFixed(2)}</div>
        <div class="peer-sub">PM VWAP $${p.pm_vwap ? p.pm_vwap.toFixed(2) : '--'} (${fmtPct(p.vs_pm_vwap_pct)})</div>
      </div>
    `;
  }).join("");

  // Gates
  document.getElementById("gatesList").innerHTML = state.gates.map(g => `
    <div class="gate-row">
      <div>
        <div style="font-size:12.5px;font-weight:700;">${g.id}: ${g.name}</div>
        <div style="font-size:11px;color:var(--muted);">${g.note}</div>
        <div class="mono" style="font-size:11px;color:#93c5fd;margin-top:2px;">Now: ${g.current} &bull; Req: ${g.threshold}</div>
      </div>
      <span class="gate-badge badge-${g.state} mono">${g.state}</span>
    </div>
  `).join("");

  const lv = state.levels;
  document.getElementById("levelSummaryTag").textContent = `PM Vol ${nv.pm_vol_m.toFixed(1)}M | RTH Vol ${nv.rth_vol_m.toFixed(1)}M`;
  document.getElementById("ladderGrid").innerHTML = `
    <div>Target 2 (Nov 9 Hi): <strong class="pos">$${lv.target_180.toFixed(2)}</strong></div>
    <div>PM High (T2): <strong style="color:var(--cyan);">$${lv.pm_high.toFixed(2)}</strong></div>
    <div>PM VWAP (T1): <strong style="color:var(--gold);">$${lv.pm_vwap.toFixed(2)}</strong></div>
    <div>Live RTH VWAP: <strong style="color:var(--purple);">${lv.rth_vwap ? '$'+lv.rth_vwap.toFixed(2) : 'Wait 09:30'}</strong></div>
    <div>Flush Zone: <strong class="pos">$${lv.flush_zone_low.toFixed(2)}–$${lv.flush_zone_high.toFixed(2)}</strong></div>
    <div>50% Gap / PM Lo: <strong>$${lv.gap_fill_50.toFixed(2)} / $${lv.pm_low.toFixed(2)}</strong></div>
    <div>Nov 10 Close: <strong>$${lv.prev_close.toFixed(2)}</strong></div>
    <div>Hard Stop Guard: <strong class="neg">$${lv.hard_stop.toFixed(2)}</strong></div>
  `;

  document.getElementById("chartMeta").textContent =
    `${state.session_date} | Last 5m Bar ${nv.last_bar_ts} ET | PM Range $${lv.pm_low.toFixed(2)}–$${lv.pm_high.toFixed(2)}`;

  renderSetupCard("setupACard", state.setup_a);
  renderSetupCard("setupBCard", state.setup_b);
  renderSizer();
  drawChart(state);

  document.getElementById("eventList").innerHTML = (state.events || []).map(ev => `
    <div class="ev-item ${ev.level}">
      <div style="display:flex;justify-content:space-between;font-weight:700;">
        <span>${ev.title}</span>
        <span class="mono" style="color:var(--muted);font-size:11px;">${ev.ts}</span>
      </div>
      <div style="color:#cbd5e1;margin-top:2px;font-size:11.5px;">${ev.detail}</div>
    </div>
  `).join("");
}

async function fetchState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    const data = await res.json();
    renderAll(data);
  } catch (err) {
    console.error("Poll error:", err);
  }
}

window.addEventListener("resize", () => { if (latestState) drawChart(latestState); });
fetchState();
setInterval(fetchState, 3000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)
