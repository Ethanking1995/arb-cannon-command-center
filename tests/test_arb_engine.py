"""
Comprehensive Unit Tests for arb_engine.py and nightly_mailer.py (tests/test_arb_engine.py)
"""

from __future__ import annotations

import math
from pathlib import Path

from arb_engine import (
    EST_TZ,
    GATEKEEPER_RULES,
    STRATEGY_BENCHMARKS,
    _extract_ticker_and_deal_value,
    calculate_deal_mechanics,
    calculate_hft_cooldown,
    check_edgar_8k,
    classify_headline,
    compute_leak_freshness,
    evaluate_watchlist,
    fetch_extended_hours_quote,
    load_config,
    passes_strict_ma_headline_filter,
    scan_ma_wires,
)
from nightly_mailer import build_subject_line, generate_and_send_nightly_report


def test_strategy_benchmarks_and_gatekeeper_constants() -> None:
    """Verify hardcoded 3-year historical backtest benchmarks and 8-Point Gatekeeper rules."""
    assert STRATEGY_BENCHMARKS["total_leak_events"] == 46
    assert STRATEGY_BENCHMARKS["filtered_win_rate_pct"] == 84.2
    assert STRATEGY_BENCHMARKS["sun_mon_tue_named_buyer_win_rate_pct"] == 93.1
    assert STRATEGY_BENCHMARKS["avg_net_spread_captured_pct"] == 5.8
    assert STRATEGY_BENCHMARKS["target_capital_pool_usd"] == 400000
    assert STRATEGY_BENCHMARKS["historical_avg_clip_usd"] == 383000

    pnl_by_year = {
        row["year"]: row for row in STRATEGY_BENCHMARKS["annual_pnl_table"]
    }
    assert pnl_by_year["2024"]["filtered_strategy_usd"] == 313656
    assert pnl_by_year["2024"]["unfiltered_all_leaks_usd"] == 71590
    assert pnl_by_year["2024"]["idle_sgov_usd"] == 26000

    assert pnl_by_year["2025"]["filtered_strategy_usd"] == 332649
    assert pnl_by_year["2025"]["unfiltered_all_leaks_usd"] == 68564
    assert pnl_by_year["2025"]["idle_sgov_usd"] == 22000

    assert pnl_by_year["2026 YTD"]["filtered_strategy_usd"] == 191627
    assert pnl_by_year["2026 YTD"]["unfiltered_all_leaks_usd"] == 45003
    assert pnl_by_year["2026 YTD"]["idle_sgov_usd"] == 15721

    assert len(GATEKEEPER_RULES) == 8
    expected_ids = [
        "GATE_1_PLUMBING",
        "GATE_2_TIER1_SOURCE",
        "GATE_3_TIMING_AND_PRICE",
        "GATE_4_ALL_CASH",
        "GATE_5_CLEAN_BUYER",
        "GATE_6_NET_DEBT_AUDIT",
        "GATE_7_LIQUIDITY_AND_TRANCHES",
        "GATE_8_EXIT_PROTOCOL",
    ]
    assert [g["id"] for g in GATEKEEPER_RULES] == expected_ids


def test_ev_to_equity_net_debt_waterfall_and_coc_dilution() -> None:
    """
    Test GATE_6_NET_DEBT_AUDIT exact math:
      Net Debt = (LT Debt + ST Debt + Preferred) - Cash
      Implied Equity Value = Rumored EV - Net Debt
      Adjusted Diluted Shares = Diluted Shares * (1 + CoC Buffer)
      Implied Cash Buyout Per Share = Implied Equity Value / Adjusted Diluted Shares
    """
    custom_bs = {
        "long_term_debt_usd": 800_000_000.0,
        "short_term_debt_usd": 150_000_000.0,
        "preferred_stock_usd": 50_000_000.0,
        "total_cash_usd": 300_000_000.0,
        "diluted_shares": 100_000_000.0,
    }
    res = calculate_deal_mechanics(
        ticker="TEST",
        input_mode="EV_BILLIONS",
        value=2.7,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        current_price_override=18.20,
        balance_sheet_override=custom_bs,
        use_live_network=False,
    )
    wf = res["balance_sheet_waterfall"]
    ms = res["market_and_spread"]

    assert wf["total_debt_and_preferred_usd"] == 1_000_000_000.0
    assert wf["net_debt_usd"] == 700_000_000.0
    assert wf["implied_equity_value_usd"] == 2_000_000_000.0
    assert wf["adjusted_diluted_shares"] == 101_500_000.0

    expected_per_share = 2_000_000_000.0 / 101_500_000.0
    assert math.isclose(
        ms["implied_cash_buyout_per_share_exact"], expected_per_share, rel_tol=1e-9
    )
    assert ms["verdict"] == "PASS_HOT"
    assert ms["is_take_under_trap"] is False


def test_bmbl_and_wen_live_post_8k_and_price_verification() -> None:
    """
    Verify BMBL uses actual $5.97 price (+1.34% tight post-8-K spread, WARN_TIGHT & 8-K Item 1.01 flagged)
    and WEN at $8.16 vs $8.00/sh is flagged as FAIL_TAKE_UNDER & 8-K Item 1.01 filed.
    """
    bmbl = calculate_deal_mechanics(
        ticker="BMBL",
        input_mode="EV_BILLIONS",
        value=1.30,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
    )
    assert bmbl["market_and_spread"]["regular_market_price"] == 5.97
    assert bmbl["market_and_spread"]["extended_hours_price"] == 5.97
    assert bmbl["market_and_spread"]["implied_cash_buyout_per_share"] == 6.05
    assert bmbl["market_and_spread"]["gross_spread_pct"] == 1.34
    assert bmbl["market_and_spread"]["has_recent_8k_item_1_01"] is True
    assert bmbl["market_and_spread"]["verdict"] == "WARN_TIGHT"

    wen = calculate_deal_mechanics(
        ticker="WEN",
        input_mode="PER_SHARE",
        value=8.00,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
    )
    assert wen["market_and_spread"]["regular_market_price"] == 8.15
    assert wen["market_and_spread"]["implied_cash_buyout_per_share"] == 8.00
    assert wen["market_and_spread"]["is_take_under_trap"] is True
    assert wen["market_and_spread"]["has_recent_8k_item_1_01"] is True
    assert wen["market_and_spread"]["verdict"] == "FAIL_TAKE_UNDER"


def test_take_under_trap_detection() -> None:
    """
    Verify automatic detection of a 'Take-Under Trap' (FAIL_TAKE_UNDER) when
    Implied Per-Share Price <= Current Extended-Hours Market Price.
    """
    # 1. Unity ($U) $25B EV Take-Under Test preset ($50.09/sh implied vs $51.45 AH price)
    u_res = calculate_deal_mechanics(
        ticker="U",
        input_mode="EV_BILLIONS",
        value=25.0,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
    )
    assert (
        u_res["market_and_spread"]["implied_cash_buyout_per_share"]
        <= u_res["market_and_spread"]["extended_hours_price"]
    )
    assert u_res["market_and_spread"]["is_take_under_trap"] is True
    assert u_res["market_and_spread"]["verdict"] == "FAIL_TAKE_UNDER"

    # 2. Global Payments ($GPN) $24B EV Test preset ($16.34B net debt haircut)
    gpn_res = calculate_deal_mechanics(
        ticker="GPN",
        input_mode="EV_BILLIONS",
        value=24.0,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
    )
    assert gpn_res["market_and_spread"]["is_take_under_trap"] is True
    assert gpn_res["market_and_spread"]["verdict"] == "FAIL_TAKE_UNDER"

    # 3. Exact equality boundary condition (P_deal == P_market -> FAIL_TAKE_UNDER)
    eq_res = calculate_deal_mechanics(
        ticker="WEN",
        input_mode="PER_SHARE",
        value=8.00,
        current_price_override=8.00,
        use_live_network=False,
    )
    assert eq_res["market_and_spread"]["is_take_under_trap"] is True
    assert eq_res["market_and_spread"]["verdict"] == "FAIL_TAKE_UNDER"


def test_three_tranche_limit_ladder_exact_math() -> None:
    """
    Verify GATE_7 3-Tranche Limit Order Ladder exact math:
      - Tranche 1: 40% of $380,000 = $152,000 | 5.5% discount -> P_deal / 1.055 | floor(152000 / L1)
      - Tranche 2: 35% of $380,000 = $133,000 | 6.5% discount -> P_deal / 1.065 | floor(133000 / L2)
      - Tranche 3: 25% of $380,000 = $95,000  | 8.0% discount -> P_deal / 1.080 | floor(95000 / L3)
    """
    p_deal = 10.00
    clip = 380000.0
    res = calculate_deal_mechanics(
        ticker="WEN",
        input_mode="PER_SHARE",
        value=p_deal,
        clip_usd=clip,
        current_price_override=9.25,
        use_live_network=False,
    )
    tranches = res["tranche_ladder"]
    assert len(tranches) == 3

    t1, t2, t3 = tranches[0], tranches[1], tranches[2]

    assert t1["allocation_usd"] == 152000.0
    assert t2["allocation_usd"] == 133000.0
    assert t3["allocation_usd"] == 95000.0

    l1_exact = p_deal / 1.055
    l2_exact = p_deal / 1.065
    l3_exact = p_deal / 1.080

    assert math.isclose(t1["limit_price_exact"], l1_exact, rel_tol=1e-9)
    assert math.isclose(t2["limit_price_exact"], l2_exact, rel_tol=1e-9)
    assert math.isclose(t3["limit_price_exact"], l3_exact, rel_tol=1e-9)

    assert t1["shares"] == math.floor(152000.0 / l1_exact)
    assert t2["shares"] == math.floor(133000.0 / l2_exact)
    assert t3["shares"] == math.floor(95000.0 / l3_exact)


def test_ira_vs_nyc_taxable_pnl_calculation() -> None:
    """
    Verify Dual Tax-Regime P&L Summary:
      - IRA 0% Tax captures 100% of gross profit
      - NYC Taxable (54.5% short-term marginal rate) retains 45.5% of gross profit
    """
    res = calculate_deal_mechanics(
        ticker="BMBL",
        input_mode="EV_BILLIONS",
        value=1.30,
        clip_usd=380000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
    )
    tax = res["tax_regime_pnl"]
    tranches = res["tranche_ladder"]

    p_deal = res["market_and_spread"]["implied_cash_buyout_per_share_exact"]
    expected_gross = sum(
        t["shares"] * (p_deal - t["limit_price_exact"]) for t in tranches
    )

    assert math.isclose(
        tax["ira_tax_free_net_profit_usd"], round(expected_gross, 2), abs_tol=0.05
    )
    assert math.isclose(
        tax["nyc_taxable_net_profit_usd"],
        round(expected_gross * (1.0 - 0.545), 2),
        abs_tol=0.05,
    )
    assert math.isclose(
        tax["nyc_tax_drag_usd"],
        round(expected_gross * 0.545, 2),
        abs_tol=0.05,
    )
    assert "SGOV" in tax["tax_fungibility_instruction"]


def test_rss_headline_classification_tags_and_8k_disqualification() -> None:
    """
    Test RSS headline classification for:
      - 🟢 TIER-1 SOURCE
      - 🔥 11TH-HOUR TRIGGER
      - 🚨 STOCK-DEAL / ANTITRUST TRAP
      - ⚠️ ALREADY ANNOUNCED (LATE)
      - 📅 DAY-OF-WEEK QUALITY (Mon/Tue 100% clip vs Fri 50% clip)
      - Automatic 8-K Item 1.01 disqualification for BMBL and WEN
    """
    # 1. Actionable Monday Tier-1 + 11th-Hour All-Cash Leak on a fresh pre-8-K target (ACME)
    h1 = classify_headline(
        title="Exclusive: Bain Capital in advanced talks to take AcmeSoftware (ACME) private for $65.00 per share in cash as soon as Monday",
        source="Wall Street Journal",
        pub_date="Mon, 09 Nov 2026 16:20:00 -0500",
        enforce_edgar_8k_check=True,
    )
    assert h1["is_tier1"] is True
    assert h1["is_11th_hour"] is True
    assert h1["is_stock_or_antitrust_trap"] is False
    assert h1["is_already_announced"] is False
    assert h1["is_actionable_trigger"] is True
    assert "🟢 TIER-1 SOURCE" in h1["tags"]
    assert "🔥 11TH-HOUR TRIGGER" in h1["tags"]
    assert "[TIER-1 SOURCE]" in h1["factual_keyword_tags"]
    assert "[11TH-HOUR KEYWORD]" in h1["factual_keyword_tags"]
    assert h1["day_quality_tag"] == "🟢 MON/TUE BOARD WINDOW (100% CLIP)"
    assert h1["recommended_clip_multiplier"] == 1.0

    # 2. BMBL / WEN must NOT be flagged as actionable triggers when enforce_edgar_8k_check=True
    h_bmbl = classify_headline(
        title="Exclusive: Ithaca Holdings in advanced talks to take Bumble (BMBL) private for $1.3 billion in cash",
        source="Wall Street Journal",
        pub_date="Mon, 09 Nov 2026 16:20:00 -0500",
        enforce_edgar_8k_check=True,
    )
    assert h_bmbl["is_already_announced"] is True
    assert h_bmbl["is_actionable_trigger"] is False
    assert "⚠️ ALREADY ANNOUNCED (LATE)" in h_bmbl["tags"]

    # 3. Friday Trial-Balloon Leak (50% clip warning)
    h_fri = classify_headline(
        title="Private equity consortium nearing a deal to buy TargetCorp for $45 per share",
        source="Reuters",
        pub_date="Fri, 06 Nov 2026 16:45:00 -0500",
    )
    assert h_fri["day_quality_tag"] == "⚠️ FRI TRIAL-BALLOON RISK (50% CLIP)"
    assert h_fri["recommended_clip_multiplier"] == 0.5

    # 4. Stock-Deal / Antitrust Trap
    h_trap = classify_headline(
        title="Marvell (MRVL) nearing a deal with Lumentum (LITE) in all-stock exchange ratio merger facing FTC antitrust review",
        source="Bloomberg",
        pub_date="Tue, 10 Nov 2026 16:30:00 -0500",
    )
    assert h_trap["is_stock_or_antitrust_trap"] is True
    assert h_trap["is_actionable_trigger"] is False
    assert "🚨 STOCK-DEAL / ANTITRUST TRAP" in h_trap["tags"]

    # 5. Already Announced (Form 8-K out -> leak window dead)
    h_late = classify_headline(
        title="Thoma Bravo announces definitive agreement to acquire SolarWinds for $18.50 per share",
        source="CNBC",
        pub_date="Mon, 09 Nov 2026 07:30:00 -0500",
    )
    assert h_late["is_already_announced"] is True
    assert h_late["is_actionable_trigger"] is False
    assert "⚠️ ALREADY ANNOUNCED (LATE)" in h_late["tags"]


def test_wires_edgar_quote_and_nightly_mailer(tmp_path: Path) -> None:
    """Verify wire scanner, EDGAR 8-K scanner, quote fetcher, HFT timer, and HTML mailer."""
    wires = scan_ma_wires(use_live_rss=False, include_curated_fallback=True)
    assert len(wires) >= 4
    # Ensure BMBL and WEN are NOT flagged as actionable triggers
    for w in wires:
        if w["detected_ticker"] in ("BMBL", "WEN"):
            assert w["is_actionable_trigger"] is False

    edgar = check_edgar_8k(["BMBL", "WEN", "U", "GPN"], use_live_sec=False)
    assert set(edgar.keys()) == {"BMBL", "WEN", "U", "GPN"}
    assert edgar["BMBL"]["has_recent_item_1_01"] is True
    assert edgar["WEN"]["has_recent_item_1_01"] is True
    assert edgar["U"]["has_recent_item_1_01"] is False
    assert edgar["GPN"]["has_recent_item_1_01"] is False

    q_bmbl = fetch_extended_hours_quote("BMBL", use_live_yf=False)
    assert q_bmbl["regular_market_price"] == 5.97
    assert q_bmbl["extended_hours_price"] == 5.97
    assert math.isclose(
        q_bmbl["max_clip_10pct_volume_usd"],
        q_bmbl["extended_hours_dollar_volume"] * 0.10,
    )

    cd = calculate_hft_cooldown("16:18")
    assert cd["settled_window_open_est"] == "17:18 EST"
    assert cd["settled_window_close_est"] == "19:18 EST"

    # Subject line with active trigger vs without active triggers
    active_sample = [
        classify_headline(
            title="Exclusive: Advent in advanced talks to acquire NewTarget (NTGT) for $40 per share in cash",
            source="Reuters",
            pub_date="Mon, 09 Nov 2026 16:20:00 -0500",
        )
    ]
    subj_trig, cnt = build_subject_line(
        active_sample, ["U", "WEN", "BMBL", "GPN"], "2026-11-08"
    )
    assert cnt == 1
    assert "🚨 [ARB CANNON TRIGGER ALERT]" in subj_trig

    subj_sweep, cnt0 = build_subject_line(
        wires, ["U", "WEN", "BMBL", "GPN"], "2026-11-08"
    )
    assert cnt0 == 0
    assert "📡 [Arb Cannon 5PM Sweep]" in subj_sweep

    report_out = tmp_path / "latest_5pm_report.html"
    mail_res = generate_and_send_nightly_report(
        dry_run=True, use_live_network=False, output_path=report_out
    )
    assert report_out.exists()
    html_text = report_out.read_text(encoding="utf-8")
    assert "ARB CANNON" in html_text
    assert "GATE_1_PLUMBING" in html_text
    assert mail_res["delivery_status"] == "DRY_RUN_SAVED_HTML"


def test_four_hour_leak_freshness_gate_and_stale_separation() -> None:
    """
    Verify the mandatory <= 4.0-Hour Leak Freshness Gate:
      - Leaks <= 4.0h old are marked is_stale_leak=False ('FRESH_ACTIONABLE' or 'BREAKING_HFT_COOLDOWN')
      - Leaks > 4.0h old (e.g. BMBL, WEN, U, GPN, or 6h old wire items) are marked is_stale_leak=True ('STALE_EXPIRED')
      - classify_headline(..., enforce_freshness_gate=True) disqualifies stale (>4h) headlines
      - evaluate_watchlist() marks BMBL, WEN, U, GPN as stale leaks with explicit Stale Leak rejection reasons
    """
    import datetime as dt

    ref_now = dt.datetime(2026, 11, 8, 18, 0, 0, tzinfo=EST_TZ)
    fresh_dt = ref_now - dt.timedelta(hours=1, minutes=30)
    stale_dt = ref_now - dt.timedelta(hours=6, minutes=15)

    fresh_info = compute_leak_freshness(fresh_dt, reference_dt=ref_now)
    assert fresh_info["is_stale_leak"] is False
    assert fresh_info["freshness_status"] == "FRESH_ACTIONABLE"
    assert "🟢 FRESH LEAK" in fresh_info["freshness_badge"]

    stale_info = compute_leak_freshness(stale_dt, reference_dt=ref_now)
    assert stale_info["is_stale_leak"] is True
    assert stale_info["freshness_status"] == "STALE_EXPIRED"
    assert "⏳ STALE LEAK" in stale_info["freshness_badge"]

    # Headline that is Tier-1 + 11th-hour + all-cash, but 6.25 hours old (> 4.0h max)
    h_stale = classify_headline(
        title="Exclusive: Bain Capital in advanced talks to take AcmeSoftware (ACME) private for $65.00 per share in cash",
        source="Wall Street Journal",
        pub_date=stale_dt.isoformat(),
        enforce_freshness_gate=True,
        reference_dt=ref_now,
    )
    assert h_stale["is_stale_leak"] is True
    assert h_stale["is_actionable_trigger"] is False
    assert any("Stale Leak" in r for r in h_stale["rejection_reasons"])

    # Same headline at 1.5 hours old (<= 4.0h max) clears
    h_fresh = classify_headline(
        title="Exclusive: Bain Capital in advanced talks to take AcmeSoftware (ACME) private for $65.00 per share in cash",
        source="Wall Street Journal",
        pub_date=fresh_dt.isoformat(),
        enforce_freshness_gate=True,
        reference_dt=ref_now,
    )
    assert h_fresh["is_stale_leak"] is False
    assert h_fresh["is_actionable_trigger"] is True

    # BMBL calculator defaults to stale (>4h), while simulate_fresh_leak=True overrides to fresh
    bmbl_default = calculate_deal_mechanics(
        ticker="BMBL", input_mode="EV_BILLIONS", value=1.30, use_live_network=False
    )
    assert bmbl_default["market_and_spread"]["is_stale_leak"] is True
    assert bmbl_default["leak_freshness"]["is_stale_leak"] is True

    bmbl_sim_fresh = calculate_deal_mechanics(
        ticker="BMBL",
        input_mode="EV_BILLIONS",
        value=1.30,
        use_live_network=False,
        simulate_fresh_leak=True,
    )
    assert bmbl_sim_fresh["market_and_spread"]["is_stale_leak"] is False

    # Watchlist evaluation marks U, HELE, WEN, RYTM, GPN as stale leaks (>4h)
    wl = evaluate_watchlist(use_live_network=False)
    assert [row["ticker"] for row in wl] == ["U", "HELE", "WEN", "RYTM", "GPN"]
    for row in wl:
        assert row["is_stale_leak"] is True
        assert "⏳ STALE LEAK" in row["freshness_badge"]
        assert any("Stale Leak" in r for r in row["rejection_reasons"])


def test_strict_rss_filter_no_fabricated_prices_and_verified_watchlist() -> None:
    """
    Verify:
      1. Zero synthetic/hardcoded pre-deal pipeline tickers ($DOCU, $BILL, $FIVN, $MTCH, $DBX, $CART)
         exist in config.json or arb_engine.py.
      2. Strict RSS filter (passes_strict_ma_headline_filter) blocks 'Clarus Corp Q3 2026 Earnings Call Highlights'
         and all 'Earnings Call', 'Q1', 'Q2', 'Q3', 'Q4', 'Transcript', ' Earnings ' headlines, while allowing
         headlines with hard M&A phrases.
      3. _extract_ticker_and_deal_value NEVER fabricates a deal price when no dollar amount is in regex.
      4. config.json Watchlist contains ONLY the 5 verified November 2026 situations (U, HELE, WEN, RYTM, GPN)
         with factual notes, and GPN has implied_deal_price=None.
    """
    # 1. Verify zero synthetic pipeline tickers in config.json or arb_engine.py
    arb_src = Path("arb_engine.py").read_text(encoding="utf-8")
    cfg_src = Path("config.json").read_text(encoding="utf-8")
    for banned in ("DOCU", "BILL", "FIVN", "MTCH", "DBX", "CART"):
        assert f'"{banned}"' not in arb_src
        assert f'"{banned}"' not in cfg_src

    # 2. Verify strict RSS filter rejects $CLAR Q3 2026 Earnings Call & all earnings/transcript noise
    assert (
        passes_strict_ma_headline_filter(
            "Clarus Corp Q3 2026 Earnings Call Highlights"
        )
        is False
    )
    assert (
        passes_strict_ma_headline_filter(
            "Clarus Corp (CLAR) Q3 Earnings Call Transcript Discusses Acquisition Strategy"
        )
        is False
    )
    assert (
        passes_strict_ma_headline_filter(
            "Company X Reports Q1 Revenue Beat and Buyout Rumors"
        )
        is False
    )
    assert (
        passes_strict_ma_headline_filter(
            "Company Y Q2 Transcript: Management Exploring a Sale"
        )
        is False
    )
    assert (
        passes_strict_ma_headline_filter(
            "Company Z Q4 Earnings Release and Acquisition Update"
        )
        is False
    )
    assert (
        passes_strict_ma_headline_filter(
            "Generic Market Rally as Tech Stocks Climb"
        )
        is False
    )

    # Valid hard M&A headlines without earnings noise pass
    assert (
        passes_strict_ma_headline_filter(
            "Reuters: Silver Lake & Saudi PIF approached Unity (U) in take-private talks"
        )
        is True
    )
    assert (
        passes_strict_ma_headline_filter(
            "WSJ: AstraZeneca in advanced talks to acquire Rhythm Pharmaceuticals (RYTM)"
        )
        is True
    )

    # 3. Verify _extract_ticker_and_deal_value NEVER fabricates a price when none is in headline
    tkr_unpriced, mode_unpriced, val_unpriced = _extract_ticker_and_deal_value(
        "FT/Reuters: CD&R and GTCR in early-stage joint take-private talks for Global Payments (GPN)"
    )
    assert tkr_unpriced == "GPN"
    assert mode_unpriced is None
    assert val_unpriced is None

    ch_unpriced = classify_headline(
        title="FT/Reuters: CD&R and GTCR in early-stage joint take-private talks for Global Payments (GPN)",
        source="Reuters",
        pub_date="Fri, 30 Oct 2026 16:30:00 -0400",
    )
    assert ch_unpriced["suggested_input_mode"] is None
    assert ch_unpriced["suggested_value"] is None
    assert "[TIER-1 SOURCE]" in ch_unpriced["factual_keyword_tags"]

    # Explicit dollar price in headline IS extracted accurately via regex
    tkr_priced, mode_priced, val_priced = _extract_ticker_and_deal_value(
        "Empower Brands submitted $37.00 per share all-cash bid to acquire Helen of Troy (HELE)"
    )
    assert tkr_priced == "HELE"
    assert mode_priced == "PER_SHARE"
    assert val_priced == 37.0

    # 4. Verify the 5 November 2026 Watchlist situations in config.json and evaluate_watchlist()
    cfg = load_config()
    wl_cfg = cfg["watchlist"]
    assert [w["ticker"] for w in wl_cfg] == ["U", "HELE", "WEN", "RYTM", "GPN"]

    wl_eval = {row["ticker"]: row for row in evaluate_watchlist(use_live_network=False)}
    assert set(wl_eval.keys()) == {"U", "HELE", "WEN", "RYTM", "GPN"}

    assert "Silver Lake & Saudi PIF approached Unity for ~$25B take-private" in wl_eval["U"]["rumor_headline"]
    assert "Empower Brands (Oaktree + Spectrum) submitted $37.00/sh" in wl_eval["HELE"]["rumor_headline"]
    assert "Trian & Sixth Street submitted $7.35/sh ($1.4B) non-binding offer" in wl_eval["WEN"]["rumor_headline"]
    assert "AstraZeneca approached Rhythm around ~$124/sh (~$10B)" in wl_eval["RYTM"]["rumor_headline"]
    assert "CD&R and GTCR in early-stage joint take-private talks" in wl_eval["GPN"]["rumor_headline"]

    # GPN is unpriced — must not have any fabricated deal price or spread
    assert wl_eval["GPN"]["implied_deal_price"] is None
    assert wl_eval["GPN"]["gross_spread_pct"] is None
    assert wl_eval["GPN"]["verdict"] == "AWAITING_PRICE_LEAK"
    assert wl_eval["GPN"]["tranche_ladder"] == []



