"""
FastAPI Endpoint Integration Tests (tests/test_app_endpoints.py)

Verifies:
  - GET / (Overnight Scanner), GET /biotech-rumors, GET /research, GET /backtest, and GET /terminal
  - GET /api/backtest
  - GET /api/scanner
  - GET /api/price-history
  - GET /api/dashboard
  - POST /api/calculate (EV_BILLIONS, PER_SHARE, Take-Under Trap, Live $5.97 BMBL price)
  - POST /api/scan
  - POST /api/watchlist (add & remove)
  - POST /api/fire-email
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_get_root_scanner_html() -> None:
    """Verify GET / serves the Overnight Scanner wired to /api/scanner and /api/price-history."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Biotech M&amp;A Overnight Scanner" in html
    assert "/api/scanner" in html
    assert "/api/price-history" in html
    assert "Overnight Position (Simulation)" in html
    assert "Research &amp; Evidence" in html


def test_get_api_scanner() -> None:
    """Verify GET /api/scanner ranks the RYTM biopharma setup first with its modeled scenarios."""
    resp = client.get("/api/scanner?use_live_network=false")
    assert resp.status_code == 200
    data = resp.json()
    kpis = data["kpis"]
    assert kpis["active_candidates"] == 5
    assert kpis["actionable_setups"] == 1
    assert kpis["actionable_biotech"] == 1
    assert kpis["backtest_win_rate_pct"] == 84.2
    assert kpis["avg_overnight_move_pct"] == 5.8

    top = data["opportunities"][0]
    assert top["ticker"] == "RYTM"
    assert top["sector"] == "Biotech"
    assert top["status_key"] == "open"
    assert top["decision_key"] == "go"
    assert top["decision_label"] == "Actionable"
    assert "Passes all 6 biotech checks" in top["decision_text"]
    assert "$114.08 max buy price" in top["decision_text"]
    signal = top["biotech_signal"]
    assert signal["is_actionable"] is True
    assert signal["label"] == "Actionable biotech M&A rumor"
    assert signal["gates_passed"] == 6
    assert signal["gates_total"] == 6
    assert signal["max_entry_price"] == 114.08
    assert signal["buyer"].startswith("AstraZeneca")
    assert len(signal["checks"]) == 6
    assert all(c["passed"] and c["label"] and c["detail"] for c in signal["checks"])
    assert signal["checks"][0]["label"] == "Named big-pharma buyer with a specific price"
    assert top["base_offer"] == 124.0
    assert top["higher_offer"] == 134.0
    assert top["floor_price"] == 92.0
    assert top["upside_low_pct"] == 9.73
    assert top["upside_high_pct"] == 18.58
    assert top["downside_pct"] == -18.58
    assert top["ev_pct"] == 0.31
    assert top["rumored_window"] == "Nov 16 – Nov 23"
    assert top["analysis_url"].startswith("/terminal?ticker=RYTM")

    gpn = next(o for o in data["opportunities"] if o["ticker"] == "GPN")
    assert gpn["base_offer"] is None
    assert gpn["ev_pct"] is None
    assert gpn["decision_label"] == "Wait"
    assert gpn["biotech_signal"] is None
    assert len(data["wire_items"]) >= 4
    assert len(data["performance"]["annual_pnl_table"]) == 3


def test_get_api_price_history() -> None:
    """Verify GET /api/price-history validates the range and never fabricates bars offline."""
    resp = client.get("/api/price-history?ticker=rytm&range=5D&use_live_network=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RYTM"
    assert data["range"] == "5D"
    assert data["points"] == []
    assert data["source"] == "unavailable"

    bad = client.get("/api/price-history?ticker=RYTM&range=10Y&use_live_network=false")
    assert bad.status_code == 400


def test_get_research_and_backtest_pages() -> None:
    """Verify /research and /backtest serve the light shell wired to their data endpoints."""
    research = client.get("/research")
    assert research.status_code == 200
    assert "M&amp;A Wire &amp; EDGAR Research" in research.text
    assert "/api/scan" in research.text
    assert 'class="nav-item active" href="/research"' in research.text
    assert "const STATUS_TEXT" in research.text

    backtest = client.get("/backtest")
    assert backtest.status_code == 200
    assert "Strategy Backtests" in backtest.text
    assert "/api/backtest" in backtest.text
    assert 'class="nav-item active" href="/backtest"' in backtest.text

    scanner = client.get("/")
    assert 'href="/research"' in scanner.text
    assert 'href="/backtest"' in scanner.text


def test_get_biotech_rumors_page() -> None:
    """Verify /biotech-rumors serves the light shell wired to the biopharma endpoints and is linked from every sidebar."""
    resp = client.get("/biotech-rumors")
    assert resp.status_code == 200
    html = resp.text
    assert "Biotech M&amp;A Rumors" in html
    assert "/api/biopharma-backtest" in html
    assert "/api/biopharma-evaluate" in html
    assert "/api/scanner" in html
    assert 'class="nav-item active" href="/biotech-rumors"' in html
    assert 'href="/biotech"' in html

    for path in ("/", "/research", "/backtest"):
        page = client.get(path)
        assert page.status_code == 200
        assert 'class="nav-item" href="/biotech-rumors"' in page.text, path


def test_get_api_backtest() -> None:
    """Verify GET /api/backtest bundles the biopharma backtest with the PE benchmarks and 8 gates."""
    resp = client.get("/api/backtest")
    assert resp.status_code == 200
    data = resp.json()
    bio = data["biopharma"]
    assert len(bio["historical_events"]) == 25
    assert bio["filtered_6_gate_metrics"]["win_rate_pct"] == 55.6
    assert len(bio["purged_untradable_weekend_gaps"]) == 9
    assert len(bio["gatekeeper_rules"]) == 6
    assert data["pe"]["benchmarks"]["filtered_win_rate_pct"] == 84.2
    assert len(data["pe"]["gatekeeper_rules"]) == 8
    assert "alpha_window" in data["pe"]["thesis"]


def test_get_terminal_html() -> None:
    """Verify GET /terminal returns HTTP 200 and renders the institutional trading terminal UI with <=4h Stale Leak Separation."""
    resp = client.get("/terminal")
    assert resp.status_code == 200
    html = resp.text
    assert "M&amp;A LEAK ARBITRAGE COMMAND CENTER" in html
    assert "SCAN M&amp;A WIRES &amp; REFRESH EXTENDED-HOURS QUOTES" in html
    assert "BIOTECH M&amp;A RUMOR COMMAND CENTER" in html
    assert "btn-biotech-mode-toggle" in html
    assert "toggleBiotechCommandCenter()" in html
    assert "FIRE 5:00 PM EMAIL REPORT NOW" in html

    bio_resp = client.get("/biotech")
    assert bio_resp.status_code == 200
    assert "btn-biotech-mode-toggle" in bio_resp.text
    assert "Stale Benchmark: BMBL $1.3B EV" in html
    assert "Stale Benchmark: WEN $8.00/sh" in html
    assert "Stale Benchmark: U $25B EV" in html
    assert "Stale Benchmark: GPN $24B EV" in html
    assert "SEPARATED STALE / EXPIRED WIRE RUMORS" in html
    assert "SEPARATED STALE RUMORS &amp; HISTORICAL BENCHMARKS" in html
    assert "calc-freshness-banner" in html
    assert "84.2%" in html
    assert "+$313,656" in html
    assert "+$332,649" in html
    assert "+$191,627" in html


def test_get_api_dashboard() -> None:
    """Verify GET /api/dashboard returns full telemetry, benchmarks, gatekeeper rules, wires, and watchlist."""
    resp = client.get("/api/dashboard?use_live_network=false")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["telemetry"]["dry_powder_usd"] == 400000
    assert payload["telemetry"]["default_clip_usd"] == 380000
    assert payload["benchmarks"]["filtered_win_rate_pct"] == 84.2
    assert len(payload["gatekeeper_rules"]) == 8
    assert len(payload["wire_items"]) >= 4
    assert len(payload["watchlist"]) >= 4


def test_post_api_calculate() -> None:
    """Verify POST /api/calculate computes EV_BILLIONS, PER_SHARE, and Take-Under Trap states."""
    # 1. BMBL $1.3B EV at current $5.97 price (Post-8K WARN_TIGHT)
    resp_bmbl = client.post(
        "/api/calculate",
        json={
            "ticker": "BMBL",
            "input_mode": "EV_BILLIONS",
            "value": 1.30,
            "clip_usd": 380000,
            "coc_dilution_pct": 1.5,
            "use_live_network": False,
        },
    )
    assert resp_bmbl.status_code == 200
    data_bmbl = resp_bmbl.json()
    assert data_bmbl["ticker"] == "BMBL"
    assert data_bmbl["market_and_spread"]["extended_hours_price"] == 5.97
    assert data_bmbl["market_and_spread"]["implied_cash_buyout_per_share"] == 6.05
    assert data_bmbl["market_and_spread"]["verdict"] == "WARN_TIGHT"
    assert data_bmbl["market_and_spread"]["is_stale_leak"] is True
    assert len(data_bmbl["tranche_ladder"]) == 3

    # 2. Simulated pre-8K fresh leak spread (PASS_HOT when AH price is 5.65 and simulate_fresh_leak=True)
    resp_sim = client.post(
        "/api/calculate",
        json={
            "ticker": "BMBL",
            "input_mode": "EV_BILLIONS",
            "value": 1.30,
            "clip_usd": 380000,
            "coc_dilution_pct": 1.5,
            "current_price_override": 5.65,
            "use_live_network": False,
            "simulate_fresh_leak": True,
        },
    )
    assert resp_sim.status_code == 200
    assert resp_sim.json()["market_and_spread"]["verdict"] == "PASS_HOT"
    assert resp_sim.json()["market_and_spread"]["is_stale_leak"] is False

    # 3. U $25B EV Take-Under Trap
    resp_u = client.post(
        "/api/calculate",
        json={
            "ticker": "U",
            "input_mode": "EV_BILLIONS",
            "value": 25.0,
            "clip_usd": 380000,
            "coc_dilution_pct": 1.5,
            "use_live_network": False,
        },
    )
    assert resp_u.status_code == 200
    data_u = resp_u.json()
    assert data_u["market_and_spread"]["is_take_under_trap"] is True
    assert data_u["market_and_spread"]["verdict"] == "FAIL_TAKE_UNDER"


def test_get_scan_page_and_post_api_scan() -> None:
    """Verify GET /scan renders loading stages & POST /api/scan returns wire_items and watchlist with rejection_reasons."""
    page_resp = client.get("/scan")
    assert page_resp.status_code == 200
    assert "EXECUTING LIVE M&amp;A WIRE &amp; SEC EDGAR 8-K DEEP SCAN" in page_resp.text
    assert "STAGE 1 // RSS WIRE SWEEP" in page_resp.text
    assert "GATEKEEPER AUDIT STATUS:" in page_resp.text
    # Ensure zero synthetic pre-deal pipeline text appears in /scan
    assert "COMING SOON" not in page_resp.text
    assert "8-GATE PROBABILITY" not in page_resp.text

    resp = client.post("/api/scan", json={"use_live_network": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["actionable_trigger_count"] == 0
    assert "coming_soon_rumors" not in data
    assert len(data["wire_items"]) >= 4
    assert [w["ticker"] for w in data["watchlist"]] == ["U", "HELE", "WEN", "RYTM", "GPN"]
    for item in data["wire_items"]:
        if not item["is_actionable_trigger"]:
            assert len(item["rejection_reasons"]) >= 1
    for wl in data["watchlist"]:
        assert len(wl["rejection_reasons"]) >= 1


def test_post_api_watchlist_add_and_remove() -> None:
    """Verify POST /api/watchlist adds and removes a target ticker cleanly."""
    resp_add = client.post(
        "/api/watchlist",
        json={
            "action": "add",
            "ticker": "ACME",
            "input_mode": "EV_BILLIONS",
            "rumored_value": 13.5,
            "rumor_headline": "Test buyout talks for Acme Corp",
            "use_live_network": False,
        },
    )
    assert resp_add.status_code == 200
    wl_after_add = resp_add.json()["watchlist"]
    assert any(item["ticker"] == "ACME" for item in wl_after_add)

    resp_rem = client.post(
        "/api/watchlist",
        json={"action": "remove", "ticker": "ACME", "use_live_network": False},
    )
    assert resp_rem.status_code == 200
    wl_after_rem = resp_rem.json()["watchlist"]
    assert not any(item["ticker"] == "ACME" for item in wl_after_rem)


def test_post_api_fire_email() -> None:
    """Verify POST /api/fire-email runs the 5:00 PM report generator and returns HTML preview."""
    resp = client.post(
        "/api/fire-email", json={"dry_run": True, "use_live_network": False}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "Arb Cannon 5PM Sweep" in data["subject"]
    assert "<html" in data["html_content"].lower()
    assert "GATE_1_PLUMBING" in data["html_content"]


def test_biopharma_bolt_on_endpoints() -> None:
    """Verify GET /api/biopharma-backtest, POST /api/biopharma-evaluate, and BIOPHARMA_BOLT_ON calculator mode."""
    bt_resp = client.get("/api/biopharma-backtest")
    assert bt_resp.status_code == 200
    bt_data = bt_resp.json()
    assert bt_data["unfiltered_metrics"]["total_events"] == 25
    assert bt_data["unfiltered_metrics"]["win_rate_pct"] == 36.0
    assert bt_data["unfiltered_metrics"]["median_return_per_trade_pct"] == -11.20
    assert bt_data["broad_commercial_metrics"]["total_events"] == 13
    assert bt_data["broad_commercial_metrics"]["win_rate_pct"] == 38.5
    assert bt_data["broad_commercial_metrics"]["median_return_per_trade_pct"] == -11.64
    assert bt_data["filtered_6_gate_metrics"]["qualified_events"] == 9
    assert bt_data["filtered_6_gate_metrics"]["wins"] == 5
    assert bt_data["filtered_6_gate_metrics"]["losses_or_walkaways"] == 4
    assert bt_data["filtered_6_gate_metrics"]["win_rate_pct"] == 55.6
    assert bt_data["filtered_6_gate_metrics"]["winner_median_spread_pct"] == 19.86
    assert bt_data["filtered_6_gate_metrics"]["expected_hold_clock"] == "1–57 trading days (Bimodal: 1–11d fast | 53–57d contested)"
    assert len(bt_data["purged_untradable_weekend_gaps"]) == 9
    assert bt_data["live_rytm_audit"]["ticker"] == "RYTM"
    assert bt_data["live_rytm_audit"]["hard_ceiling_92pct"] == 114.08
    assert bt_data["live_rytm_audit"]["positive_ev_87pct_ceiling"] == 107.88
    assert bt_data["live_rytm_audit"]["all_biopharma_gates_passed"] is True
    assert bt_data["live_rytm_audit"]["live_100k_lot_scenarios"]["shares"] == 885
    assert bt_data["live_rytm_audit"]["live_100k_lot_scenarios"]["probability_weighted_ev_usd"] == 311.52
    assert len(bt_data["live_rytm_audit"]["deal_timeline_windows"]) == 3

    eval_resp = client.post(
        "/api/biopharma-evaluate",
        json={
            "ticker": "RYTM",
            "current_price": 113.00,
            "unaffected_price": 86.44,
            "walk_away_floor_price": 92.00,
            "base_cash_bid_per_share": 124.00,
            "sweetened_ceiling_per_share": 134.00,
            "deal_ev_billions": 10.0,
            "fda_approved_commercial_anchor": True,
            "clip_usd": 190000.0,
            "live_position_usd": 100000.0,
            "live_position_entry_price": 113.00,
        },
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["verdict"] == "BIO_PASS_HOT"
    assert eval_data["passed_gates_count"] == 6
    assert eval_data["hard_ceiling_92pct"] == 114.08
    assert eval_data["live_100k_lot_scenarios"]["shares"] == 885
    assert [t["limit_price"] for t in eval_data["tranche_ladder"]] == [
        112.73,
        110.22,
        107.83,
    ]

    calc_resp = client.post(
        "/api/calculate",
        json={
            "ticker": "RYTM",
            "input_mode": "PER_SHARE",
            "value": 124.0,
            "clip_usd": 190000.0,
            "coc_dilution_pct": 1.5,
            "use_live_network": False,
            "strategy_mode": "BIOPHARMA_BOLT_ON",
            "sweetened_ceiling_per_share": 134.0,
        },
    )
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert calc_data["strategy_mode"] == "BIOPHARMA_BOLT_ON"
    assert [t["limit_price"] for t in calc_data["tranche_ladder"]] == [
        112.73,
        110.22,
        107.83,
    ]
    assert calc_data["biopharma_bolt_on_audit"]["all_biopharma_gates_passed"] is True

