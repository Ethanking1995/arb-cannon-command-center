# NVDA Signal Monitor Dashboard (Port 9879)

Real-time intraday monitoring dashboard built for the `NVDA` Oversold + `CRWV` Q3 earnings bounce & `SOXL` rally playbook.

It continuously polls live CNBC Harmony 5-minute extended-hours and RTH bars alongside live tick quotes for `NVDA`, `CRWV`, `SOXL`, `SMH`, `MU`, `AMD`, `AVGO`, `QQQ`, and `SPY`.

---

## Quickstart: How to Run the Dashboard

### 1. Prerequisites
Ensure the virtual environment has `fastapi`, `uvicorn`, and `httpx` installed:

```bash
cd "/Users/ethanking/Desktop/arb cannon dash"
source .venv/bin/activate
pip install fastapi uvicorn httpx
```

### 2. Start the Server on Port 9879

From the repository root (`arb cannon dash`):

```bash
cd "/Users/ethanking/Desktop/arb cannon dash"
.venv/bin/uvicorn server:app --app-dir nvda_signal_monitor --host 127.0.0.1 --port 9879 --reload
```

Or run it directly in the background:

```bash
nohup .venv/bin/uvicorn server:app --app-dir nvda_signal_monitor --host 127.0.0.1 --port 9879 > nvda_signal_monitor/monitor.log 2>&1 &
```

### 3. Open in Browser

- **Dashboard UI**: [http://127.0.0.1:9879](http://127.0.0.1:9879)
- **Live State API**: [http://127.0.0.1:9879/api/state](http://127.0.0.1:9879/api/state)

---

## Strategy Rules & Signals Monitored

1. **Premarket Guard (`< 09:30 ET`)**:
   - Stands down before the bell to avoid chasing below `PM_VWAP` (`~$175.44`). Historical data shows a 94%–100% morning dip rate below premarket prices.

2. **Tailwind & Safety Gates**:
   - **Gate T1 (`SOXL`)**: Must hold `> $62.50` (`+11.8%+` vs `$55.88` close).
   - **Gate T2 (`CRWV`)**: Must hold `> $53.50` (above Premarket Low / `+9.7%+`).
   - **Gate T3 (`NVDA`)**: Hard Stop Guard at `$168.40` (breaching invalidates the bounce).
   - **Gate T4 (`RTH Bell`)**: Requires `>= 09:30:00 ET` open, evaluating confirmations on **completed 5m RTH bars**.

3. **Setup A (Primary Shakeout & Reclaim, `09:30–10:45 ET`)**:
   - **Armed**: `NVDA` dips into `$170.90–$172.20` flush zone while holding `> $168.40`.
   - **Signal Flash**: Completed 5m RTH candle closes green (`Close > Open`) with a higher low (`Low > Flush_Low`) while Gates T1–T3 hold.
   - **Targets**: Tranche 1 (50%) at `PM_VWAP` (`~$175.44`), Tranche 2 (50%) at `PM_High` (`~$178.36`) or pre-earnings swing hold.

4. **Setup B (Strength Reclaim Breakout, `>= 09:45 ET`)**:
   - For sessions where `NVDA` refuses to flush deeply.
   - **Signal Flash**: Two consecutive completed 5m RTH bars close above `max($175.50, PM_VWAP, RTH_VWAP)`.
   - **Stop / Targets**: Stop at `max($173.40, RTH_Low)` | Targets: `$178.36` -> `$180.00`.

---

## Features on the Page

- **Audio & Desktop Chimes**: Click `🔔 Enable Audio + Desktop Alerts` once to arm WebAudio tones and browser notifications for `ARMED` and `SIGNAL FLASH` transitions.
- **Dynamic 5m Candlestick Chart**: Shows Premarket + RTH bars, live RTH VWAP curve, Premarket VWAP line, and flush zone shading.
- **Order Sizer & Copy Ticket**: Configurable dollar allocation (`$25k`, `$50k`, `$100k`, `$150k`) computing exact share counts, dollar risk to hard/tight stops, target payouts, and one-click clipboard copying.
