"""
FastAPI Endpoint Integration Tests (tests/test_app_endpoints.py)

Verifies:
  - GET /
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


def test_get_root_terminal_html() -> None:
    """Verify GET / returns HTTP 200 and renders the institutional trading terminal UI with <=4h Stale Leak Separation."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "M&amp;A LEAK ARBITRAGE COMMAND CENTER" in html
    assert "SCAN M&amp;A WIRES &amp; REFRESH EXTENDED-HOURS QUOTES" in html
    assert "FIRE 5:00 PM EMAIL REPORT NOW" in html
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
