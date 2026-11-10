"""
Arb Cannon: M&A Leak Arbitrage Command Center — FastAPI Web Server & Trading Terminal UI (app.py)

Serves the dark-mode institutional trading terminal at http://127.0.0.1:8000 and provides
REST endpoints for M&A wire scanning, SEC EDGAR XBRL Net-Debt & 3-Tranche Limit Order
calculations, Watchlist management, and 5:00 PM EST Email Report generation.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from arb_engine import (
    calculate_deal_mechanics,
    calculate_hft_cooldown,
    evaluate_watchlist,
    get_dashboard_payload,
    modify_watchlist,
    scan_ma_wires,
)
from biopharma_leak_backtest import (
    evaluate_biopharma_bolt_on_candidate,
    run_biopharma_backtest,
)
from nightly_mailer import generate_and_send_nightly_report

app = FastAPI(
    title="Arb Cannon: M&A Leak Arbitrage Command Center",
    description=(
        "Extended-Hours All-Cash Private Equity M&A Leak Arbitrage Command Center "
        "(100% Read-Only Public Market & SEC EDGAR XBRL Data)."
    ),
    version="2.0.0",
)


# ==============================================================================
# PYDANTIC REQUEST SCHEMAS
# ==============================================================================


class CalculateRequest(BaseModel):
    ticker: str = Field(default="BMBL", description="Target stock ticker symbol")
    input_mode: str = Field(
        default="EV_BILLIONS", description="'EV_BILLIONS' or 'PER_SHARE'"
    )
    value: float = Field(
        default=1.30,
        description="Rumored EV in $B (if EV_BILLIONS) or $/sh (if PER_SHARE)",
    )
    clip_usd: float = Field(
        default=380000.0, description="Total target clip allocation in USD"
    )
    coc_dilution_pct: float = Field(
        default=1.5, description="Change-of-Control RSU dilution buffer %"
    )
    current_price_override: Optional[float] = Field(
        default=None, description="Optional override for extended-hours market price"
    )
    use_live_network: bool = Field(
        default=True, description="Fetch live quotes and SEC EDGAR XBRL facts"
    )
    leak_timestamp: Optional[str] = Field(
        default=None, description="Optional ISO timestamp of when the leak broke"
    )
    simulate_fresh_leak: bool = Field(
        default=False,
        description="Simulate a fresh (<4h) leak window to test staging on historical benchmarks",
    )
    strategy_mode: str = Field(
        default="PE_ALL_CASH",
        description="'PE_ALL_CASH' (5.5%/6.5%/8.0% ladder) or 'BIOPHARMA_BOLT_ON' (10.0%/12.5%/15.0% ladder)",
    )
    sweetened_ceiling_per_share: Optional[float] = Field(
        default=None,
        description="Optional sweetened/CVR ceiling price per share in Biopharma Bolt-On mode",
    )


class BiopharmaEvaluateRequest(BaseModel):
    ticker: str = Field(default="RYTM")
    current_price: float = Field(default=113.00)
    unaffected_price: float = Field(default=86.44)
    walk_away_floor_price: float = Field(default=92.00)
    base_cash_bid_per_share: float = Field(default=124.00)
    sweetened_ceiling_per_share: float = Field(default=134.00)
    deal_ev_billions: float = Field(default=10.0)
    fda_approved_commercial_anchor: bool = Field(default=True)
    commercial_drug_name: str = Field(
        default="Imcivree ($92.1M Q3 rev, +79.6% YoY / +29% QoQ) + Nov 2 $750M KKR/Blackstone facility & 1% LG Chem royalty buydown"
    )
    named_pharma_suitor: str = Field(
        default="AstraZeneca ($124/sh Offer) + Reported 2nd Bidder ($134–$145+ Target)"
    )
    zero_moa_overlap: bool = Field(default=True)
    bid_sweetening_or_cvr: bool = Field(default=True)
    clip_usd: float = Field(default=190000.0)
    live_position_usd: float = Field(default=100000.0)
    live_position_entry_price: float = Field(default=113.00)


class ScanRequest(BaseModel):
    use_live_network: bool = Field(default=True)


class WatchlistMutationRequest(BaseModel):
    action: str = Field(
        default="add", description="'add' or 'remove' ticker from watchlist"
    )
    ticker: str = Field(..., description="Target stock ticker")
    company_name: Optional[str] = Field(default=None)
    rumor_headline: Optional[str] = Field(
        default="PE Sponsor all-cash buyout rumor under Gatekeeper review"
    )
    input_mode: str = Field(default="EV_BILLIONS")
    rumored_value: float = Field(default=5.0)
    buyer_type: Optional[str] = Field(default="Financial Sponsor / PE")
    gate_notes: Optional[str] = Field(
        default="Verify 100% cash terms and SEC 10-Q Net Debt."
    )
    use_live_network: bool = Field(default=True)


class FireEmailRequest(BaseModel):
    dry_run: bool = Field(default=True)
    use_live_network: bool = Field(default=True)


class CooldownRequest(BaseModel):
    headline_time_est: str = Field(default="16:18")


# ==============================================================================
# FASTAPI API ENDPOINTS
# ==============================================================================


@app.get("/api/dashboard")
def api_get_dashboard(use_live_network: bool = True) -> Dict[str, Any]:
    """Return complete initial state for the Arb Cannon Command Center dashboard."""
    return get_dashboard_payload(use_live_network=use_live_network)


@app.post("/api/calculate")
def api_calculate(req: CalculateRequest) -> Dict[str, Any]:
    """Run the 60-Second SEC EDGAR XBRL Net-Debt & 3-Tranche Limit Calculator."""
    try:
        result = calculate_deal_mechanics(
            ticker=req.ticker,
            input_mode=req.input_mode,
            value=req.value,
            clip_usd=req.clip_usd,
            coc_dilution_pct=req.coc_dilution_pct,
            current_price_override=req.current_price_override,
            use_live_network=req.use_live_network,
            leak_timestamp=req.leak_timestamp,
            simulate_fresh_leak=req.simulate_fresh_leak,
            strategy_mode=req.strategy_mode,
            sweetened_ceiling_per_share=req.sweetened_ceiling_per_share,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/biopharma-backtest")
def api_get_biopharma_backtest() -> Dict[str, Any]:
    """Return the 2023–2026 Historical Biopharma Pre-Announcement Leak Backtest & Live $RYTM Audit."""
    return run_biopharma_backtest()


@app.post("/api/biopharma-evaluate")
def api_evaluate_biopharma(req: BiopharmaEvaluateRequest) -> Dict[str, Any]:
    """Evaluate a Biopharma Bolt-On M&A candidate against the 6-Gate Biopharma Framework."""
    return evaluate_biopharma_bolt_on_candidate(
        ticker=req.ticker,
        current_price=req.current_price,
        unaffected_price=req.unaffected_price,
        walk_away_floor_price=req.walk_away_floor_price,
        base_cash_bid_per_share=req.base_cash_bid_per_share,
        sweetened_ceiling_per_share=req.sweetened_ceiling_per_share,
        deal_ev_billions=req.deal_ev_billions,
        fda_approved_commercial_anchor=req.fda_approved_commercial_anchor,
        commercial_drug_name=req.commercial_drug_name,
        named_pharma_suitor=req.named_pharma_suitor,
        zero_moa_overlap=req.zero_moa_overlap,
        bid_sweetening_or_cvr=req.bid_sweetening_or_cvr,
        clip_usd=req.clip_usd,
        live_position_usd=req.live_position_usd,
        live_position_entry_price=req.live_position_entry_price,
    )


@app.post("/api/scan")
def api_scan_wires(req: Optional[ScanRequest] = None) -> Dict[str, Any]:
    """Trigger live M&A RSS Wire scan, SEC EDGAR 8-K Item 1.01 check, and Watchlist refresh."""
    use_live = req.use_live_network if req is not None else True
    watchlist_rows = evaluate_watchlist(use_live_network=use_live)
    wire_items = scan_ma_wires(
        use_live_rss=use_live, include_curated_fallback=not use_live
    )
    actionable_count = sum(
        1 for w in wire_items if w.get("is_actionable_trigger")
    )
    return {
        "status": "ok",
        "actionable_trigger_count": actionable_count,
        "wire_items": wire_items,
        "watchlist": watchlist_rows,
    }


@app.post("/api/watchlist")
def api_mutate_watchlist(req: WatchlistMutationRequest) -> Dict[str, Any]:
    """Add or remove a ticker from config.json watchlist and return evaluated watchlist."""
    try:
        modify_watchlist(
            action=req.action,
            item=req.model_dump(),
            ticker=req.ticker,
        )
        updated_rows = evaluate_watchlist(use_live_network=req.use_live_network)
        return {
            "status": "ok",
            "action": req.action,
            "ticker": req.ticker.upper().strip(),
            "watchlist": updated_rows,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/fire-email")
def api_fire_email(req: Optional[FireEmailRequest] = None) -> Dict[str, Any]:
    """Run nightly_mailer.py and return the HTML email preview & delivery metadata."""
    dry_run = req.dry_run if req is not None else True
    use_live = req.use_live_network if req is not None else True
    report_result = generate_and_send_nightly_report(
        dry_run=dry_run, use_live_network=use_live
    )
    return {
        "status": "ok",
        "subject": report_result["subject"],
        "trigger_count": report_result["trigger_count"],
        "wire_hits_count": report_result["wire_hits_count"],
        "delivery_status": report_result["delivery_status"],
        "report_path": report_result["report_path"],
        "generated_at": report_result["generated_at"],
        "html_content": report_result["html_content"],
    }


@app.post("/api/cooldown")
def api_calculate_cooldown(req: CooldownRequest) -> Dict[str, Any]:
    """Calculate T+60m to T+180m post-headline HFT cooldown window."""
    return calculate_hft_cooldown(req.headline_time_est)


# ==============================================================================
# TRADING TERMINAL HTML UI (GET /)
# ==============================================================================

TERMINAL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ARB CANNON // M&amp;A Leak Arbitrage Command Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-canvas: #0B0F19;
      --bg-card: #111827;
      --bg-elevated: #0F172A;
      --border-hairline: #1E293B;
      --border-accent: #334155;
      --text-primary: #F8FAFC;
      --text-secondary: #94A3B8;
      --text-muted: #64748B;
      --emerald: #10B981;
      --emerald-bg: rgba(16, 185, 129, 0.14);
      --amber: #F59E0B;
      --amber-bg: rgba(245, 158, 11, 0.14);
      --crimson: #EF4444;
      --crimson-bg: rgba(239, 68, 68, 0.16);
      --cyan: #38BDF8;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-canvas);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.45;
      font-variant-numeric: tabular-nums;
      min-height: 100vh;
    }

    .mono {
      font-family: var(--font-mono);
      font-variant-numeric: tabular-nums;
    }

    /* TOP COMMAND BAR */
    .command-bar {
      position: sticky;
      top: 0;
      z-index: 100;
      background-color: rgba(11, 15, 25, 0.96);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--border-hairline);
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .brand-block {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-badge {
      background: linear-gradient(135deg, #064E3B 0%, #0F172A 100%);
      border: 1px solid var(--emerald);
      color: var(--emerald);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 4px;
      letter-spacing: 0.8px;
    }

    .brand-title {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text-primary);
    }

    .brand-subtitle {
      font-size: 11px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
    }

    .telemetry-strip {
      display: flex;
      align-items: center;
      gap: 16px;
      background-color: var(--bg-card);
      border: 1px solid var(--border-hairline);
      padding: 6px 14px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 12px;
    }

    .telemetry-item span.label {
      color: var(--text-secondary);
      font-size: 11px;
      margin-right: 4px;
    }

    .telemetry-item span.val {
      color: var(--emerald);
      font-weight: 700;
    }

    .command-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .btn {
      cursor: pointer;
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: 5px;
      border: 1px solid var(--border-accent);
      background-color: var(--bg-card);
      color: var(--text-primary);
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .btn:hover {
      border-color: var(--cyan);
      background-color: #1E293B;
    }

    .btn-primary {
      background-color: #065F46;
      border-color: var(--emerald);
      color: #ECFDF5;
    }

    .btn-primary:hover {
      background-color: #047857;
      border-color: #34D399;
    }

    .btn-secondary {
      background-color: #1E293B;
      border-color: var(--amber);
      color: #FDE68A;
    }

    .btn-secondary:hover {
      background-color: #334155;
    }

    .btn-sm {
      padding: 4px 9px;
      font-size: 11px;
    }

    /* MAIN CONTAINER */
    .workspace {
      max-width: 1640px;
      margin: 0 auto;
      padding: 16px 20px 40px 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .card {
      background-color: var(--bg-card);
      border: 1px solid var(--border-hairline);
      border-radius: 8px;
      overflow: hidden;
    }

    .card-header {
      background-color: var(--bg-elevated);
      border-bottom: 1px solid var(--border-hairline);
      padding: 11px 16px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .card-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .card-body {
      padding: 16px;
    }

    /* BENCHMARK HEADER PANEL */
    .benchmark-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 14px;
    }

    .stat-box {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 12px 14px;
    }

    .stat-label {
      font-size: 11px;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }

    .stat-value {
      font-family: var(--font-mono);
      font-size: 20px;
      font-weight: 700;
      color: var(--emerald);
    }

    .stat-sub {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 3px;
      font-family: var(--font-mono);
    }

    .year-comparison-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }

    .year-card {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-left: 3px solid var(--emerald);
      border-radius: 6px;
      padding: 12px 14px;
    }

    .year-card-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 8px;
      font-family: var(--font-mono);
    }

    .year-title {
      font-size: 13px;
      font-weight: 700;
      color: var(--cyan);
    }

    .year-filtered {
      font-size: 18px;
      font-weight: 700;
      color: var(--emerald);
    }

    .year-bars {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--text-secondary);
      padding-top: 6px;
      border-top: 1px dashed var(--border-hairline);
    }

    .thesis-strip {
      margin-top: 12px;
      padding: 10px 14px;
      background-color: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
      font-size: 11px;
    }

    .thesis-item strong {
      display: block;
      color: var(--cyan);
      font-family: var(--font-mono);
      margin-bottom: 2px;
    }

    /* TWO-COLUMN WORKSPACE GRID */
    .main-grid {
      display: grid;
      grid-template-columns: 1.05fr 1fr;
      gap: 16px;
    }

    @media (max-width: 1200px) {
      .main-grid, .benchmark-grid, .year-comparison-grid, .thesis-strip {
        grid-template-columns: 1fr;
      }
    }

    /* TABLES */
    table {
      width: 100%;
      border-collapse: collapse;
    }

    th {
      background-color: var(--bg-elevated);
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border-hairline);
    }

    td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--border-hairline);
      vertical-align: middle;
    }

    tr:hover td {
      background-color: rgba(30, 41, 59, 0.35);
    }

    .text-right {
      text-align: right;
    }

    /* BADGES */
    .badge {
      display: inline-block;
      padding: 2px 7px;
      margin: 2px 4px 2px 0;
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 600;
      white-space: nowrap;
    }

    .badge-emerald {
      background-color: var(--emerald-bg);
      color: #34D399;
      border: 1px solid rgba(16, 185, 129, 0.35);
    }

    .badge-amber {
      background-color: var(--amber-bg);
      color: #FBBF24;
      border: 1px solid rgba(245, 158, 11, 0.35);
    }

    .badge-crimson {
      background-color: var(--crimson-bg);
      color: #FCA5A5;
      border: 1px solid rgba(239, 68, 68, 0.4);
    }

    .badge-neutral {
      background-color: #1E293B;
      color: #CBD5E1;
    }

    /* CALCULATOR INPUTS & WATERFALL */
    .preset-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }

    .calc-form-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
      margin-bottom: 14px;
      background-color: var(--bg-elevated);
      padding: 12px;
      border-radius: 6px;
      border: 1px solid var(--border-hairline);
    }

    .form-group label {
      display: block;
      font-size: 10.5px;
      font-family: var(--font-mono);
      color: var(--text-secondary);
      text-transform: uppercase;
      margin-bottom: 4px;
    }

    .form-control {
      width: 100%;
      background-color: var(--bg-canvas);
      border: 1px solid var(--border-accent);
      color: var(--text-primary);
      font-family: var(--font-mono);
      font-size: 13px;
      padding: 6px 8px;
      border-radius: 4px;
    }

    .form-control:focus {
      outline: none;
      border-color: var(--cyan);
    }

    .verdict-banner {
      padding: 12px 14px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .verdict-pass {
      background-color: var(--emerald-bg);
      border: 1px solid var(--emerald);
      color: #34D399;
    }

    .verdict-warn {
      background-color: var(--amber-bg);
      border: 1px solid var(--amber);
      color: #FBBF24;
    }

    .verdict-fail {
      background-color: var(--crimson-bg);
      border: 1px solid var(--crimson);
      color: #FCA5A5;
    }

    .waterfall-tax-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 12px;
      margin-bottom: 14px;
    }

    .sub-panel {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 12px;
    }

    .sub-panel-title {
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--cyan);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border-hairline);
    }

    .wf-row {
      display: flex;
      justify-content: space-between;
      padding: 4px 0;
      font-size: 12px;
      border-bottom: 1px dashed rgba(30, 41, 59, 0.7);
    }

    .wf-row.highlight {
      color: var(--emerald);
      font-weight: 700;
      border-top: 1px solid var(--border-accent);
      border-bottom: none;
      padding-top: 7px;
      margin-top: 3px;
      font-size: 13px;
    }

    .tax-box {
      padding: 10px;
      border-radius: 5px;
      margin-bottom: 8px;
      font-family: var(--font-mono);
    }

    .tax-ira {
      background-color: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.4);
    }

    .tax-nyc {
      background-color: rgba(245, 158, 11, 0.08);
      border: 1px solid rgba(245, 158, 11, 0.35);
    }

    /* GATEKEEPER & HFT TIMER */
    .gate-list {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-bottom: 14px;
    }

    .gate-item {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 9px 11px;
      display: flex;
      align-items: flex-start;
      gap: 9px;
      cursor: pointer;
      transition: border-color 0.15s ease;
    }

    .gate-item.checked {
      border-color: var(--emerald);
      background-color: rgba(16, 185, 129, 0.07);
    }

    .gate-item input[type="checkbox"] {
      margin-top: 3px;
      accent-color: var(--emerald);
      width: 15px;
      height: 15px;
      cursor: pointer;
    }

    .gate-code {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      color: var(--emerald);
    }

    .gate-desc {
      font-size: 11.5px;
      color: var(--text-secondary);
      margin-top: 2px;
    }

    .cooldown-bar {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 12px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    /* MODAL PREVIEW */
    .modal-backdrop {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 200;
      background-color: rgba(0, 0, 0, 0.78);
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .modal-backdrop.open {
      display: flex;
    }

    .modal-window {
      width: 100%;
      max-width: 1040px;
      max-height: 90vh;
      background-color: var(--bg-card);
      border: 1px solid var(--border-accent);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .modal-body {
      padding: 0;
      overflow-y: auto;
      flex: 1;
      background-color: #0B0F19;
    }

    .modal-iframe {
      width: 100%;
      height: 72vh;
      border: none;
      background-color: #0B0F19;
    }
  </style>
</head>
<body>

  <!-- TOP COMMAND BAR -->
  <header class="command-bar">
    <div class="brand-block">
      <span class="brand-badge">ARB CANNON v2.0</span>
      <div>
        <div class="brand-title">M&amp;A LEAK ARBITRAGE COMMAND CENTER</div>
        <div class="brand-subtitle">EXTENDED-HOURS ALL-CASH PE TAKE-PRIVATE ENGINE // SEC EDGAR XBRL + RSS WIRES</div>
      </div>
    </div>

    <div class="telemetry-strip">
      <div class="telemetry-item">
        <span class="label">DRY POWDER ($SGOV):</span>
        <span class="val" id="tel-dry-powder">$400,000</span>
      </div>
      <div class="telemetry-item">
        <span class="label">$SGOV QUOTE / YIELD:</span>
        <span class="val" id="tel-sgov-yield">$100.49 (~$18,400/yr | 4.60%)</span>
      </div>
      <div class="telemetry-item">
        <span class="label">DEFAULT CLIP:</span>
        <span class="val" id="tel-default-clip">$380,000</span>
      </div>
    </div>

    <div class="command-actions">
      <button class="btn btn-primary" id="btn-scan-wires" onclick="triggerWireScan()">
        📡 SCAN M&amp;A WIRES &amp; REFRESH EXTENDED-HOURS QUOTES
      </button>
      <button class="btn btn-secondary" id="btn-fire-email" onclick="triggerNightlyEmailModal()">
        ✉️ FIRE 5:00 PM EMAIL REPORT NOW (DRY-RUN / SMTP)
      </button>
    </div>
  </header>

  <main class="workspace">

    <!-- HEADER PANEL: STRATEGY TELEMETRY & 3-YEAR BACKTEST BENCHMARKS (2024-2026 YTD) -->
    <section class="card">
      <div class="card-header">
        <div class="card-title">
          <span>📊 STRATEGY TELEMETRY &amp; 3-YEAR HISTORICAL BACKTEST BENCHMARKS (2024–2026 YTD | 46 LEAK EVENTS)</span>
        </div>
        <div class="mono" style="font-size:11px;color:var(--text-secondary);">
          100% ALL-CASH PE SPONSOR FILTER // &lt;=10% AH DOLLAR VOLUME CAP // IRA 0%-TAX FUNGIBILITY
        </div>
      </div>
      <div class="card-body">
        <div class="benchmark-grid">
          <div class="stat-box">
            <div class="stat-label">Filtered Strategy Win Rate</div>
            <div class="stat-value">84.2%</div>
            <div class="stat-sub">93.1% on Sun/Mon/Tue Named-Buyer Leaks</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Average Net Spread Captured</div>
            <div class="stat-value">+5.8%</div>
            <div class="stat-sub">Exit into 8-K Morning Wave (48–72h Hold)</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Liquidity-Constrained Sizing</div>
            <div class="stat-value">$383,000 Avg</div>
            <div class="stat-sub">Capped &lt;= 10% AH Vol ($300k–$450k Clips)</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Realized Annual Net Extraction</div>
            <div class="stat-value">$75k–$95k+/yr</div>
            <div class="stat-sub">5–7 Qualified Trades/Yr + $SGOV Base Yield</div>
          </div>
        </div>

        <div class="year-comparison-grid">
          <div class="year-card">
            <div class="year-card-header">
              <span class="year-title">2024 BACKTEST ($500K NORM CLIP)</span>
              <span class="year-filtered">+$313,656</span>
            </div>
            <div class="year-bars">
              <span>Unfiltered (All 46 Leaks): <strong style="color:var(--amber);">+$71,590</strong></span>
              <span>Idle $SGOV: <strong style="color:var(--text-primary);">+$26,000</strong></span>
            </div>
          </div>
          <div class="year-card">
            <div class="year-card-header">
              <span class="year-title">2025 BACKTEST ($500K NORM CLIP)</span>
              <span class="year-filtered">+$332,649</span>
            </div>
            <div class="year-bars">
              <span>Unfiltered (All 46 Leaks): <strong style="color:var(--amber);">+$68,564</strong></span>
              <span>Idle $SGOV: <strong style="color:var(--text-primary);">+$22,000</strong></span>
            </div>
          </div>
          <div class="year-card">
            <div class="year-card-header">
              <span class="year-title">2026 YTD BACKTEST ($500K NORM CLIP)</span>
              <span class="year-filtered">+$191,627</span>
            </div>
            <div class="year-bars">
              <span>Unfiltered (All 46 Leaks): <strong style="color:var(--amber);">+$45,003</strong></span>
              <span>Idle $SGOV: <strong style="color:var(--text-primary);">+$15,721</strong></span>
            </div>
          </div>
        </div>

        <!-- Strategy Thesis Reference Strip -->
        <div class="thesis-strip">
          <div class="thesis-item">
            <strong>1. THE ALPHA WINDOW (3:45–5:30 PM)</strong>
            Tier-1 scoop (WSJ, Bloomberg, Reuters, FT, CNBC) breaks exclusive PE 'advanced talks' / 'nearing a deal' all-cash valuation.
          </div>
          <div class="thesis-item">
            <strong>2. WHY 5.5%–8.0% AH DISCOUNT EXISTS</strong>
            Institutional arb pods (Citadel, Millennium, Pentwater) cannot deploy full size until binding Form 8-K is filed on EDGAR.
          </div>
          <div class="thesis-item">
            <strong>3. SETTLED ENTRY (T+60m–T+180m)</strong>
            Wait 60–120m (5:30–7:00 PM EST) for HFT whipsaws to subside; stage 3 limit tranches at 5.5%, 6.5%, and 8.0% discounts.
          </div>
          <div class="thesis-item">
            <strong>4. CONVERGENCE EXIT (T+15h–T+72h)</strong>
            Exit 100% into the 6:30–9:45 AM EST Form 8-K institutional buying wave (~1.2%–2.0% residual spread); sweep back to $SGOV.
          </div>
          <div class="thesis-item">
            <strong>5. CROSS-ACCOUNT TAX FUNGIBILITY</strong>
            Execute in Tax-Sheltered IRA (0% tax vs 54.5% NYC short-term tax); withdraw matching living cash from Taxable $SGOV principal ($0 tax).
          </div>
        </div>
      </div>
    </section>

    <!-- MAIN 2-COLUMN WORKSPACE: PANEL 1 (WIRES) + PANEL 2 (60s SEC XBRL CALCULATOR) -->
    <div class="main-grid">

      <!-- PANEL 1: LIVE M&A LEAK WIRE SCANNER & EDGAR ITEM 1.01 MONITOR -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>📡 PANEL 1: LIVE M&amp;A LEAK WIRE SCANNER (&lt;= 4.0H FRESH GATE)</span>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-sm" onclick="filterWireTable('ALL')">All Separated</button>
            <button class="btn btn-sm btn-primary" onclick="filterWireTable('FRESH')">🟢 Fresh (&lt;=4h)</button>
            <button class="btn btn-sm" onclick="filterWireTable('STALE')">⏳ Stale (&gt;4h)</button>
            <button class="btn btn-sm" onclick="filterWireTable('TRAP')">🚨 Traps / Late</button>
          </div>
        </div>
        <div class="card-body" style="padding:12px;max-height:720px;overflow-y:auto;">

          <!-- SEPARATED SECTION A: FRESH ACTIONABLE LEAKS (<= 4.0 HOURS OLD) -->
          <div style="border:1px solid rgba(16,185,129,0.45);background:rgba(16,185,129,0.05);border-radius:6px;margin-bottom:14px;overflow:hidden;">
            <div style="padding:8px 12px;background:rgba(16,185,129,0.14);border-bottom:1px solid rgba(16,185,129,0.3);display:flex;justify-content:space-between;align-items:center;">
              <span class="mono" style="font-size:11.5px;font-weight:700;color:#34D399;">
                🟢 FRESH ACTIONABLE LEAK WINDOW (&lt;= 4.0 HOURS OLD)
              </span>
              <span class="badge badge-emerald" id="fresh-wire-count-badge">0 FRESH (&lt;=4H)</span>
            </div>
            <table>
              <tbody id="fresh-wire-table-body">
                <!-- Populated by JS -->
              </tbody>
            </table>
          </div>

          <!-- SEPARATED SECTION B: STALE / EXPIRED WIRE RUMORS (> 4.0 HOURS OLD) -->
          <div style="border:1px solid rgba(245,158,11,0.45);background:rgba(245,158,11,0.04);border-radius:6px;overflow:hidden;">
            <div style="padding:8px 12px;background:rgba(245,158,11,0.14);border-bottom:1px solid rgba(245,158,11,0.3);display:flex;justify-content:space-between;align-items:center;">
              <span class="mono" style="font-size:11.5px;font-weight:700;color:#FBBF24;">
                ⏳ SEPARATED STALE / EXPIRED WIRE RUMORS (&gt; 4.0 HOURS OLD — NON-ACTIONABLE)
              </span>
              <span class="badge badge-amber" id="stale-wire-count-badge">0 STALE (&gt;4H)</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Stale Headline, Age Indicator &amp; Disqualification Reasons</th>
                  <th>Day Window</th>
                  <th class="text-right">Historical Audit</th>
                </tr>
              </thead>
              <tbody id="wire-table-body">
                <!-- Populated by JS -->
              </tbody>
            </table>
          </div>

        </div>
      </section>

      <!-- PANEL 2: INTERACTIVE 60-SECOND SEC EDGAR XBRL NET-DEBT & LIMIT TRANCHE CALCULATOR -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🧮 PANEL 2: 60-SECOND SEC EDGAR XBRL NET-DEBT &amp; 3-TRANCHE LIMIT CALCULATOR</span>
          </div>
          <span class="mono" style="font-size:11px;color:var(--emerald);" id="calc-cik-badge">CIK: 0001830043</span>
        </div>
        <div class="card-body">

          <!-- 1-Click Historical Benchmark Preset Buttons + Fresh Simulation Override -->
          <div class="preset-bar" style="align-items:center;justify-content:space-between;">
            <div style="display:flex;flex-wrap:wrap;gap:6px;">
              <button class="btn btn-sm" style="border-color:var(--amber);color:#FBBF24;" onclick="loadPreset('BMBL', 'EV_BILLIONS', 1.30, 380000, 1.5)">
                [⏳ Stale Benchmark: BMBL $1.3B EV]
              </button>
              <button class="btn btn-sm" style="border-color:var(--amber);color:#FBBF24;" onclick="loadPreset('WEN', 'PER_SHARE', 8.00, 380000, 1.5)">
                [⏳ Stale Benchmark: WEN $8.00/sh]
              </button>
              <button class="btn btn-sm btn-secondary" onclick="loadPreset('U', 'EV_BILLIONS', 25.0, 380000, 1.5)">
                [⏳ Stale Benchmark: U $25B EV]
              </button>
              <button class="btn btn-sm btn-secondary" onclick="loadPreset('GPN', 'EV_BILLIONS', 24.0, 380000, 1.5, 'PE_ALL_CASH')">
                [⏳ Stale Benchmark: GPN $24B EV]
              </button>
              <button class="btn btn-sm btn-primary" style="border-color:var(--cyan);" onclick="loadPreset('RYTM', 'PER_SHARE', 124.0, 190000, 1.5, 'BIOPHARMA_BOLT_ON', 134.0)">
                [🧬 Biopharma Bolt-On: RYTM $124 Base &rarr; $134 Sweetened]
              </button>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <select id="inp-strategy-mode" class="form-control" style="font-size:11px;padding:4px 8px;width:auto;border-color:var(--cyan);" onchange="onStrategyModeChange()">
                <option value="PE_ALL_CASH">🏢 Strategy Mode: PE All-Cash LBO (5.5% / 6.5% / 8.0% Ladder | $380k Clip)</option>
                <option value="BIOPHARMA_BOLT_ON">🧬 Strategy Mode: Biopharma Bolt-On (10.0% / 12.5% / 15.0% Ladder | $190k 50% Clip)</option>
              </select>
              <label class="mono" style="font-size:11px;color:var(--cyan);display:flex;align-items:center;gap:6px;cursor:pointer;background:rgba(56,189,248,0.1);padding:4px 8px;border-radius:4px;border:1px solid rgba(56,189,248,0.35);">
                <input type="checkbox" id="chk-simulate-fresh" onchange="runCalculation()" style="accent-color:var(--emerald);" />
                ⚡ Simulate Fresh &lt;4h Leak Window
              </label>
            </div>
          </div>

          <!-- Calculator Input Controls -->
          <div class="calc-form-grid">
            <div class="form-group">
              <label for="inp-ticker">Target Ticker</label>
              <input id="inp-ticker" class="form-control" type="text" value="BMBL" />
            </div>
            <div class="form-group">
              <label for="inp-mode">Valuation Mode</label>
              <select id="inp-mode" class="form-control" onchange="runCalculation()">
                <option value="EV_BILLIONS">EV_BILLIONS ($B)</option>
                <option value="PER_SHARE">PER_SHARE ($/sh)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="inp-value">Rumored Value</label>
              <input id="inp-value" class="form-control" type="number" step="0.05" value="1.30" />
            </div>
            <div class="form-group">
              <label for="inp-clip">Clip Size ($)</label>
              <input id="inp-clip" class="form-control" type="number" step="10000" value="380000" />
            </div>
            <div class="form-group">
              <label for="inp-coc">CoC RSU Buffer (%)</label>
              <div style="display:flex;gap:6px;">
                <input id="inp-coc" class="form-control" type="number" step="0.1" value="1.5" />
                <button class="btn btn-primary btn-sm" onclick="runCalculation()">AUDIT</button>
              </div>
            </div>
          </div>

          <!-- IMMEDIATE STALE LEAK VISUAL INDICATOR BANNER (< 4.0H GATE) -->
          <div id="calc-freshness-banner" style="padding:10px 14px;border-radius:6px;margin-bottom:10px;border:2px solid var(--amber);background:rgba(245,158,11,0.15);display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;">
            <div>
              <div class="mono" style="font-size:12.5px;font-weight:700;color:#FBBF24;" id="calc-freshness-title">
                ⏳ STALE LEAK WARNING (AGE: 27.1d ago &gt; 4.0H MAX ACTIONABLE WINDOW)
              </div>
              <div style="font-size:11.5px;color:var(--text-primary);margin-top:2px;" id="calc-freshness-sub">
                You are viewing a STALE LEAK that broke more than 4 hours ago. Actionable M&amp;A leak arbitrage requires entry within 4.0 hours of the initial scoop.
              </div>
            </div>
            <span class="badge badge-amber" style="font-size:11.5px;padding:4px 9px;" id="calc-freshness-pill">
              ⏳ STALE LEAK (&gt;4H MAX)
            </span>
          </div>

          <!-- Take-Under / Spread Verdict Banner -->
          <div id="calc-verdict-banner" class="verdict-banner verdict-warn">
            <span id="calc-verdict-text">⚠️ POST-8-K / TIGHT SPREAD: +1.34% Gross Spread (Form 8-K Item 1.01 Filed 2026-10-13 — Leak Window Closed)</span>
            <span id="calc-price-summary">AH: $5.97 &rarr; Implied Deal: $6.05/sh</span>
          </div>

          <!-- Biopharma Bolt-On 6-Gate & Sweetened/CVR Callout (Visible when Biopharma Bolt-On Mode or $RYTM is active) -->
          <div id="calc-biopharma-banner" style="display:none;padding:10px 14px;border-radius:6px;margin-bottom:12px;border:1px solid var(--cyan);background:rgba(56,189,248,0.1);">
            <!-- Populated by JS -->
          </div>

          <!-- Waterfall + Tax Regime Comparison -->
          <div class="waterfall-tax-grid">
            <div class="sub-panel">
              <div class="sub-panel-title">SEC EDGAR XBRL Balance-Sheet Waterfall (GATE_6)</div>
              <div id="waterfall-rows" class="mono">
                <!-- Populated by JS -->
              </div>
            </div>

            <div class="sub-panel">
              <div class="sub-panel-title">Dual Tax-Regime P&amp;L Comparison (IRA vs NYC)</div>
              <div class="tax-box tax-ira">
                <div style="font-size:11px;color:#34D399;">IRA 0%-TAX NET PROFIT (RECOMMENDED)</div>
                <div style="font-size:20px;font-weight:700;color:var(--emerald);" id="pnl-ira-val">+$22,748</div>
                <div style="font-size:10.5px;color:#A7F3D0;margin-top:3px;" id="pnl-ira-8k-sub">
                  8-K Morning Exit (1.5% residual): +$17,114
                </div>
              </div>
              <div class="tax-box tax-nyc">
                <div style="font-size:11px;color:#FBBF24;">NYC TAXABLE (54.5% SHORT-TERM TAX) NET PROFIT</div>
                <div style="font-size:17px;font-weight:700;color:var(--amber);" id="pnl-nyc-val">+$10,350</div>
                <div style="font-size:10.5px;color:var(--text-secondary);margin-top:2px;" id="pnl-tax-drag">
                  NYC Tax Drag Avoided via IRA: $12,398
                </div>
              </div>
              <div style="font-size:11px;color:var(--text-secondary);line-height:1.35;" id="tax-instruction-text">
                💡 Withdraw matching $ from Taxable $SGOV principal at $0 capital gains tax.
              </div>
            </div>
          </div>

          <!-- 5:30 PM EST 3-Tranche Limit Order Ladder -->
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span class="mono" style="font-size:11.5px;font-weight:700;color:var(--text-primary);">
              STAGE 5:30 PM – 7:00 PM EST 3-TRANCHE LIMIT ORDER LADDER (GATE_7)
            </span>
            <button class="btn btn-sm" onclick="copyLimitOrdersToClipboard()" id="btn-copy-orders">
              📋 Copy Limit Orders to Clipboard
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Tranche &amp; Discount</th>
                <th class="text-right">Target Allocation</th>
                <th class="text-right">Limit Price</th>
                <th class="text-right">Exact Shares</th>
                <th class="text-right">Gross Profit (to Deal)</th>
              </tr>
            </thead>
            <tbody id="tranche-table-body" class="mono">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
      </section>

    </div>

    <!-- BOTTOM 2-COLUMN GRID: PANEL 3 (8-POINT GATEKEEPER & HFT TIMER) + PANEL 4 (WATCHLIST) -->
    <div class="main-grid">

      <!-- PANEL 3: INTERACTIVE 8-POINT PRE-TRADE GATEKEEPER & POST-HEADLINE HFT COOLDOWN TIMER -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🛡️ PANEL 3: 8-POINT PRE-TRADE GATEKEEPER &amp; HFT COOLDOWN TIMER</span>
          </div>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-sm" onclick="toggleAllGates(true)">Check All 8 Gates</button>
            <button class="btn btn-sm" onclick="toggleAllGates(false)">Reset</button>
          </div>
        </div>
        <div class="card-body">

          <!-- HFT Cooldown Timer -->
          <div class="cooldown-bar">
            <div style="display:flex;align-items:center;gap:10px;">
              <span class="mono" style="font-weight:700;color:var(--cyan);">⏱️ HFT COOLDOWN TIMER:</span>
              <label class="mono" style="font-size:11px;color:var(--text-secondary);">Headline Break (EST):</label>
              <input id="inp-headline-time" type="time" value="16:18" class="form-control" style="width:110px;" onchange="updateCooldownTimer()" />
            </div>
            <div class="mono" style="font-size:12px;" id="cooldown-milestones">
              T+60m Settled Open: <strong style="color:var(--emerald);">17:18 EST</strong> |
              T+180m Window Close: <strong style="color:var(--amber);">19:18 EST</strong>
            </div>
          </div>

          <!-- Gatekeeper Cleared Hot Status Banner -->
          <div id="gatekeeper-status-banner" class="verdict-banner verdict-warn">
            <span id="gatekeeper-banner-text">⚠️ PRE-TRADE GATEKEEPER LOCKED — CHECK ALL 8 GATES TO STAGE ORDERS</span>
            <span id="gatekeeper-counter" class="mono">0 / 8 GATES CLEARED</span>
          </div>

          <!-- 8 Gate Checkboxes -->
          <div class="gate-list" id="gatekeeper-grid">
            <!-- Populated by JS -->
          </div>
        </div>
      </section>

      <!-- PANEL 4: RUMOR RADAR WATCHLIST (SEPARATED FRESH <=4H vs STALE >4H BENCHMARKS) -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🎯 PANEL 4: RUMOR RADAR WATCHLIST (FRESH &lt;=4H vs. SEPARATED STALE &gt;4H BENCHMARKS)</span>
          </div>
          <span class="mono" style="font-size:11px;color:var(--amber);">⏳ &lt;= 4.0H FRESHNESS GATE ENFORCED</span>
        </div>
        <div class="card-body">

          <!-- SEPARATED GROUP A: ACTIVE FRESH WATCHLIST LEAKS (<= 4.0 HOURS OLD) -->
          <div style="border:1px solid rgba(16,185,129,0.45);background:rgba(16,185,129,0.05);border-radius:6px;margin-bottom:14px;overflow-x:auto;">
            <div style="padding:7px 12px;background:rgba(16,185,129,0.14);border-bottom:1px solid rgba(16,185,129,0.3);display:flex;justify-content:space-between;align-items:center;">
              <span class="mono" style="font-size:11px;font-weight:700;color:#34D399;">
                🟢 ACTIVE FRESH LEAK RADAR (&lt;= 4.0 HOURS OLD — ACTIONABLE CANDIDATES)
              </span>
              <span class="badge badge-emerald" id="fresh-wl-count-badge">0 FRESH TARGETS</span>
            </div>
            <table>
              <tbody id="fresh-watchlist-table-body" class="mono">
                <!-- Populated by JS -->
              </tbody>
            </table>
          </div>

          <!-- SEPARATED GROUP B: STALE RUMORS & HISTORICAL BENCHMARKS (> 4.0 HOURS OLD) -->
          <div style="border:1px solid rgba(245,158,11,0.45);background:rgba(245,158,11,0.04);border-radius:6px;margin-bottom:14px;overflow-x:auto;">
            <div style="padding:7px 12px;background:rgba(245,158,11,0.14);border-bottom:1px solid rgba(245,158,11,0.3);display:flex;justify-content:space-between;align-items:center;">
              <span class="mono" style="font-size:11px;font-weight:700;color:#FBBF24;">
                ⏳ SEPARATED STALE RUMORS &amp; HISTORICAL BENCHMARKS (&gt; 4.0 HOURS OLD — TOO STALE TO BE ACTIONABLE)
              </span>
              <span class="badge badge-amber" id="stale-wl-count-badge">4 STALE BENCHMARKS</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Ticker &amp; Buyer</th>
                  <th>Leak Age (&lt;4h Gate)</th>
                  <th class="text-right">Reg / AH Price</th>
                  <th class="text-right">Implied Deal</th>
                  <th class="text-right">Gross Spread</th>
                  <th>EDGAR 8-K Status</th>
                  <th class="text-right">Actions</th>
                </tr>
              </thead>
              <tbody id="watchlist-table-body" class="mono">
                <!-- Populated by JS -->
              </tbody>
            </table>
          </div>

          <!-- Add Ticker Form -->
          <div style="background-color:var(--bg-elevated);border:1px solid var(--border-hairline);border-radius:6px;padding:10px 12px;">
            <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;text-transform:uppercase;">
              + Add Breaking PE Leak Target to Active Fresh Radar (&lt;=4h)
            </div>
            <div style="display:grid;grid-template-columns:0.8fr 1.1fr 0.8fr 1.8fr auto;gap:8px;align-items:center;">
              <input id="wl-ticker" class="form-control" placeholder="Ticker (e.g. RYTM)" />
              <select id="wl-mode" class="form-control">
                <option value="EV_BILLIONS">EV_BILLIONS ($B)</option>
                <option value="PER_SHARE">PER_SHARE ($/sh)</option>
              </select>
              <input id="wl-val" class="form-control" type="number" step="0.1" placeholder="Value (e.g. 124.0)" value="10.0" />
              <input id="wl-headline" class="form-control" placeholder="Factual Watchlist Note / Headline" />
              <button class="btn btn-primary btn-sm" onclick="addWatchlistTicker()">+ Add Target</button>
            </div>
          </div>
        </div>
      </section>

    </div>

    <!-- PANEL 5: BIOPHARMA TWO-REGIME PRE-ANNOUNCEMENT ENGINE & FULL 30-EVENT UN-BIASED BACKTEST (2022–2026) -->
    <section class="card" style="border-color:rgba(56,189,248,0.45);">
      <div class="card-header" style="background:linear-gradient(90deg, rgba(15,23,42,0.98) 0%, rgba(6,78,59,0.35) 100%);">
        <div class="card-title">
          <span style="color:var(--cyan);">🧬 PANEL 5: BIOPHARMA TWO-REGIME PRE-ANNOUNCEMENT ENGINE &amp; FULL 30-EVENT UN-BIASED BACKTEST (2022–2026)</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <span class="badge badge-emerald" id="bio-bt-winrate-badge">NAMED-BID CONVERSION: 75.0% (12W / 4L | N=16)</span>
          <span class="badge badge-amber" id="bio-bt-spread-badge">BROAD COMMERCIAL: 60.0% (12W / 8L | N=20) | UNFILTERED: 46.7% (N=30)</span>
          <span class="badge badge-neutral" style="border:1px solid var(--cyan);color:var(--cyan);">LIVE $100K @ $113.00 (885 SH) &le; $114.08 HARD 92% CAP</span>
          <button class="btn btn-sm btn-primary" onclick="loadPreset('RYTM', 'PER_SHARE', 124.0, 190000, 1.5, 'BIOPHARMA_BOLT_ON', 134.0)">
            ⚡ Stage $RYTM ($100k @ $113.00 Held | Hard Ceiling $114.08) &uarr;
          </button>
        </div>
      </div>
      <div class="card-body">

        <!-- Biopharma Strategy Telemetry vs. Unfiltered Control Comparison -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;">
          <div class="sub-panel" style="border-color:rgba(16,185,129,0.45);background:rgba(16,185,129,0.06);">
            <div class="sub-panel-title" style="color:#34D399;">Named-Bid Conversion Rate (N=16 Setups)</div>
            <div class="mono" style="font-size:20px;font-weight:700;color:var(--emerald);" id="bio-kpi-filtered-wr">75.0% (12W / 4L)</div>
            <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
              Broad Commercial (N=20): <strong style="color:var(--amber);">60.0%</strong> | All 30 Rumors: <strong style="color:var(--crimson);" id="bio-kpi-unfiltered-wr">46.7% (-4.46% Med)</strong>
            </div>
          </div>
          <div class="sub-panel" style="border-color:rgba(56,189,248,0.45);background:rgba(56,189,248,0.05);">
            <div class="sub-panel-title" style="color:var(--cyan);">Live $100k @ $113.00 (~885 sh) $RYTM Lot</div>
            <div class="mono" style="font-size:18px;font-weight:700;color:var(--emerald);" id="bio-kpi-avg-spread">+$9,735 @ $124 | +$18,585 @ $134</div>
            <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
              Walk-Away $92 Floor (25%): <strong style="color:var(--crimson);">-$18,585 (-0.46% NW)</strong> | EV: <strong style="color:var(--emerald);">+$6,195</strong>
            </div>
          </div>
          <div class="sub-panel">
            <div class="sub-panel-title">Expected 8-K Formalization Clock (Day 4 = Nov 10)</div>
            <div class="mono" style="font-size:17px;font-weight:700;color:var(--emerald);" id="bio-kpi-cum-pnl">Mon Nov 16 or Mon Nov 23 (55%)</div>
            <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
              2-Bid Auction (25%): <strong style="color:var(--cyan);">Nov 30–Dec 14</strong> | Time-Stop: <strong style="color:var(--amber);">Dec 7 / Dec 14</strong>
            </div>
          </div>
          <div class="sub-panel" style="border-color:rgba(16,185,129,0.4);background:rgba(16,185,129,0.04);">
            <div class="sub-panel-title" style="color:#34D399;">Walk-Away Floor ($89–$95) &amp; $RVMD Precedent</div>
            <div class="mono" style="font-size:18px;font-weight:700;color:var(--emerald);">$92.00 Floor (-18.6% vs -23.5%)</div>
            <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
              Nov 2–3 Q3 +79.6% YoY + $750M facility; $RVMD -19.7% &rarr; +68.9% ($198.50)
            </div>
          </div>
        </div>

        <!-- LIVE $100,000 @ $113.00 (~885 SHARES) $RYTM 3-SCENARIO PAYOFF & FORMALIZATION CALENDAR STRIP -->
        <div id="bio-rytm-100k-strip" class="sub-panel" style="border-color:rgba(56,189,248,0.5);background:linear-gradient(90deg, rgba(15,23,42,0.95) 0%, rgba(6,78,59,0.22) 100%);margin-bottom:14px;">
          <!-- Populated by JS -->
        </div>

        <!-- Regime B Pre-Rumor "Walk-Away Leverage" Radar ($RYTM, $SRRK, $COGT) & Purged Weekend Gaps -->
        <div style="display:grid;grid-template-columns:1.35fr 0.65fr;gap:12px;margin-bottom:14px;">
          <div class="sub-panel" style="border-color:rgba(16,185,129,0.4);background:rgba(16,185,129,0.04);">
            <div class="sub-panel-title" style="color:#34D399;">
              ⚡ REGIME B PRE-RUMOR "WALK-AWAY LEVERAGE" RADAR (RA CAPITAL SEMPER MAIOR 2026 PLAYBOOK — CATCHING WEEKEND GAPS BEFORE THE LEAK)
            </div>
            <div id="bio-regime-b-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
              <!-- Populated by JS -->
            </div>
          </div>
          <div class="sub-panel" style="border-color:rgba(239,68,68,0.4);background:rgba(239,68,68,0.04);">
            <div class="sub-panel-title" style="color:#FCA5A5;">
              🚫 4 PURGED UNTRADABLE WEEKEND / OVERNIGHT GAPS (EXCLUDED FROM REGIME A)
            </div>
            <div id="bio-purged-gaps-list" class="mono" style="font-size:10.5px;color:var(--text-secondary);line-height:1.45;">
              <!-- Populated by JS -->
            </div>
          </div>
        </div>

        <!-- Live $RYTM & Historical Case Study Interactive 6-Gate Inspector -->
        <div style="display:grid;grid-template-columns:1.15fr 1fr;gap:14px;margin-bottom:14px;">
          <div class="sub-panel" style="border-color:rgba(56,189,248,0.4);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:8px;">
              <div class="sub-panel-title" style="margin:0;color:var(--cyan);">
                🔬 LIVE BIOPHARMA 6-GATE AUDITOR (DEFAULT: $RYTM $100K @ $113.00 | HARD CEILING $114.08 = 92% OF $124)
              </div>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">
                <button class="btn btn-sm btn-primary" onclick="loadBiopharmaCaseStudy('RYTM')">🧬 Live: $RYTM ($100k @ $113)</button>
                <button class="btn btn-sm" onclick="loadBiopharmaCaseStudy('GBT')">✅ $GBT (+8.7% in 3d)</button>
                <button class="btn btn-sm" onclick="loadBiopharmaCaseStudy('RNA')">✅ $RNA (+22.6%)</button>
                <button class="btn btn-sm" onclick="loadBiopharmaCaseStudy('CDTX')">✅ $CDTX (+19.6%)</button>
                <button class="btn btn-sm" style="border-color:var(--amber);color:#FBBF24;" onclick="loadBiopharmaCaseStudy('RVMD')">⚠️ Walk-Away: $RVMD (-19.7% &rarr; +68.9%)</button>
                <button class="btn btn-sm" style="border-color:var(--crimson);color:#FCA5A5;" onclick="loadBiopharmaCaseStudy('BMRN')">🚨 No-Bid Drift: $BMRN (-20.0%)</button>
                <button class="btn btn-sm" style="border-color:var(--crimson);color:#FCA5A5;" onclick="loadBiopharmaCaseStudy('VKTX')">🚨 Bleed: $VKTX (-45.0%)</button>
              </div>
            </div>
            <div id="bio-live-audit-card">
              <!-- Populated by JS -->
            </div>
          </div>

          <div class="sub-panel">
            <div class="sub-panel-title" style="color:var(--emerald);">
              📐 $190K IRA 3-TRANCHE LIMIT LADDER ($112.73 / $110.22 / $107.83 | 7–20 TRADING DAY CLOCK)
            </div>
            <div id="bio-live-tranche-card">
              <!-- Populated by JS -->
            </div>
          </div>
        </div>

        <!-- 30-Event Verified Tradable Regular-Session Biopharma Cohort Table (2022–2026) -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
          <span class="mono" style="font-size:11.5px;font-weight:700;color:var(--text-primary);">
            📚 FULL 30-EVENT UN-BIASED TRADABLE BIOTECH M&amp;A COHORT (2022–2026 — 16 QUALIFIED NAMED-BID [75.0%: 12W / 4L] vs. 14 DISQUALIFIED)
          </span>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-sm" onclick="filterBiopharmaTable('ALL')">All 30 Tradable Rumors (46.7% WR: 14W / 16L | -4.46% Med)</button>
            <button class="btn btn-sm btn-primary" onclick="filterBiopharmaTable('QUALIFIED')">✅ 16 Qualified Named-Bid Setups (75.0% WR: 12W / 4L | +17.7% Winner Med)</button>
            <button class="btn btn-sm" onclick="filterBiopharmaTable('FILTERED')">❌ 14 Disqualified (No-Bid Commercial Drifts [$BMRN/$ALNY/$FOLD/$ACAD] / &gt;92% Chase / Clinical)</button>
          </div>
        </div>
        <div style="overflow-x:auto;border:1px solid var(--border-hairline);border-radius:6px;">
          <table>
            <thead>
              <tr>
                <th>Leak Date, Target &amp; Hold Clock</th>
                <th>Reported Suitor &amp; Walk-Away Leverage Anchor</th>
                <th class="text-right">Unaffected &rarr; Entry (% of Anchor)</th>
                <th class="text-right">8-K / Deal-Window Exit</th>
                <th class="text-right">Realized Spread</th>
                <th class="text-right">IRA P&amp;L ($190k Clip)</th>
                <th>Gate 1–6 Audit Status &amp; Disqualification Reason</th>
              </tr>
            </thead>
            <tbody id="bio-backtest-tbody" class="mono">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>

      </div>
    </section>

  </main>

  <!-- MODAL FOR 5:00 PM EMAIL REPORT PREVIEW -->
  <div class="modal-backdrop" id="email-modal">
    <div class="modal-window">
      <div class="card-header">
        <div>
          <div class="card-title" id="modal-email-subject">✉️ 5:00 PM EST NIGHTLY REPORT PREVIEW</div>
          <div class="mono" style="font-size:11px;color:var(--emerald);margin-top:2px;" id="modal-email-meta">
            Saved to latest_5pm_report.html
          </div>
        </div>
        <button class="btn btn-sm" onclick="closeEmailModal()">✕ Close Preview</button>
      </div>
      <div class="modal-body">
        <iframe id="email-preview-iframe" class="modal-iframe" title="5PM Email Report Preview"></iframe>
      </div>
    </div>
  </div>

  <script>
    let STATE = {
      wireItems: [],
      wireFilter: 'ALL',
      watchlist: [],
      gatekeeperRules: [],
      checkedGates: new Set(),
      currentCalculation: null,
      biopharmaBacktest: null,
      biopharmaFilter: 'ALL',
      sweetenedCeilingOverride: null,
    };

    function fmtUSD(val, decimals = 0) {
      if (val === null || val === undefined || isNaN(val)) return '$0';
      const sign = val < 0 ? '-' : '';
      return sign + '$' + Math.abs(Number(val)).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      });
    }

    async function initDashboard() {
      const res = await fetch('/api/dashboard');
      const data = await res.json();
      STATE.wireItems = data.wire_items || [];
      STATE.watchlist = data.watchlist || [];
      STATE.gatekeeperRules = data.gatekeeper_rules || [];
      STATE.currentCalculation = data.default_calculation;
      STATE.biopharmaBacktest = data.biopharma_backtest || null;

      renderTelemetry(data.telemetry);
      renderWireTable();
      renderGatekeeperGrid();
      renderWatchlistTable();
      renderCalculation(data.default_calculation);
      renderBiopharmaBacktestPanel();
      updateCooldownTimer();

      // Support deep-linking from /scan page (?ticker=U&mode=EV_BILLIONS&value=25&sim_fresh=1)
      const params = new URLSearchParams(window.location.search);
      if (params.get('ticker')) {
        const tkr = params.get('ticker').toUpperCase();
        const mode = params.get('mode') || (tkr === 'RYTM' ? 'PER_SHARE' : 'EV_BILLIONS');
        const val = parseFloat(params.get('value')) || (tkr === 'RYTM' ? 124.0 : 1.3);
        const clip = parseFloat(params.get('clip')) || (tkr === 'RYTM' ? 190000 : 380000);
        const strat = tkr === 'RYTM' ? 'BIOPHARMA_BOLT_ON' : 'PE_ALL_CASH';
        if (params.get('sim_fresh') === '1') {
          const chk = document.getElementById('chk-simulate-fresh');
          if (chk) chk.checked = true;
        }
        await loadPreset(tkr, mode, val, clip, 1.5, strat, tkr === 'RYTM' ? 134.0 : null);
      }
    }

    function renderTelemetry(tel) {
      if (!tel) return;
      document.getElementById('tel-dry-powder').textContent = fmtUSD(tel.dry_powder_usd);
      document.getElementById('tel-sgov-yield').textContent =
        `$${Number(tel.sgov_price).toFixed(2)} (~${fmtUSD(tel.sgov_annual_yield_usd)}/yr | ${Number(tel.sgov_annual_yield_pct).toFixed(2)}%)`;
      document.getElementById('tel-default-clip').textContent = fmtUSD(tel.default_clip_usd);
    }

    function filterWireTable(mode) {
      STATE.wireFilter = mode;
      renderWireTable();
    }

    function renderSingleWireRow(item) {
      const tagList = item.factual_keyword_tags && item.factual_keyword_tags.length
        ? [item.freshness_badge, ...item.factual_keyword_tags]
        : (item.tags || []);
      const badges = tagList.filter(Boolean).map(tag => {
        let cls = 'badge-neutral';
        if (tag.includes('FRESH LEAK') || tag.includes('TIER-1')) cls = 'badge-emerald';
        else if (tag.includes('STALE LEAK') || tag.includes('11TH-HOUR')) cls = 'badge-amber';
        else if (tag.includes('TRAP') || tag.includes('ALREADY') || tag.includes('8-K')) cls = 'badge-crimson';
        return `<span class="badge ${cls}">${tag}</span>`;
      }).join('');

      const rowBorder = item.is_stale_leak
        ? 'border-left:3px solid var(--amber);background:rgba(245,158,11,0.03);'
        : 'border-left:3px solid var(--emerald);';

      const tkrPrefix = item.detected_ticker
        ? `<span class="mono" style="color:var(--cyan);">[$${item.detected_ticker}]</span> `
        : '';

      const hasExplicitValuation = item.detected_ticker && item.suggested_input_mode && item.suggested_value !== null && item.suggested_value !== undefined;
      const actionCell = hasExplicitValuation
        ? `<button class="btn btn-sm ${item.is_stale_leak ? '' : 'btn-primary'}"
             onclick="loadPreset('${item.detected_ticker}', '${item.suggested_input_mode}', ${item.suggested_value}, ${Math.round(380000 * item.recommended_clip_multiplier)}, 1.5)">
             Load Explicit ${item.suggested_input_mode === 'PER_SHARE' ? '$' + item.suggested_value + '/sh' : '$' + item.suggested_value + 'B EV'}
           </button>`
        : `<a href="${item.link}" target="_blank" rel="noopener" class="btn btn-sm">Open Source Link &nearr;</a>`;

      return `
        <tr style="${rowBorder}">
          <td>
            <div style="font-weight:600;color:var(--text-primary);margin-bottom:4px;">
              ${tkrPrefix}<a href="${item.link}" target="_blank" rel="noopener" style="color:var(--text-primary);text-decoration:underline;">${item.title}</a>
            </div>
            <div style="margin-bottom:4px;">${badges}</div>
            <div class="mono" style="font-size:11px;color:var(--text-muted);">
              Source: <strong>${item.source}</strong> &bull; Published: ${item.published_at} &bull;
              <strong style="color:${item.is_stale_leak ? '#FBBF24' : '#34D399'};">Age: ${item.leak_age_human || 'N/A'}</strong>
            </div>
          </td>
          <td class="mono" style="font-size:11px;">
            ${item.day_of_week}
          </td>
          <td class="text-right">
            ${actionCell}
          </td>
        </tr>
      `;
    }

    function renderWireTable() {
      const freshTbody = document.getElementById('fresh-wire-table-body');
      const staleTbody = document.getElementById('wire-table-body');
      let items = STATE.wireItems || [];
      if (STATE.wireFilter === 'FRESH') {
        items = items.filter(i => !i.is_stale_leak);
      } else if (STATE.wireFilter === 'STALE') {
        items = items.filter(i => i.is_stale_leak);
      } else if (STATE.wireFilter === 'TRAP') {
        items = items.filter(i => i.is_stock_or_antitrust_trap || i.is_already_announced);
      }

      const freshItems = items.filter(i => !i.is_stale_leak);
      const staleItems = items.filter(i => i.is_stale_leak);

      document.getElementById('fresh-wire-count-badge').textContent = `${freshItems.length} FRESH (<=4H)`;
      document.getElementById('stale-wire-count-badge').textContent = `${staleItems.length} STALE (>4H)`;

      if (freshItems.length === 0) {
        freshTbody.innerHTML = `
          <tr>
            <td colspan="3" class="mono" style="padding:12px;color:var(--text-secondary);font-size:11.5px;">
              🔎 <strong>0 Fresh M&amp;A Leaks (&lt;= 4.0 hours old)</strong> on the wire right now. All older headlines (&gt; 4.0h old) are separated into the <strong>⏳ Stale / Expired Wire Rumors</strong> table below.
            </td>
          </tr>
        `;
      } else {
        freshTbody.innerHTML = freshItems.map(renderSingleWireRow).join('');
      }

      if (staleItems.length === 0) {
        staleTbody.innerHTML = `
          <tr>
            <td colspan="3" class="mono" style="padding:12px;color:var(--text-secondary);font-size:11.5px;">
              No stale (&gt;4h) wire items under current filter.
            </td>
          </tr>
        `;
      } else {
        staleTbody.innerHTML = staleItems.map(renderSingleWireRow).join('');
      }
    }

    async function loadPreset(ticker, mode, value, clipUsd = 380000, cocPct = 1.5, strategyMode = null, sweetenedCeiling = null) {
      document.getElementById('inp-ticker').value = ticker;
      document.getElementById('inp-mode').value = mode;
      document.getElementById('inp-value').value = value;
      document.getElementById('inp-clip').value = clipUsd;
      document.getElementById('inp-coc').value = cocPct;
      const stratSel = document.getElementById('inp-strategy-mode');
      if (stratSel) {
        stratSel.value = strategyMode || (ticker.toUpperCase() === 'RYTM' ? 'BIOPHARMA_BOLT_ON' : 'PE_ALL_CASH');
      }
      STATE.sweetenedCeilingOverride = sweetenedCeiling;
      await runCalculation();
    }

    async function onStrategyModeChange() {
      const stratSel = document.getElementById('inp-strategy-mode');
      const modeVal = stratSel ? stratSel.value : 'PE_ALL_CASH';
      const clipInput = document.getElementById('inp-clip');
      if (modeVal === 'BIOPHARMA_BOLT_ON' && parseFloat(clipInput.value) === 380000) {
        clipInput.value = 190000;
      } else if (modeVal === 'PE_ALL_CASH' && parseFloat(clipInput.value) === 190000) {
        clipInput.value = 380000;
      }
      await runCalculation();
    }

    async function runCalculation() {
      const simFresh = Boolean(document.getElementById('chk-simulate-fresh')?.checked);
      const stratMode = document.getElementById('inp-strategy-mode')?.value || 'PE_ALL_CASH';
      const tkrVal = document.getElementById('inp-ticker').value.trim().toUpperCase();
      const payload = {
        ticker: tkrVal,
        input_mode: document.getElementById('inp-mode').value,
        value: parseFloat(document.getElementById('inp-value').value) || 0,
        clip_usd: parseFloat(document.getElementById('inp-clip').value) || 380000,
        coc_dilution_pct: parseFloat(document.getElementById('inp-coc').value) || 1.5,
        simulate_fresh_leak: simFresh,
        strategy_mode: stratMode,
        sweetened_ceiling_per_share: tkrVal === 'RYTM' ? (STATE.sweetenedCeilingOverride || 134.0) : STATE.sweetenedCeilingOverride,
      };
      const res = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const calc = await res.json();
      STATE.currentCalculation = calc;
      renderCalculation(calc);
      updateGatekeeperBanner();
    }

    function renderCalculation(calc) {
      if (!calc || !calc.balance_sheet_waterfall) return;
      const wf = calc.balance_sheet_waterfall;
      const ms = calc.market_and_spread;
      const tax = calc.tax_regime_pnl;
      const lf = calc.leak_freshness || {};

      document.getElementById('calc-cik-badge').textContent =
        `${calc.ticker} // CIK: ${calc.cik} (${wf.filing_source})`;

      // Freshness / Stale Visual Indicator Banner (< 4.0h Gate)
      const fBanner = document.getElementById('calc-freshness-banner');
      const fTitle = document.getElementById('calc-freshness-title');
      const fSub = document.getElementById('calc-freshness-sub');
      const fPill = document.getElementById('calc-freshness-pill');

      if (ms.is_stale_leak) {
        fBanner.style.borderColor = 'var(--amber)';
        fBanner.style.backgroundColor = 'rgba(245, 158, 11, 0.16)';
        fTitle.style.color = '#FBBF24';
        fTitle.textContent = `⏳ STALE LEAK DETECTED — AGE: ${ms.leak_age_human} (> 4.0H MAX ACTIONABLE WINDOW)`;
        fSub.textContent = `${lf.freshness_banner || 'This rumor broke > 4 hours ago and is too stale to be actionable.'} (Check "⚡ Simulate Fresh <4h Leak Window" above to test fresh order staging.)`;
        fPill.className = 'badge badge-amber';
        fPill.textContent = ms.freshness_badge || '⏳ STALE LEAK (>4H MAX)';
      } else {
        fBanner.style.borderColor = 'var(--emerald)';
        fBanner.style.backgroundColor = 'rgba(16, 185, 129, 0.14)';
        fTitle.style.color = '#34D399';
        fTitle.textContent = `🟢 FRESH LEAK WINDOW — AGE: ${ms.leak_age_human} (<= 4.0H ACTIONABLE GATE CLEARED)`;
        fSub.textContent = lf.freshness_banner || 'Inside the mandatory <= 4.0-hour post-headline actionable window.';
        fPill.className = 'badge badge-emerald';
        fPill.textContent = ms.freshness_badge || '🟢 FRESH LEAK (<=4H)';
      }

      // Verdict Banner
      const banner = document.getElementById('calc-verdict-banner');
      banner.className = 'verdict-banner ' + (
        ms.verdict === 'PASS_HOT' ? 'verdict-pass' :
        ms.verdict === 'FAIL_TAKE_UNDER' ? 'verdict-fail' : 'verdict-warn'
      );
      document.getElementById('calc-verdict-text').textContent = ms.verdict_label;
      document.getElementById('calc-price-summary').textContent =
        `Reg: $${ms.regular_market_price.toFixed(2)} | AH: $${ms.extended_hours_price.toFixed(2)} → Implied Cash Buyout: $${ms.implied_cash_buyout_per_share.toFixed(2)}/sh (Net: ${ms.net_spread_pct >= 0 ? '+' : ''}${ms.net_spread_pct.toFixed(2)}%)`;

      // Biopharma Bolt-On Banner (when Biopharma Bolt-On mode or $RYTM is active)
      const bioBanner = document.getElementById('calc-biopharma-banner');
      if (bioBanner) {
        const bio = calc.biopharma_bolt_on_audit;
        if (bio && (calc.strategy_mode === 'BIOPHARMA_BOLT_ON' || calc.ticker === 'RYTM')) {
          bioBanner.style.display = 'block';
          const ceilColor = bio.passes_anchor_92pct_gate ? 'var(--emerald)' : 'var(--crimson)';
          bioBanner.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px;">
              <span class="mono" style="font-size:12px;font-weight:700;color:var(--cyan);">
                🧬 BIOPHARMA REGIME A CONTESTED AUCTION MODE (${bio.passed_gates_count}/${bio.total_gates_count} GATES | 10–45 DAY CLOCK) — ${bio.named_pharma_suitor}
              </span>
              <span class="badge ${bio.all_biopharma_gates_passed ? 'badge-emerald' : 'badge-amber'}">
                ${bio.verdict} | Open $${bio.current_price.toFixed(2)} = ${bio.entry_pct_of_anchor_display}% of $${bio.base_cash_bid_per_share.toFixed(2)} Floor (Hard 92% Ceiling: $${bio.hard_ceiling_92pct.toFixed(2)})
              </span>
            </div>
            <div class="mono" style="font-size:11px;color:var(--text-primary);display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <span>Walk-Away Leverage: <strong style="color:var(--emerald);">${bio.commercial_drug_name}</strong></span>
              <span>Hard Gate 5 (&le;92%): <strong style="color:${ceilColor};">$${bio.hard_ceiling_92pct.toFixed(2)} Max</strong> | IRA @ Base ($${bio.base_cash_bid_per_share}): <strong style="color:var(--emerald);">+${fmtUSD(bio.pnl_summary.ira_base_bid_net_profit_usd)}</strong> | @ Sweetened ($${bio.sweetened_ceiling_per_share}): <strong style="color:var(--cyan);">+${fmtUSD(bio.pnl_summary.ira_sweetened_bid_net_profit_usd)}</strong></span>
            </div>
          `;
        } else {
          bioBanner.style.display = 'none';
        }
      }

      // Balance-Sheet Waterfall
      const wfContainer = document.getElementById('waterfall-rows');
      wfContainer.innerHTML = `
        <div class="wf-row"><span>Rumored Enterprise Value:</span><span>${fmtUSD(wf.rumored_enterprise_value_usd)}</span></div>
        <div class="wf-row"><span>(+) Total Debt &amp; Preferred:</span><span style="color:var(--crimson);">${fmtUSD(wf.total_debt_and_preferred_usd)}</span></div>
        <div class="wf-row"><span>(-) Total Cash &amp; ST Inv:</span><span style="color:var(--emerald);">${fmtUSD(wf.total_cash_usd)}</span></div>
        <div class="wf-row"><span>(=) Net Debt Subtracted:</span><span style="color:var(--amber);">${fmtUSD(wf.net_debt_usd)}</span></div>
        <div class="wf-row"><span>(=) Implied Equity Value:</span><span>${fmtUSD(wf.implied_equity_value_usd)}</span></div>
        <div class="wf-row"><span>Base Diluted Shares:</span><span>${(wf.base_diluted_shares / 1e6).toFixed(2)}M sh</span></div>
        <div class="wf-row"><span>CoC Adjusted Shares (+${wf.coc_dilution_pct}%):</span><span>${(wf.adjusted_diluted_shares / 1e6).toFixed(2)}M sh</span></div>
        <div class="wf-row highlight">
          <span>IMPLIED CASH BUYOUT / SH:</span>
          <span>$${ms.implied_cash_buyout_per_share.toFixed(2)} / sh</span>
        </div>
      `;

      // Tax Regime P&L
      document.getElementById('pnl-ira-val').textContent = `+${fmtUSD(tax.ira_tax_free_net_profit_usd)}`;
      document.getElementById('pnl-ira-8k-sub').textContent =
        `8-K Morning Exit (1.5% residual spread): +${fmtUSD(tax.ira_8k_convergence_net_profit_usd)}`;
      document.getElementById('pnl-nyc-val').textContent = `+${fmtUSD(tax.nyc_taxable_net_profit_usd)}`;
      document.getElementById('pnl-tax-drag').textContent =
        `NYC 54.5% Tax Drag Saved in IRA: ${fmtUSD(tax.nyc_tax_drag_usd)}`;
      document.getElementById('tax-instruction-text').textContent =
        `💡 ${tax.tax_fungibility_instruction}`;

      // 3-Tranche Limit Order Table
      const tbody = document.getElementById('tranche-table-body');
      tbody.innerHTML = (calc.tranche_ladder || []).map(t => `
        <tr>
          <td>
            <strong style="color:var(--cyan);">Tranche ${t.tranche_number}</strong>
            <span style="color:var(--text-secondary);">(${t.weight_pct}% Clip | -${t.discount_pct.toFixed(1)}% Gross Disc)</span>
          </td>
          <td class="text-right">${fmtUSD(t.allocation_usd)}</td>
          <td class="text-right" style="color:var(--emerald);font-weight:700;">$${t.limit_price.toFixed(2)}</td>
          <td class="text-right" style="font-weight:700;">${t.shares.toLocaleString()} sh</td>
          <td class="text-right" style="color:var(--emerald);">+${fmtUSD(t.expected_gross_profit_usd)}</td>
        </tr>
      `).join('');
    }

    function copyLimitOrdersToClipboard() {
      const calc = STATE.currentCalculation;
      if (!calc || !calc.tranche_ladder) return;
      const lines = calc.tranche_ladder.map(t =>
        `BUY ${t.shares} ${calc.ticker} LMT $${t.limit_price.toFixed(2)} EXT (Tranche ${t.tranche_number} | ${t.discount_pct}% Disc | Alloc ${fmtUSD(t.allocation_usd)})`
      );
      const text = `// ARB CANNON 5:30 PM EST EXTENDED-HOURS LIMIT LADDER (${calc.ticker})\n` + lines.join('\n');
      navigator.clipboard.writeText(text);
      const btn = document.getElementById('btn-copy-orders');
      btn.textContent = '✅ Copied 3-Tranche Limit Orders!';
      setTimeout(() => { btn.textContent = '📋 Copy Limit Orders to Clipboard'; }, 2000);
    }

    function renderGatekeeperGrid() {
      const container = document.getElementById('gatekeeper-grid');
      container.innerHTML = (STATE.gatekeeperRules || []).map(g => {
        const isChecked = STATE.checkedGates.has(g.id);
        return `
          <label class="gate-item ${isChecked ? 'checked' : ''}" id="label-${g.id}">
            <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="onGateToggle('${g.id}', this.checked)" />
            <div>
              <div class="gate-code">${g.number}. ${g.name} — ${g.title}</div>
              <div class="gate-desc">${g.description}</div>
            </div>
          </label>
        `;
      }).join('');
      updateGatekeeperBanner();
    }

    function onGateToggle(gateId, checked) {
      if (checked) STATE.checkedGates.add(gateId);
      else STATE.checkedGates.delete(gateId);
      const lbl = document.getElementById(`label-${gateId}`);
      if (lbl) lbl.classList.toggle('checked', checked);
      updateGatekeeperBanner();
    }

    function toggleAllGates(checkAll) {
      if (checkAll) {
        (STATE.gatekeeperRules || []).forEach(g => STATE.checkedGates.add(g.id));
      } else {
        STATE.checkedGates.clear();
      }
      renderGatekeeperGrid();
    }

    function updateGatekeeperBanner() {
      const total = (STATE.gatekeeperRules || []).length || 8;
      const count = STATE.checkedGates.size;
      const ms = STATE.currentCalculation?.market_and_spread || {};
      const isTakeUnder = ms.is_take_under_trap;
      const has8k101 = ms.has_recent_8k_item_1_01;
      const isStaleLeak = ms.is_stale_leak;
      const banner = document.getElementById('gatekeeper-status-banner');
      const textEl = document.getElementById('gatekeeper-banner-text');
      const countEl = document.getElementById('gatekeeper-counter');

      countEl.textContent = `${count} / ${total} GATES CLEARED`;

      if (isStaleLeak) {
        banner.className = 'verdict-banner verdict-fail';
        textEl.textContent = `⏳ STALE LEAK (${ms.leak_age_human || '>4h'} > 4.0H MAX WINDOW) — NON-ACTIONABLE / ORDER STAGING LOCKED`;
      } else if (isTakeUnder) {
        banner.className = 'verdict-banner verdict-fail';
        textEl.textContent = '🚨 GATE_6 TAKE-UNDER TRAP DETECTED — ORDER STAGING HARD-LOCKED';
      } else if (has8k101) {
        banner.className = 'verdict-banner verdict-fail';
        textEl.textContent = '🚨 GATE_2 FORM 8-K ITEM 1.01 ALREADY FILED — LEAK WINDOW DEAD';
      } else if (count === total) {
        banner.className = 'verdict-banner verdict-pass';
        textEl.textContent = '🟢 CLEARED HOT — STAGE 3-TRANCHE LIMIT ORDERS (5:30 PM – 7:00 PM EST)';
      } else {
        banner.className = 'verdict-banner verdict-warn';
        textEl.textContent = '⚠️ PRE-TRADE GATEKEEPER LOCKED — VERIFY & CHECK ALL 8 GATES BEFORE STAGING';
      }
    }

    async function updateCooldownTimer() {
      const timeVal = document.getElementById('inp-headline-time').value || '16:18';
      const res = await fetch('/api/cooldown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headline_time_est: timeVal }),
      });
      const cd = await res.json();
      document.getElementById('cooldown-milestones').innerHTML = `
        HFT Whipsaw Ends (T+45m): <strong style="color:var(--crimson);">${cd.hft_whipsaw_end_est}</strong> |
        Settled Entry Open (T+60m): <strong style="color:var(--emerald);">${cd.settled_window_open_est}</strong> |
        Window Close (T+180m): <strong style="color:var(--amber);">${cd.settled_window_close_est}</strong>
      `;
    }

    function renderWatchlistRow(row) {
      const badgeCls = row.verdict === 'PASS_HOT' ? 'badge-emerald' :
                       row.verdict === 'FAIL_TAKE_UNDER' ? 'badge-crimson' : 'badge-amber';
      const edgarBadge = row.edgar_8k?.status_badge || '🟢 NO 8-K ITEM 1.01';
      const ageCls = row.is_stale_leak ? 'badge-amber' : 'badge-emerald';
      const ageBadge = row.freshness_badge || (row.is_stale_leak ? `⏳ STALE (${row.leak_age_human})` : `🟢 FRESH (${row.leak_age_human})`);
      const rowStyle = row.is_stale_leak
        ? 'border-left:3px solid var(--amber);background:rgba(245,158,11,0.03);'
        : 'border-left:3px solid var(--emerald);';

      const isUnpriced = row.rumored_value === null || row.rumored_value === undefined || row.implied_deal_price === null;
      const modeStr = isUnpriced ? 'UNPRICED' : `${row.input_mode}: ${row.rumored_value}`;
      const impliedStr = isUnpriced ? '<span style="color:var(--amber);">AWAITING PRICE LEAK</span>' : `$${Number(row.implied_deal_price).toFixed(2)}`;
      const spreadStr = isUnpriced
        ? '<span class="badge badge-amber">UNPRICED</span>'
        : `<span class="badge ${badgeCls}">${row.gross_spread_pct >= 0 ? '+' : ''}${Number(row.gross_spread_pct).toFixed(2)}%</span>`;
      const actionBtn = isUnpriced
        ? `<button class="btn btn-sm" disabled title="Wait for explicit per-share or EV price to leak">⏳ Await Price</button>`
        : `<button class="btn btn-sm ${row.is_stale_leak ? '' : 'btn-primary'}"
             onclick="loadPreset('${row.ticker}', '${row.input_mode}', ${row.rumored_value}, 380000, 1.5)">
             ${row.is_stale_leak ? '⏳ Inspect Stale' : '⚡ Stage Tranches'}
           </button>`;

      return `
        <tr style="${rowStyle}">
          <td>
            <strong style="color:var(--cyan);font-size:13px;">$${row.ticker}</strong>
            <span style="color:var(--text-secondary);font-size:11px;">(${modeStr})</span>
            <div style="font-family:var(--font-sans);font-size:11px;color:var(--text-primary);max-width:260px;margin-top:2px;">
              ${row.gate_notes || row.rumor_headline}
            </div>
          </td>
          <td>
            <span class="badge ${ageCls}">${ageBadge}</span>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">Broke: ${row.leak_timestamp_est || 'Historical'}</div>
          </td>
          <td class="text-right">
            <span style="color:var(--text-secondary);">$${row.regular_market_price.toFixed(2)}</span><br/>
            <strong>$${row.extended_hours_price.toFixed(2)}</strong>
          </td>
          <td class="text-right" style="font-weight:700;">${impliedStr}</td>
          <td class="text-right">
            ${spreadStr}
          </td>
          <td style="font-size:11px;">${edgarBadge}</td>
          <td class="text-right" style="white-space:nowrap;">
            ${actionBtn}
            <button class="btn btn-sm" onclick="removeWatchlistTicker('${row.ticker}')">✕</button>
          </td>
        </tr>
      `;
    }

    function renderWatchlistTable() {
      const freshTbody = document.getElementById('fresh-watchlist-table-body');
      const staleTbody = document.getElementById('watchlist-table-body');
      const rows = STATE.watchlist || [];
      const freshRows = rows.filter(r => !r.is_stale_leak);
      const staleRows = rows.filter(r => r.is_stale_leak);

      document.getElementById('fresh-wl-count-badge').textContent = `${freshRows.length} FRESH (<=4H)`;
      document.getElementById('stale-wl-count-badge').textContent = `${staleRows.length} STALE (>4H)`;

      if (freshRows.length === 0) {
        freshTbody.innerHTML = `
          <tr>
            <td colspan="7" style="padding:10px 12px;color:var(--text-secondary);font-size:11.5px;">
              🔎 <strong>0 Fresh Watchlist Leaks (&lt;= 4.0 hours old)</strong> currently active. Verified November 2026 Watchlist situations (<strong>$U, $HELE, $WEN, $RYTM, $GPN</strong>) are separated below as <strong>⏳ Stale Rumors (&gt; 4.0h old)</strong>.
            </td>
          </tr>
        `;
      } else {
        freshTbody.innerHTML = freshRows.map(renderWatchlistRow).join('');
      }

      staleTbody.innerHTML = staleRows.map(renderWatchlistRow).join('');
    }

    async function addWatchlistTicker() {
      const ticker = document.getElementById('wl-ticker').value.trim().toUpperCase();
      if (!ticker) return;
      const mode = document.getElementById('wl-mode').value;
      const val = parseFloat(document.getElementById('wl-val').value) || 5.0;
      const headline = document.getElementById('wl-headline').value.trim() || `All-cash PE buyout rumor on $${ticker}`;

      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'add',
          ticker: ticker,
          input_mode: mode,
          rumored_value: val,
          rumor_headline: headline,
        }),
      });
      const data = await res.json();
      STATE.watchlist = data.watchlist || [];
      renderWatchlistTable();
      document.getElementById('wl-ticker').value = '';
      document.getElementById('wl-headline').value = '';
    }

    async function removeWatchlistTicker(ticker) {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'remove', ticker: ticker }),
      });
      const data = await res.json();
      STATE.watchlist = data.watchlist || [];
      renderWatchlistTable();
    }

    function triggerWireScan() {
      window.location.href = '/scan';
    }

    async function triggerNightlyEmailModal() {
      const btn = document.getElementById('btn-fire-email');
      btn.textContent = '⏳ GENERATING 5:00 PM REPORT...';
      try {
        const res = await fetch('/api/fire-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dry_run: true }),
        });
        const data = await res.json();
        document.getElementById('modal-email-subject').textContent = data.subject;
        document.getElementById('modal-email-meta').textContent =
          `Status: ${data.delivery_status} | Saved to: ${data.report_path} | Generated: ${data.generated_at}`;
        const iframe = document.getElementById('email-preview-iframe');
        iframe.srcdoc = data.html_content;
        document.getElementById('email-modal').classList.add('open');
      } finally {
        btn.textContent = '✉️ FIRE 5:00 PM EMAIL REPORT NOW (DRY-RUN / SMTP)';
      }
    }

    function closeEmailModal() {
      document.getElementById('email-modal').classList.remove('open');
    }

    function renderBiopharmaAuditCards(audit) {
      if (!audit) return;
      const auditEl = document.getElementById('bio-live-audit-card');
      const trancheEl = document.getElementById('bio-live-tranche-card');
      if (!auditEl || !trancheEl) return;

      const badgeCls = audit.all_biopharma_gates_passed ? 'badge-emerald' : 'badge-crimson';
      const gatesHtml = (audit.gate_checks || []).map(g => `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;padding:5px 8px;border-bottom:1px solid var(--border-hairline);font-size:11.5px;">
          <div>
            <span class="mono" style="font-weight:700;color:${g.passed ? 'var(--emerald)' : 'var(--crimson)'};">
              ${g.passed ? '✅' : '❌'} [${g.id.split('_').slice(0,3).join('_')}]
            </span>
            <strong style="color:var(--text-primary);margin-left:4px;">${g.title}:</strong>
            <div style="color:var(--text-secondary);font-size:11px;margin-top:1px;">${g.detail}</div>
          </div>
          <span class="badge ${g.passed ? 'badge-emerald' : 'badge-crimson'}">${g.passed ? 'PASS' : 'FAIL'}</span>
        </div>
      `).join('');

      auditEl.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(15,23,42,0.85);border-radius:5px;border:1px solid var(--border-hairline);margin-bottom:8px;">
          <div>
            <span class="mono" style="font-size:15px;font-weight:700;color:var(--cyan);">$${audit.ticker}</span>
            <span class="mono" style="font-size:11.5px;color:var(--text-secondary);margin-left:6px;">
              Suitor: <strong style="color:var(--text-primary);">${audit.named_pharma_suitor}</strong> | EV: $${audit.deal_ev_billions.toFixed(1)}B
            </span>
          </div>
          <span class="badge ${badgeCls}">${audit.verdict} (${audit.passed_gates_count}/${audit.total_gates_count} GATES)</span>
        </div>
        <div class="mono" style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px;font-size:11px;background:var(--bg-canvas);padding:7px 9px;border-radius:4px;border:1px solid var(--border-hairline);">
          <div>
            <span style="color:var(--text-muted);font-size:10px;display:block;">ENTRY (% OF ANCHOR)</span>
            <strong style="color:${audit.passes_anchor_92pct_gate ? 'var(--emerald)' : 'var(--crimson)'};">$${audit.current_price.toFixed(2)} (${audit.entry_pct_of_anchor_display}%)</strong>
          </div>
          <div>
            <span style="color:var(--text-muted);font-size:10px;display:block;">HARD 92% CEILING</span>
            <strong style="color:var(--amber);">&le; $${Number(audit.hard_ceiling_92pct || audit.base_cash_bid_per_share * 0.92).toFixed(2)}</strong>
          </div>
          <div>
            <span style="color:var(--text-muted);font-size:10px;display:block;">ANCHOR &rarr; SWEETENED</span>
            <strong style="color:var(--cyan);">$${audit.base_cash_bid_per_share.toFixed(2)} &rarr; $${audit.sweetened_ceiling_per_share.toFixed(2)}</strong>
          </div>
          <div>
            <span style="color:var(--text-muted);font-size:10px;display:block;">HOLD CLOCK / FLOOR</span>
            <strong style="color:var(--emerald);">10–45d | $${audit.unaffected_price.toFixed(2)}</strong>
          </div>
        </div>
        <div style="border:1px solid var(--border-hairline);border-radius:5px;overflow:hidden;">
          ${gatesHtml}
        </div>
      `;

      const pnl = audit.pnl_summary || {};
      const rowsHtml = (audit.tranche_ladder || []).map(t => `
        <tr>
          <td>
            <strong style="color:var(--cyan);">T${t.tranche_number}</strong>
            <span style="color:var(--text-secondary);">(${t.weight_pct}% | -${t.target_discount_pct.toFixed(1)}% Disc)</span>
            ${t.actionable_at_open ? '<span class="badge badge-emerald" style="margin-left:4px;">ACTIONABLE</span>' : ''}
          </td>
          <td class="text-right">${fmtUSD(t.allocation_usd)}</td>
          <td class="text-right" style="color:var(--emerald);font-weight:700;">$${t.limit_price.toFixed(2)}</td>
          <td class="text-right">${t.shares.toLocaleString()} sh</td>
          <td class="text-right" style="color:var(--emerald);">+${fmtUSD(t.base_bid_profit_usd)}</td>
          <td class="text-right" style="color:var(--cyan);font-weight:700;">+${fmtUSD(t.sweetened_bid_profit_usd)}</td>
        </tr>
      `).join('');

      trancheEl.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
          <div class="tax-box tax-ira" style="margin:0;">
            <div class="mono" style="font-size:10.5px;color:#34D399;">IRA 0%-TAX @ BASE ($${audit.base_cash_bid_per_share.toFixed(2)}/sh)</div>
            <div class="mono" style="font-size:18px;font-weight:700;color:var(--emerald);">+${fmtUSD(pnl.ira_base_bid_net_profit_usd)}</div>
            <div class="mono" style="font-size:10.5px;color:var(--text-secondary);">NYC 54.5% Tax: +${fmtUSD(pnl.nyc_base_bid_net_profit_usd)}</div>
          </div>
          <div class="tax-box" style="margin:0;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.4);">
            <div class="mono" style="font-size:10.5px;color:var(--cyan);">IRA 0%-TAX @ SWEETENED ($${audit.sweetened_ceiling_per_share.toFixed(2)}/sh)</div>
            <div class="mono" style="font-size:18px;font-weight:700;color:var(--cyan);">+${fmtUSD(pnl.ira_sweetened_bid_net_profit_usd)}</div>
            <div class="mono" style="font-size:10.5px;color:var(--text-secondary);">NYC 54.5% Tax: +${fmtUSD(pnl.nyc_sweetened_bid_net_profit_usd)}</div>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Tranche</th>
              <th class="text-right">Allocation</th>
              <th class="text-right">Limit Px</th>
              <th class="text-right">Shares</th>
              <th class="text-right">Base Profit</th>
              <th class="text-right">Sweetened Profit</th>
            </tr>
          </thead>
          <tbody class="mono">
            ${rowsHtml}
          </tbody>
        </table>
        <div class="mono" style="margin-top:8px;font-size:11px;color:var(--text-secondary);display:flex;justify-content:space-between;flex-wrap:wrap;">
          <span>Hard Gate 5 Ceiling (92% of Anchor): <strong style="color:var(--amber);">$${Number(audit.hard_ceiling_92pct || audit.base_cash_bid_per_share * 0.92).toFixed(2)}</strong></span>
          <span>Expected Hold Clock: <strong style="color:var(--cyan);">${audit.expected_hold_clock || '10–45 Days'}</strong></span>
        </div>
      `;
    }

    async function loadBiopharmaCaseStudy(ticker) {
      const presets = {
        RYTM: {
          ticker: 'RYTM', current_price: 113.00, unaffected_price: 86.44, walk_away_floor_price: 92.00,
          base_cash_bid_per_share: 124.00, sweetened_ceiling_per_share: 134.00,
          deal_ev_billions: 10.0, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'Imcivree ($92.1M Q3 rev, +79.6% YoY / +29% QoQ) + Nov 2 $750M KKR/Blackstone facility & 1% LG Chem royalty buydown',
          named_pharma_suitor: 'AstraZeneca ($124/sh Offer) + Reported 2nd Bidder ($134–$145+ Target)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: true, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 113.00
        },
        GBT: {
          ticker: 'GBT', current_price: 63.00, unaffected_price: 48.00, walk_away_floor_price: 51.00,
          base_cash_bid_per_share: 68.50, sweetened_ceiling_per_share: 68.50,
          deal_ev_billions: 5.4, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'Oxbryta FDA-approved commercial rare blood disease franchise (Aug 5 WSJ leak -> Aug 8 Pfizer $68.50/sh 8-K)',
          named_pharma_suitor: 'Pfizer ($68.50/sh All-Cash Buyout in 3 Days — +8.73% Post-Leak)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: true, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 63.00
        },
        RNA: {
          ticker: 'RNA', current_price: 57.80, unaffected_price: 38.10, walk_away_floor_price: 44.00,
          base_cash_bid_per_share: 64.00, sweetened_ceiling_per_share: 72.00,
          deal_ev_billions: 12.0, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'Pivotal AOC RNA data + $1.4B cash floor ("Walk-Away Leverage" forced Novartis to $72 + SpinCo)',
          named_pharma_suitor: 'Novartis (Completed $72.00/sh Cash + SpinCo over 56d)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: true, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 57.80
        },
        CDTX: {
          ticker: 'CDTX', current_price: 183.50, unaffected_price: 105.99, walk_away_floor_price: 125.00,
          base_cash_bid_per_share: 202.00, sweetened_ceiling_per_share: 221.50,
          deal_ev_billions: 9.2, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'FDA-approved Rezzayo + pivotal CD388 universal flu asset (4-bidder auction)',
          named_pharma_suitor: 'Merck & Co. (Outbid 3 Rivals -> $221.50/sh Cash in 8d)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: true, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 183.50
        },
        RVMD: {
          ticker: 'RVMD', current_price: 117.63, unaffected_price: 94.50, walk_away_floor_price: 94.47,
          base_cash_bid_per_share: 135.00, sweetened_ceiling_per_share: 145.00,
          deal_ev_billions: 28.0, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'RASONQUE RAS(ON) asset: Merck walked away Jan 26 (-19.69% to $94.47), then rallied +68.9% to $198.50 on FDA approval',
          named_pharma_suitor: 'Merck & Co. (Walk-Away on Price -> +68.9% Standalone Recovery to $198.50)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: false, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 117.63
        },
        BMRN: {
          ticker: 'BMRN', current_price: 96.00, unaffected_price: 88.00, walk_away_floor_price: 76.80,
          base_cash_bid_per_share: 102.00, sweetened_ceiling_per_share: 102.00,
          deal_ev_billions: 18.0, fda_approved_commercial_anchor: true,
          commercial_drug_name: 'FAIL BIO_GATE_1 & 5: Commercial Voxzogo rare-disease leader, but unpriced street chatter without dollar bid drifted -20.0%',
          named_pharma_suitor: 'Unnamed Pharma Chatter (No Dollar Bid Leaked -> -20.00% Drift)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: false, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 96.00
        },
        VKTX: {
          ticker: 'VKTX', current_price: 72.00, unaffected_price: 60.00, walk_away_floor_price: 39.60,
          base_cash_bid_per_share: 75.00, sweetened_ceiling_per_share: 75.00,
          deal_ev_billions: 8.5, fda_approved_commercial_anchor: false,
          commercial_drug_name: 'FAIL BIO_GATE_1 & 2: Clinical Phase 2 obesity VK2735 with no commercial revenue anchor -> -45.00% 6-month bleed',
          named_pharma_suitor: 'Unnamed Obesity Chatter (No Deal Signed -> -45.00% Bleed)',
          zero_moa_overlap: true, bid_sweetening_or_cvr: false, clip_usd: 190000,
          live_position_usd: 100000, live_position_entry_price: 72.00
        }
      };
      const reqBody = presets[ticker] || presets.RYTM;
      const res = await fetch('/api/biopharma-evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      });
      const audit = await res.json();
      renderBiopharmaAuditCards(audit);
    }

    function filterBiopharmaTable(mode) {
      STATE.biopharmaFilter = mode;
      renderBiopharmaBacktestPanel();
    }

    function renderBiopharmaBacktestPanel() {
      const bt = STATE.biopharmaBacktest;
      if (!bt) return;
      renderBiopharmaAuditCards(bt.live_rytm_audit);

      // Render Live $100,000 @ $113.00 (~885 Shares) $RYTM Scenario Payoff & Formalization Calendar Strip
      const stripEl = document.getElementById('bio-rytm-100k-strip');
      if (stripEl && bt.live_rytm_audit && bt.live_rytm_audit.live_100k_lot_scenarios) {
        const lot = bt.live_rytm_audit.live_100k_lot_scenarios;
        const windows = bt.live_rytm_audit.deal_timeline_windows || [];
        const scCards = (lot.scenarios || []).map(sc => {
          const isNeg = sc.ira_0pct_tax_pnl_usd < 0;
          const borderCol = isNeg ? 'rgba(239,68,68,0.45)' : 'rgba(16,185,129,0.45)';
          const valCol = isNeg ? 'var(--crimson)' : 'var(--emerald)';
          const sign = isNeg ? '' : '+';
          return `
            <div style="background:rgba(15,23,42,0.9);border:1px solid ${borderCol};border-radius:6px;padding:9px 11px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span class="mono" style="font-size:11px;font-weight:700;color:var(--cyan);">${sc.scenario}</span>
                <span class="badge ${isNeg ? 'badge-crimson' : 'badge-emerald'}">${sc.probability_pct}% PROB</span>
              </div>
              <div class="mono" style="font-size:17px;font-weight:700;color:${valCol};">
                ${sign}${fmtUSD(sc.ira_0pct_tax_pnl_usd)} (${sign}${sc.return_pct.toFixed(1)}% @ $${sc.exit_price.toFixed(2)}/sh)
              </div>
              <div class="mono" style="font-size:10px;color:var(--text-muted);margin-top:2px;">
                NYC Taxable (54.5%): ${sign}${fmtUSD(sc.nyc_taxable_pnl_usd)}${sc.pct_of_4m_net_worth ? ` | <strong style="color:#FCA5A5;">${sc.pct_of_4m_net_worth}% of $4.0M Net Worth</strong>` : ''}
              </div>
              <div style="font-size:11px;color:var(--text-secondary);margin-top:4px;line-height:1.35;">${sc.notes}</div>
            </div>
          `;
        }).join('');

        const winCards = windows.map(w => `
          <div style="background:rgba(15,23,42,0.85);border:1px solid var(--border-hairline);border-left:3px solid var(--cyan);border-radius:5px;padding:8px 10px;">
            <div class="mono" style="font-size:11px;font-weight:700;color:var(--emerald);margin-bottom:2px;">${w.window}: <span style="color:var(--text-primary);">${w.target_dates}</span></div>
            <div style="font-size:11px;color:var(--text-secondary);line-height:1.35;">${w.catalysts_and_mechanics}</div>
          </div>
        `).join('');

        stripEl.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border-hairline);">
            <div class="mono" style="font-size:12px;font-weight:700;color:#34D399;">
              🎯 LIVE $100,000 POSITION AT $113.00 (~${lot.shares} SHARES) ON $RYTM — 3-SCENARIO PAYOFF MATRIX &amp; SCHEDULE 14D-9 FORMALIZATION CLOCK
            </div>
            <div class="mono" style="font-size:11.5px;">
              <span class="badge badge-emerald">PROB-WEIGHTED EV: +${fmtUSD(lot.probability_weighted_ev_usd)} (+${lot.probability_weighted_ev_pct}%)</span>
              <span class="badge badge-neutral" style="border:1px solid var(--amber);color:#FBBF24;">${lot.sizing_rule_verdict}</span>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px;">
            ${scCards}
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
            ${winCards}
          </div>
        `;
      }

      // Render Regime B Pre-Rumor Walk-Away Leverage Radar
      const regBEl = document.getElementById('bio-regime-b-grid');
      if (regBEl && bt.regime_b_pre_leak_radar) {
        regBEl.innerHTML = bt.regime_b_pre_leak_radar.map(r => `
          <div style="background:rgba(15,23,42,0.85);border:1px solid rgba(16,185,129,0.35);border-radius:5px;padding:8px 10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
              <span class="mono" style="font-size:13px;font-weight:700;color:var(--cyan);">$${r.ticker}</span>
              <span class="badge badge-emerald" style="font-size:9.5px;">${r.regime_status.replace(/_/g, ' ')}</span>
            </div>
            <div class="mono" style="font-size:10.5px;color:#34D399;margin-bottom:4px;">${r.pro_forma_cash_runway}</div>
            <div style="font-size:11px;color:var(--text-secondary);line-height:1.35;">${r.walk_away_leverage_catalyst}</div>
          </div>
        `).join('');
      }

      // Render 4 Purged Untradable Weekend / Overnight Gaps
      const purgedEl = document.getElementById('bio-purged-gaps-list');
      if (purgedEl && bt.purged_untradable_weekend_gaps) {
        purgedEl.innerHTML = bt.purged_untradable_weekend_gaps.map(g => `
          <div style="padding:4px 0;border-bottom:1px dashed rgba(51,65,85,0.6);">
            <strong style="color:#FCA5A5;">$${g.ticker}</strong> (${g.buyer}): ${g.actual_market_reality}
          </div>
        `).join('');
      }

      const tbody = document.getElementById('bio-backtest-tbody');
      if (!tbody) return;
      let events = bt.historical_events || [];
      if (STATE.biopharmaFilter === 'QUALIFIED') {
        events = events.filter(e => e.cleared_6_biopharma_gates);
      } else if (STATE.biopharmaFilter === 'FILTERED') {
        events = events.filter(e => !e.cleared_6_biopharma_gates);
      }

      tbody.innerHTML = events.map(ev => {
        const isPos = ev.realized_return_pct > 0;
        const retCls = isPos ? 'var(--emerald)' : 'var(--crimson)';
        const gateBadge = ev.cleared_6_biopharma_gates
          ? '<span class="badge badge-emerald">✅ QUALIFIED REGIME A (&le;92% ANCHOR)</span>'
          : '<span class="badge badge-amber">❌ DISQUALIFIED BY GATES</span>';
        const rowBorder = ev.cleared_6_biopharma_gates
          ? 'border-left:3px solid var(--emerald);background:rgba(16,185,129,0.03);'
          : (isPos ? 'border-left:3px solid var(--amber);' : 'border-left:3px solid var(--crimson);background:rgba(239,68,68,0.05);');
        const cvrTag = ev.cvr_per_share > 0 ? ` <span class="badge badge-emerald">+$${ev.cvr_per_share.toFixed(0)} CVR</span>` : '';
        const anchorPctBadge = ev.passes_anchor_92pct_gate
          ? `<span style="color:var(--emerald);font-size:10.5px;">(${ev.entry_pct_of_anchor_display}% of $${ev.leaked_valuation_anchor.toFixed(0)} &le;92%)</span>`
          : `<span style="color:var(--crimson);font-size:10.5px;">(${ev.entry_pct_of_anchor_display}% of $${ev.leaked_valuation_anchor.toFixed(0)} &gt;92%)</span>`;

        return `
          <tr style="${rowBorder}">
            <td>
              <strong style="color:var(--cyan);font-size:13px;">$${ev.ticker}</strong>
              <span style="color:var(--text-primary);font-family:var(--font-sans);font-size:11.5px;margin-left:4px;">${ev.company_name}</span>
              <div style="font-size:10.5px;color:var(--text-muted);">${ev.leak_date} &rarr; ${ev.resolution_date} (<strong>${ev.hold_trading_days}d hold</strong>) | ${ev.leak_source}</div>
            </td>
            <td style="font-family:var(--font-sans);font-size:11.5px;">
              <strong>${ev.buyer}</strong> (${fmtUSD(ev.deal_ev_billions * 1e9).replace(',000,000,000','B')})
              <div style="font-size:11px;color:${ev.fda_approved_commercial_anchor ? '#34D399' : '#FCA5A5'};margin-top:2px;">
                ${ev.fda_approved_commercial_anchor ? '🟢 Commercial/Pivotal:' : '🚨 Unapproved Risk:'} ${ev.commercial_drug_note}
              </div>
            </td>
            <td class="text-right">
              <span style="color:var(--text-secondary);">$${ev.unaffected_price.toFixed(2)}</span> &rarr;
              <strong>$${ev.settled_post_leak_entry_price.toFixed(2)}</strong><br/>
              ${anchorPctBadge}
            </td>
            <td class="text-right">
              <strong>$${ev.resolution_price.toFixed(2)}</strong>
              ${ev.final_deal_cash_per_share ? `<div style="font-size:10.5px;color:var(--emerald);">Deal: $${ev.final_deal_cash_per_share.toFixed(2)}/sh${cvrTag}</div>` : '<div style="font-size:10.5px;color:var(--crimson);">WALK-AWAY / NO DEAL</div>'}
              ${ev.standalone_recovery_note ? `<div style="font-size:10px;color:var(--cyan);">${ev.standalone_recovery_note}</div>` : ''}
            </td>
            <td class="text-right" style="font-weight:700;color:${retCls};">
              ${ev.realized_return_pct >= 0 ? '+' : ''}${ev.realized_return_pct.toFixed(2)}%
            </td>
            <td class="text-right" style="font-weight:700;color:${retCls};">
              ${ev.ira_0pct_pnl_usd >= 0 ? '+' : ''}${fmtUSD(ev.ira_0pct_pnl_usd)}
            </td>
            <td style="font-family:var(--font-sans);font-size:11px;">
              ${gateBadge}
              <div style="color:var(--text-secondary);margin-top:3px;">${ev.disqualification_note}</div>
            </td>
          </tr>
        `;
      }).join('');
    }

    window.addEventListener('DOMContentLoaded', initDashboard);
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_terminal_ui() -> HTMLResponse:
    """Serve the Arb Cannon institutional trading terminal HTML interface."""
    return HTMLResponse(content=TERMINAL_HTML, status_code=200)


SCAN_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ARB CANNON // Live M&amp;A Wire &amp; EDGAR 8-K Deep Scanner</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-canvas: #0B0F19;
      --bg-card: #111827;
      --bg-elevated: #0F172A;
      --border-hairline: #1E293B;
      --border-accent: #334155;
      --text-primary: #F8FAFC;
      --text-secondary: #94A3B8;
      --text-muted: #64748B;
      --emerald: #10B981;
      --emerald-bg: rgba(16, 185, 129, 0.14);
      --amber: #F59E0B;
      --amber-bg: rgba(245, 158, 11, 0.14);
      --crimson: #EF4444;
      --crimson-bg: rgba(239, 68, 68, 0.16);
      --cyan: #38BDF8;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-canvas);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.45;
      font-variant-numeric: tabular-nums;
      min-height: 100vh;
    }

    .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

    .command-bar {
      position: sticky;
      top: 0;
      z-index: 100;
      background-color: rgba(11, 15, 25, 0.96);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--border-hairline);
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .brand-block { display: flex; align-items: center; gap: 12px; }

    .brand-badge {
      background: linear-gradient(135deg, #064E3B 0%, #0F172A 100%);
      border: 1px solid var(--emerald);
      color: var(--emerald);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 4px;
    }

    .btn {
      cursor: pointer;
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: 5px;
      border: 1px solid var(--border-accent);
      background-color: var(--bg-card);
      color: var(--text-primary);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }

    .btn:hover { border-color: var(--cyan); background-color: #1E293B; }
    .btn-primary { background-color: #065F46; border-color: var(--emerald); color: #ECFDF5; }
    .btn-primary:hover { background-color: #047857; }
    .btn-sm { padding: 5px 10px; font-size: 11px; }

    .workspace {
      max-width: 1520px;
      margin: 0 auto;
      padding: 20px 20px 48px 20px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .card {
      background-color: var(--bg-card);
      border: 1px solid var(--border-hairline);
      border-radius: 8px;
      overflow: hidden;
    }

    .card-header {
      background-color: var(--bg-elevated);
      border-bottom: 1px solid var(--border-hairline);
      padding: 12px 16px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .card-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .card-body { padding: 16px; }

    /* LOADING PROGRESS PANEL */
    .scanner-progress-card {
      background: linear-gradient(180deg, #0F172A 0%, #111827 100%);
      border: 1px solid var(--cyan);
      border-radius: 8px;
      padding: 20px 24px;
    }

    .progress-header {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 14px;
    }

    .spinner {
      width: 24px;
      height: 24px;
      border: 3px solid rgba(56, 189, 248, 0.25);
      border-top-color: var(--cyan);
      border-radius: 50%;
      animation: spin 0.85s linear infinite;
    }

    .spinner.done {
      animation: none;
      border-color: var(--emerald);
      background-color: var(--emerald-bg);
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    .progress-bar-track {
      width: 100%;
      height: 8px;
      background-color: #1E293B;
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 14px;
    }

    .progress-bar-fill {
      height: 100%;
      width: 10%;
      background: linear-gradient(90deg, var(--cyan) 0%, var(--emerald) 100%);
      transition: width 0.35s ease;
    }

    .stage-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }

    @media (max-width: 1100px) {
      .stage-grid { grid-template-columns: 1fr; }
    }

    .stage-step {
      background-color: rgba(11, 15, 25, 0.75);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 10px 12px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: var(--text-secondary);
    }

    .stage-step.active {
      border-color: var(--cyan);
      color: var(--text-primary);
      background-color: rgba(56, 189, 248, 0.08);
    }

    .stage-step.done {
      border-color: var(--emerald);
      color: #34D399;
      background-color: rgba(16, 185, 129, 0.08);
    }

    /* SUMMARY KPI ROW */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
    }

    .kpi-box {
      background-color: var(--bg-card);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 12px 14px;
    }

    .kpi-label {
      font-size: 11px;
      color: var(--text-secondary);
      text-transform: uppercase;
      font-family: var(--font-mono);
    }

    .kpi-val {
      font-family: var(--font-mono);
      font-size: 22px;
      font-weight: 700;
      margin-top: 4px;
    }

    /* BADGES & REJECTION REASONS */
    .badge {
      display: inline-block;
      padding: 2px 7px;
      margin: 2px 4px 2px 0;
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 600;
    }

    .badge-emerald { background-color: var(--emerald-bg); color: #34D399; border: 1px solid rgba(16,185,129,0.35); }
    .badge-amber { background-color: var(--amber-bg); color: #FBBF24; border: 1px solid rgba(245,158,11,0.35); }
    .badge-crimson { background-color: var(--crimson-bg); color: #FCA5A5; border: 1px solid rgba(239,68,68,0.4); }
    .badge-neutral { background-color: #1E293B; color: #CBD5E1; }

    .reason-box {
      margin-top: 8px;
      padding: 8px 12px;
      background-color: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.35);
      border-left: 3px solid var(--crimson);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: #FCA5A5;
    }

    .reason-box div { margin-bottom: 3px; }
    .reason-box div:last-child { margin-bottom: 0; }

    .rumor-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 14px;
    }

    @media (max-width: 1100px) {
      .rumor-grid, .kpi-grid { grid-template-columns: 1fr; }
    }

    .rumor-card {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border-hairline);
      border-radius: 6px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 10px;
    }

    table { width: 100%; border-collapse: collapse; }
    th {
      background-color: var(--bg-elevated);
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      padding: 9px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border-hairline);
    }
    td {
      padding: 12px;
      border-bottom: 1px solid var(--border-hairline);
      vertical-align: top;
    }
    .text-right { text-align: right; }
  </style>
</head>
<body>

  <header class="command-bar">
    <div class="brand-block">
      <span class="brand-badge">ARB CANNON // DEEP SCANNER</span>
      <div>
        <div style="font-size:16px;font-weight:700;">LIVE M&amp;A WIRE &amp; SEC EDGAR 8-K GATEKEEPER AUDIT</div>
        <div class="mono" style="font-size:11px;color:var(--text-secondary);">
          48-HOUR GOOGLE NEWS RSS SWEEP + LIVE SEC EDGAR 8-K ITEM 1.01 + YFINANCE EXTENDED-HOURS AUDIT
        </div>
      </div>
    </div>
    <div style="display:flex;gap:10px;">
      <button class="btn btn-primary" id="btn-rescan" onclick="executeDeepScan()">
        🔄 RE-RUN LIVE M&amp;A DEEP SCAN
      </button>
      <a href="/" class="btn">
        &larr; BACK TO COMMAND CENTER
      </a>
    </div>
  </header>

  <main class="workspace">

    <!-- LIVE WORK / LOADING PROGRESS PANEL -->
    <section class="scanner-progress-card" id="progress-panel">
      <div class="progress-header">
        <div class="spinner" id="scan-spinner"></div>
        <div>
          <div style="font-size:15px;font-weight:700;" id="scan-status-title">
            EXECUTING LIVE M&amp;A WIRE &amp; SEC EDGAR 8-K DEEP SCAN...
          </div>
          <div class="mono" style="font-size:12px;color:var(--text-secondary);" id="scan-status-subtitle">
            Initializing 4-stage institutional Gatekeeper pipeline...
          </div>
        </div>
      </div>

      <div class="progress-bar-track">
        <div class="progress-bar-fill" id="scan-progress-bar"></div>
      </div>

      <div class="stage-grid">
        <div class="stage-step active" id="stage-1">
          <strong>STAGE 1 // RSS WIRE SWEEP</strong><br/>
          Querying Google News RSS (48h) for 'advanced talks', 'nearing a deal', 'take private'...
        </div>
        <div class="stage-step" id="stage-2">
          <strong>STAGE 2 // &lt;=4.0H FRESHNESS &amp; HEADLINE GATE</strong><br/>
          Enforcing &lt;=4.0h Leak Freshness Gate, Tier-1 desk (GATE_2), 11th-hour urgency (GATE_3)...
        </div>
        <div class="stage-step" id="stage-3">
          <strong>STAGE 3 // SEC EDGAR 8-K STREAM</strong><br/>
          Checking data.sec.gov/submissions for Form 8-K Item 1.01 definitive merger filings...
        </div>
        <div class="stage-step" id="stage-4">
          <strong>STAGE 4 // XBRL NET-DEBT &amp; QUOTES</strong><br/>
          Fetching live yfinance extended-hours prices &amp; 10-Q Net-Debt waterfalls (GATE_6)...
        </div>
      </div>
    </section>

    <!-- SCAN RESULTS CONTAINER (Revealed as soon as scan finishes) -->
    <div id="scan-results-container" style="display:none;flex-direction:column;gap:18px;">

      <!-- KPI Summary Strip -->
      <div class="kpi-grid">
        <div class="kpi-box">
          <div class="kpi-label">Fresh (&lt;=4h) Qualified Triggers</div>
          <div class="kpi-val" id="kpi-triggers" style="color:var(--emerald);">0</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Filtered / Stale (&gt;4h) Wire Hits</div>
          <div class="kpi-val" id="kpi-filtered-wires" style="color:var(--amber);">0</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Fresh (&lt;=4h) Watchlist Leaks</div>
          <div class="kpi-val" id="kpi-watchlist-count" style="color:var(--cyan);">0</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Separated Stale (&gt;4h) Benchmarks</div>
          <div class="kpi-val" id="kpi-disqualified" style="color:var(--crimson);">4</div>
        </div>
      </div>

      <!-- Top Verdict Banner -->
      <div id="zero-trigger-banner" style="padding:16px 20px;border-radius:8px;background-color:rgba(245,158,11,0.12);border:1px solid var(--amber);">
        <div class="mono" style="font-size:14px;font-weight:700;color:#FBBF24;margin-bottom:4px;" id="banner-headline">
          🔎 0 FRESH (&lt;= 4.0H) QUALIFIED TRIGGERS CLEARED — SURFACING SEPARATED STALE RUMORS &amp; FILTERED-OUT OPPORTUNITIES BELOW
        </div>
        <div style="font-size:12.5px;color:var(--text-primary);" id="banner-subtext">
          Actionable M&amp;A leak arbitrage requires a scoop within the last 4.0 hours. All older rumors (&gt; 4.0 hours old, including $BMBL, $WEN, $U, $GPN) are immediately flagged as STALE LEAKS and separated below with their exact disqualification reasons.
        </div>
      </div>

      <!-- SECTION 1A: ACTIVE FRESH WATCHLIST LEAKS (<= 4.0 HOURS OLD) -->
      <section class="card" style="border-color:rgba(16,185,129,0.45);">
        <div class="card-header" style="background:rgba(16,185,129,0.12);">
          <div class="card-title" style="color:#34D399;">
            <span>🟢 1A. ACTIVE FRESH WATCHLIST LEAKS (&lt;= 4.0 HOURS OLD — ACTIONABLE WINDOW)</span>
          </div>
          <span class="badge badge-emerald" id="scan-fresh-wl-badge">0 FRESH (&lt;=4H)</span>
        </div>
        <div class="card-body" id="fresh-watchlist-rumors-grid">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- SECTION 1B: SEPARATED STALE WATCHLIST RUMORS (> 4.0 HOURS OLD) -->
      <section class="card" style="border-color:rgba(245,158,11,0.45);">
        <div class="card-header" style="background:rgba(245,158,11,0.12);">
          <div class="card-title" style="color:#FBBF24;">
            <span>⏳ 1B. VERIFIED NOVEMBER 2026 WATCHLIST SITUATIONS (&gt; 4.0 HOURS OLD — FACTUAL NOTES)</span>
          </div>
          <span class="badge badge-amber" id="scan-stale-wl-badge">5 STALE (&gt;4H)</span>
        </div>
        <div class="card-body">
          <div class="rumor-grid" id="watchlist-rumors-grid">
            <!-- Populated by JS -->
          </div>
        </div>
      </section>

      <!-- SECTION 2: LIVE WIRE RUMORS & FILTERED-OUT M&A HEADLINES -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>📡 2. LIVE M&amp;A WIRE HITS — VERBATIM HEADLINES &amp; FACTUAL KEYWORD TAGS</span>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-sm" onclick="setScanWireFilter('ALL')">All Scanned Rumors</button>
            <button class="btn btn-sm btn-primary" onclick="setScanWireFilter('FRESH')">🟢 Fresh (&lt;=4h) Only</button>
            <button class="btn btn-sm" onclick="setScanWireFilter('STALE')">⏳ Stale (&gt;4h) Only</button>
            <button class="btn btn-sm" onclick="setScanWireFilter('TIER1')">🟢 Tier-1 Desk Only</button>
          </div>
        </div>
        <div class="card-body" style="padding:0;">
          <table>
            <thead>
              <tr>
                <th>Verbatim Headline, Source, Publication Timestamp &amp; Factual Keyword Tags</th>
                <th>Detected Target</th>
                <th class="text-right">Source Link / Action</th>
              </tr>
            </thead>
            <tbody id="scan-wires-tbody">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
      </section>

    </div>

  </main>

  <script>
    let SCAN_STATE = {
      wireItems: [],
      watchlist: [],
      filterMode: 'ALL',
    };

    function sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    function setStageStatus(stageNum, status) {
      const el = document.getElementById(`stage-${stageNum}`);
      if (!el) return;
      el.className = 'stage-step ' + status;
    }

    async function executeDeepScan() {
      const btn = document.getElementById('btn-rescan');
      btn.disabled = true;
      btn.textContent = '⏳ SCANNING LIVE WIRES & EDGAR...';

      const spinner = document.getElementById('scan-spinner');
      spinner.classList.remove('done');
      const bar = document.getElementById('scan-progress-bar');
      const titleEl = document.getElementById('scan-status-title');
      const subEl = document.getElementById('scan-status-subtitle');
      const resultsContainer = document.getElementById('scan-results-container');

      setStageStatus(1, 'active');
      setStageStatus(2, '');
      setStageStatus(3, '');
      setStageStatus(4, '');
      bar.style.width = '18%';
      titleEl.textContent = 'STAGE 1/4: QUERYING GOOGLE NEWS M&A RSS WIRES (LAST 48 HOURS)...';
      subEl.textContent = 'Scanning hard M&A phrases ("in talks", "advanced talks", "nearing a deal", "take private", "buyout") and excluding earnings noise...';

      // Start the actual backend scan fetch concurrently with visual stage progression
      const scanPromise = fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_live_network: true }),
      }).then(r => r.json());

      await sleep(320);
      setStageStatus(1, 'done');
      setStageStatus(2, 'active');
      bar.style.width = '45%';
      titleEl.textContent = 'STAGE 2/4: ENFORCING <= 4.0H LEAK FRESHNESS GATE & FACTUAL KEYWORD TAGS...';
      subEl.textContent = 'Tagging [TIER-1 SOURCE], [11TH-HOUR KEYWORD], [STOCK-DEAL TRAP], [ALREADY SIGNED 8-K]...';

      await sleep(320);
      setStageStatus(2, 'done');
      setStageStatus(3, 'active');
      bar.style.width = '72%';
      titleEl.textContent = 'STAGE 3/4: QUERYING SEC EDGAR SUBMISSIONS FOR FORM 8-K ITEM 1.01...';
      subEl.textContent = 'Verifying whether formal Definitive Merger Agreements have already been filed on data.sec.gov...';

      await sleep(320);
      setStageStatus(3, 'done');
      setStageStatus(4, 'active');
      bar.style.width = '90%';
      titleEl.textContent = 'STAGE 4/4: FETCHING LIVE YFINANCE EXTENDED-HOURS QUOTES & 10-Q XBRL NET DEBT...';
      subEl.textContent = 'Computing Net-Debt waterfalls on verified Watchlist situations ($U, $HELE, $WEN, $RYTM, $GPN)...';

      const data = await scanPromise;
      setStageStatus(4, 'done');
      bar.style.width = '100%';
      spinner.classList.add('done');

      SCAN_STATE.wireItems = data.wire_items || [];
      SCAN_STATE.watchlist = data.watchlist || [];

      const trigCount = data.actionable_trigger_count || 0;
      const filteredCount = SCAN_STATE.wireItems.filter(w => !w.is_actionable_trigger).length;
      const freshWlCount = SCAN_STATE.watchlist.filter(w => !w.is_stale_leak).length;
      const staleWlCount = SCAN_STATE.watchlist.filter(w => w.is_stale_leak).length;

      titleEl.textContent = `✅ DEEP SCAN COMPLETE — ${SCAN_STATE.wireItems.length} VERIFIED M&A WIRE HITS & ${SCAN_STATE.watchlist.length} WATCHLIST SITUATIONS AUDITED`;
      subEl.textContent = `${trigCount} Fresh (<=4h) Qualified Triggers | ${filteredCount} Filtered/Stale Wire Hits | ${staleWlCount} Watchlist Situations Audited`;

      document.getElementById('kpi-triggers').textContent = trigCount;
      document.getElementById('kpi-filtered-wires').textContent = filteredCount;
      document.getElementById('kpi-watchlist-count').textContent = freshWlCount;
      document.getElementById('kpi-disqualified').textContent = staleWlCount;

      const banner = document.getElementById('zero-trigger-banner');
      const bHead = document.getElementById('banner-headline');
      const bSub = document.getElementById('banner-subtext');
      if (trigCount === 0) {
        banner.style.backgroundColor = 'rgba(245, 158, 11, 0.12)';
        banner.style.borderColor = 'var(--amber)';
        bHead.style.color = '#FBBF24';
        bHead.textContent = '🔎 0 FRESH (<= 4.0H) QUALIFIED TRIGGERS FOUND — SURFACING VERIFIED NOVEMBER 2026 WATCHLIST SITUATIONS & FILTERED RSS WIRES';
        bSub.textContent = 'Zero candidate leaks broke within the last 4.0 hours. Below are the 5 verified November 2026 Watchlist situations ($U, $HELE, $WEN, $RYTM, $GPN) with factual notes, followed by strict M&A RSS wire hits.';
      } else {
        banner.style.backgroundColor = 'rgba(16, 185, 129, 0.14)';
        banner.style.borderColor = 'var(--emerald)';
        bHead.style.color = '#34D399';
        bHead.textContent = `🚨 ${trigCount} FRESH (<= 4.0H) QUALIFIED TIER-1 M&A TRIGGER(S) DETECTED`;
        bSub.textContent = 'Review fresh qualified triggers and verified Watchlist situations below before staging 5:30 PM EST 3-tranche limit orders.';
      }

      renderWatchlistRumors();
      renderScannedWires();
      resultsContainer.style.display = 'flex';

      btn.disabled = false;
      btn.textContent = '🔄 RE-RUN LIVE M&A DEEP SCAN';
    }

    function buildRumorCardHtml(row) {
      const vCls = row.verdict === 'PASS_HOT' ? 'badge-emerald' :
                   row.verdict === 'FAIL_TAKE_UNDER' ? 'badge-crimson' : 'badge-amber';
      const ageBadge = row.freshness_badge || (row.is_stale_leak ? `⏳ STALE LEAK (${row.leak_age_human})` : `🟢 FRESH LEAK (${row.leak_age_human})`);
      const reasons = (row.rejection_reasons && row.rejection_reasons.length)
        ? row.rejection_reasons
        : ['Cleared quantitative spread check; verify remaining Gatekeeper rules.'];

      const netDebtB = (Number(row.net_debt_usd || 0) / 1e9).toFixed(2);
      const isUnpriced = row.rumored_value === null || row.rumored_value === undefined || row.implied_deal_price === null;
      const impliedText = isUnpriced ? 'AWAITING PRICE LEAK' : `$${Number(row.implied_deal_price).toFixed(2)} / sh`;
      const spreadBadgeText = isUnpriced
        ? 'AWAITING_PRICE_LEAK'
        : `${row.verdict} (${row.gross_spread_pct >= 0 ? '+' : ''}${Number(row.gross_spread_pct).toFixed(2)}%)`;
      const calcUrl = isUnpriced
        ? `/?ticker=${encodeURIComponent(row.ticker)}`
        : `/?ticker=${encodeURIComponent(row.ticker)}&mode=${encodeURIComponent(row.input_mode)}&value=${encodeURIComponent(row.rumored_value)}`;
      const cardBorder = row.is_stale_leak ? 'border:1px solid rgba(245,158,11,0.45);' : 'border:1px solid rgba(16,185,129,0.5);';

      return `
        <div class="rumor-card" style="${cardBorder}">
          <div>
            <!-- Stale / Fresh Visual Header Banner -->
            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;margin-bottom:8px;border-radius:4px;background:${row.is_stale_leak ? 'rgba(245,158,11,0.14)' : 'rgba(16,185,129,0.14)'};border:1px solid ${row.is_stale_leak ? 'rgba(245,158,11,0.35)' : 'rgba(16,185,129,0.35)'};">
              <span class="mono" style="font-size:11px;font-weight:700;color:${row.is_stale_leak ? '#FBBF24' : '#34D399'};">
                ${ageBadge}
              </span>
              <span class="mono" style="font-size:10.5px;color:var(--text-secondary);">
                Broke: ${row.leak_timestamp_est || 'Historical'}
              </span>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px;">
              <div>
                <span class="mono" style="font-size:16px;font-weight:700;color:var(--cyan);">$${row.ticker}</span>
                <span style="font-weight:600;color:var(--text-primary);margin-left:6px;">${row.company_name}</span>
                <div class="mono" style="font-size:11px;color:var(--text-secondary);margin-top:2px;">
                  Buyer: ${row.buyer_type} | Reported Input: ${isUnpriced ? 'UNPRICED' : row.input_mode + ' = ' + row.rumored_value}
                </div>
              </div>
              <span class="badge ${vCls}">${spreadBadgeText}</span>
            </div>

            <div style="font-size:12px;color:var(--text-primary);margin-bottom:8px;padding:6px 8px;background:rgba(15,23,42,0.75);border-left:2px solid var(--cyan);border-radius:3px;">
              ${row.gate_notes || row.rumor_headline}
            </div>

            <div class="mono" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:var(--bg-canvas);padding:8px 10px;border-radius:4px;border:1px solid var(--border-hairline);font-size:11.5px;">
              <div>
                <span style="color:var(--text-muted);font-size:10px;display:block;">LIVE PRICE (REG / AH)</span>
                <strong>$${row.regular_market_price.toFixed(2)} / $${row.extended_hours_price.toFixed(2)}</strong>
              </div>
              <div>
                <span style="color:var(--text-muted);font-size:10px;display:block;">IMPLIED CASH BUYOUT</span>
                <strong style="color:${isUnpriced ? 'var(--amber)' : 'var(--emerald)'};">${impliedText}</strong>
              </div>
              <div>
                <span style="color:var(--text-muted);font-size:10px;display:block;">10-Q NET DEBT</span>
                <strong style="color:var(--amber);">$${netDebtB}B</strong>
              </div>
              <div>
                <span style="color:var(--text-muted);font-size:10px;display:block;">SEC EDGAR 8-K STATUS</span>
                <strong>${row.edgar_8k?.has_recent_item_1_01 ? '🚨 8-K 1.01 FILED' : '🟢 PRE-8-K OPEN'}</strong>
              </div>
            </div>

            <div class="reason-box">
              <div style="font-weight:700;color:#F87171;margin-bottom:4px;">
                GATEKEEPER AUDIT STATUS:
              </div>
              ${reasons.map(r => `<div>&bull; ${r}</div>`).join('')}
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:8px;border-top:1px solid var(--border-hairline);">
            <span class="mono" style="font-size:11px;color:var(--text-muted);">
              ${row.edgar_8k?.status_badge || ''}
            </span>
            <a href="${calcUrl}" class="btn btn-sm ${row.is_stale_leak ? '' : 'btn-primary'}">
              ${isUnpriced ? `Open $${row.ticker} in Calculator →` : `Inspect $${row.ticker} in Calculator →`}
            </a>
          </div>
        </div>
      `;
    }

    function renderWatchlistRumors() {
      const freshContainer = document.getElementById('fresh-watchlist-rumors-grid');
      const staleGrid = document.getElementById('watchlist-rumors-grid');
      const rows = SCAN_STATE.watchlist || [];
      const freshRows = rows.filter(r => !r.is_stale_leak);
      const staleRows = rows.filter(r => r.is_stale_leak);

      document.getElementById('scan-fresh-wl-badge').textContent = `${freshRows.length} FRESH (<=4H)`;
      document.getElementById('scan-stale-wl-badge').textContent = `${staleRows.length} STALE (>4H)`;

      if (freshRows.length === 0) {
        freshContainer.innerHTML = `
          <div class="mono" style="padding:10px 14px;color:var(--text-secondary);font-size:12px;">
            🔎 <strong>0 Fresh Watchlist Leaks (&lt;= 4.0 hours old)</strong> currently active. Verified November 2026 Watchlist situations (<strong>$U, $HELE, $WEN, $RYTM, $GPN</strong>) are separated into Section 1B below as <strong>⏳ Stale Rumors (&gt; 4.0h old)</strong>.
          </div>
        `;
      } else {
        freshContainer.innerHTML = `<div class="rumor-grid">${freshRows.map(buildRumorCardHtml).join('')}</div>`;
      }

      staleGrid.innerHTML = staleRows.map(buildRumorCardHtml).join('');
    }

    function setScanWireFilter(mode) {
      SCAN_STATE.filterMode = mode;
      renderScannedWires();
    }

    function renderScannedWires() {
      const tbody = document.getElementById('scan-wires-tbody');
      let items = SCAN_STATE.wireItems || [];
      if (SCAN_STATE.filterMode === 'FRESH') {
        items = items.filter(i => !i.is_stale_leak);
      } else if (SCAN_STATE.filterMode === 'STALE') {
        items = items.filter(i => i.is_stale_leak);
      } else if (SCAN_STATE.filterMode === 'TIER1') {
        items = items.filter(i => i.is_tier1);
      } else if (SCAN_STATE.filterMode === 'REJECTED') {
        items = items.filter(i => !i.is_actionable_trigger);
      }

      if (!items.length) {
        tbody.innerHTML = `
          <tr>
            <td colspan="3" class="mono" style="text-align:center;padding:24px;color:var(--text-secondary);">
              No wire items matched the selected filter (${SCAN_STATE.filterMode}). Click "All Scanned Rumors" to view all separated items.
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = items.map(item => {
        const tagList = item.factual_keyword_tags && item.factual_keyword_tags.length
          ? [item.freshness_badge, ...item.factual_keyword_tags]
          : (item.tags || []);
        const badges = tagList.filter(Boolean).map(tag => {
          let cls = 'badge-neutral';
          if (tag.includes('FRESH LEAK') || tag.includes('TIER-1')) cls = 'badge-emerald';
          else if (tag.includes('STALE LEAK') || tag.includes('11TH-HOUR')) cls = 'badge-amber';
          else if (tag.includes('TRAP') || tag.includes('ALREADY') || tag.includes('8-K')) cls = 'badge-crimson';
          return `<span class="badge ${cls}">${tag}</span>`;
        }).join('');

        const hasExplicitVal = item.detected_ticker && item.suggested_input_mode && item.suggested_value !== null && item.suggested_value !== undefined;
        const calcUrl = hasExplicitVal
          ? `/?ticker=${encodeURIComponent(item.detected_ticker)}&mode=${encodeURIComponent(item.suggested_input_mode)}&value=${encodeURIComponent(item.suggested_value)}&clip=${Math.round(380000 * (item.recommended_clip_multiplier || 1))}`
          : item.link;

        const rowStyle = item.is_stale_leak
          ? 'border-left:3px solid var(--amber);background:rgba(245,158,11,0.03);'
          : 'border-left:3px solid var(--emerald);';

        return `
          <tr style="${rowStyle}">
            <td>
              <div style="font-weight:600;font-size:13.5px;color:var(--text-primary);margin-bottom:5px;">
                <a href="${item.link}" target="_blank" rel="noopener" style="color:var(--text-primary);text-decoration:underline;">
                  ${item.title}
                </a>
              </div>
              <div style="margin-bottom:4px;">${badges}</div>
              <div class="mono" style="font-size:11px;color:var(--text-muted);">
                Source: <strong style="color:var(--text-secondary);">${item.source}</strong> &bull;
                Published: ${item.published_at} (${item.day_of_week}) &bull;
                <strong style="color:${item.is_stale_leak ? '#FBBF24' : '#34D399'};">Age: ${item.leak_age_human || 'N/A'}</strong>
              </div>
            </td>
            <td class="mono" style="font-size:12px;white-space:nowrap;">
              <strong style="color:var(--cyan);font-size:14px;">${item.detected_ticker ? '$' + item.detected_ticker : '—'}</strong><br/>
              <span style="color:var(--text-secondary);">${hasExplicitVal ? item.suggested_input_mode + ': ' + item.suggested_value : 'No explicit $ price in headline'}</span>
            </td>
            <td class="text-right" style="white-space:nowrap;">
              <a href="${item.link}" target="_blank" rel="noopener" class="btn btn-sm">
                Open Source Article &nearr;
              </a>
              ${hasExplicitVal ? `<a href="${calcUrl}" class="btn btn-sm btn-primary" style="margin-left:4px;">Load in Calculator &rarr;</a>` : ''}
            </td>
          </tr>
        `;
      }).join('');
    }

    window.addEventListener('DOMContentLoaded', executeDeepScan);
  </script>
</body>
</html>
"""


@app.get("/scan", response_class=HTMLResponse)
def get_scan_page() -> HTMLResponse:
    """Serve the dedicated Live M&A Wire & EDGAR 8-K Deep Scanner page with loading progress & filtered-out reasons."""
    return HTMLResponse(content=SCAN_PAGE_HTML, status_code=200)


if __name__ == "__main__":
    host = os.getenv("ARB_CANNON_HOST", "127.0.0.1")
    port = int(os.getenv("ARB_CANNON_PORT", "8000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
