# Arb Cannon: M&A Leak Arbitrage Command Center

Local, self-hosted quantitative Python web application and automated 5:00 PM EST nightly email reporting daemon dedicated exclusively to **Extended-Hours All-Cash Private Equity M&A Leak Arbitrage ("Leak-to-8-K Convergence")**.

## Core Features
- **100% Read-Only Public Market & SEC EDGAR Architecture**: Pulls extended-hours market data via `yfinance` (`prepost=True`), official SEC EDGAR XBRL balance-sheet & Form 8-K Item 1.01 submissions (`data.sec.gov`), and Google News RSS wires. Zero brokerage credentials required.
- **Strict M&A RSS Wire Filter**: Requires hard M&A phrases (`"in talks"`, `"advanced talks"`, `"nearing a deal"`, `"take private"`, `"take-private"`, `"buyout"`, `"to acquire"`, `"acquisition"`, `"exploring a sale"`, `"unsolicited offer"`, `"per share in cash"`) and strictly excludes earnings/transcript noise (`"Earnings Call"`, `"Q1"`, `"Q2"`, `"Q3"`, `"Q4"`, `"Transcript"`, `" Earnings "`). Never fabricates projected deal prices or probabilities on RSS headlines.
- **`<= 4.0-Hour` Leak Freshness Gate**: Automatically separates fresh actionable leaks (`<= 4.0h` old) from stale rumors (`> 4.0h` old).
- **60-Second EV-to-Equity Net-Debt Waterfall & 3-Tranche Limit Calculator (`GATE_6` & `GATE_7`)**:
  - Audits 10-Q Long-Term Debt + Short-Term Debt + Preferred Stock minus Cash, applies Change-of-Control (`CoC`) dilution buffer, and flags **Take-Under Traps** (`FAIL_TAKE_UNDER`) when implied per-share equity value is below the current extended-hours trading price.
  - Computes the 5:30 PM – 7:00 PM EST 3-Tranche Limit Order Ladder (`40% @ 5.5%`, `35% @ 6.5%`, `25% @ 8.0%` discount) and Dual Tax-Regime P&L (`IRA 0% Tax` vs. `NYC Taxable 54.5% Tax` with `$SGOV` principal drawdown fungibility).
- **5:00 PM EST Nightly Email Daemon (`nightly_mailer.py`)**: Generates `latest_5pm_report.html` and dispatches via `SMTP_SSL` when `.env` credentials are configured.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run unit & endpoint test suite
pytest -v

# Generate 5:00 PM EST HTML briefing (dry-run)
python nightly_mailer.py --dry-run

# Launch FastAPI Command Center on http://127.0.0.1:8088
uvicorn app:app --host 127.0.0.1 --port 8088 --reload

# Launch NVDA Intraday Signal Monitor on http://127.0.0.1:9879
uvicorn server:app --app-dir nvda_signal_monitor --host 127.0.0.1 --port 9879 --reload
```

### NVDA Intraday Signal Monitor (Port 9879)
For full strategy details, tailwind gates (`CRWV` / `SOXL`), and real-time audio/visual alert instructions, see [`nvda_signal_monitor/README.md`](nvda_signal_monitor/README.md).
