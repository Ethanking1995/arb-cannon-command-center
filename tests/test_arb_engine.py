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
    _build_opportunity,
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
from biopharma_leak_backtest import (
    evaluate_biopharma_bolt_on_candidate,
    run_biopharma_backtest,
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


def test_biopharma_bolt_on_backtest_and_live_rytm_audit() -> None:
    """
    Verify the Forensically Audited 25-Event Tradable Biopharma M&A Backtest (2022–2026)
    and the User's Live $100,000 @ $113.00 (~885 Shares) $RYTM Position Audit:
      - 9 untradable weekend/overnight gaps ($KRTX, $ITCI, $BPMC, $VRNA, $RETA, $IMGN, $CBAY, $DCPH, $CDTX)
        are purged into purged_untradable_weekend_gaps and excluded from historical_events
      - Post-8K merger-arb topping wars ($MTSR, $AVDL) carry is_pre_8k_rumor=False and are excluded from 6-gate pre-8K setups
      - Unfiltered 25 tradable events: 36.0% win rate (9W / 16L), -11.20% strict deal-window median
      - Broad Commercial / Pivotal pre-8K cohort (N = 13, incl. unpriced $BMRN, $ALNY, $FOLD, $ACAD):
        38.5% (5W / 8L) conversion rate, -11.64% median
      - Strict 6-Gate Pre-8K Named Suitor + Specific Leaked Dollar Bid + Entry <= 92% Anchor (N = 9):
        55.6% (5W / 4L) true audited conversion rate (+19.86% winner median spread, +8.73% overall median)
      - Corrected NYSE trading-day counts: $GBT (1 TD), $HZNP (9 TDs), $SGEN (11 TDs), $RNA (57 TDs), $SAGE (97 TDs)
      - Hard Gate 5 (`entry_pct_of_anchor <= 0.92`) blocks $VTYX (121.6%), $SWTX (108.0%), $MRTX (100.3%)
      - Live $100,000 @ $113.00 (885 shares) on $RYTM:
        * Scenario 1 ($124.00 Base, 20.0% Prob): +$9,735.00 (+9.73%)
        * Scenario 2 ($134.00 Sweetened, 35.6% Prob): +$18,585.00 (+18.58%)
        * Scenario 3 ($92.00 Fundamental Walk-Away Floor [$89–$95], 44.4% Prob): -$18,585.00 (-0.46% of $4M NW)
        * Audited Probability-Weighted EV: +$311.52 (+0.31%) | Positive-EV Add Ceiling (87%): $107.88
    """
    bt = run_biopharma_backtest(standard_biopharma_clip_usd=100000.0)
    assert bt["unfiltered_metrics"]["total_events"] == 25
    assert bt["unfiltered_metrics"]["wins"] == 9
    assert bt["unfiltered_metrics"]["losses_or_walkaways"] == 16
    assert bt["unfiltered_metrics"]["win_rate_pct"] == 36.0
    assert bt["unfiltered_metrics"]["median_return_per_trade_pct"] == -11.20

    bc = bt["broad_commercial_metrics"]
    assert bc["total_events"] == 13
    assert bc["wins"] == 5
    assert bc["losses_or_walkaways"] == 8
    assert bc["win_rate_pct"] == 38.5
    assert bc["median_return_per_trade_pct"] == -11.64
    assert bc["avg_return_per_trade_pct"] == -2.16

    fg = bt["filtered_6_gate_metrics"]
    assert fg["qualified_events"] == 9
    assert fg["wins"] == 5
    assert fg["losses_or_walkaways"] == 4
    assert fg["win_rate_pct"] == 55.6
    assert fg["winner_median_spread_pct"] == 19.86
    assert fg["median_return_per_trade_pct"] == 8.73
    assert fg["avg_return_per_trade_pct"] == 4.18
    assert fg["avg_hold_trading_days"] == 23.2
    assert fg["expected_hold_clock"] == "1–57 trading days (Bimodal: 1–11d fast | 53–57d contested)"
    assert fg["hold_days_range"] == "1–97 NYSE TDs (1–57 TDs press leaks; 97 TDs public 13D review)"
    assert fg["lone_break_standalone_recovery_pct"] == 68.9

    # Verify all 9 untradable weekend/overnight gaps are purged from historical_events
    purged_tickers = {g["ticker"] for g in bt["purged_untradable_weekend_gaps"]}
    assert purged_tickers == {
        "KRTX",
        "ITCI",
        "BPMC",
        "VRNA",
        "RETA",
        "IMGN",
        "CBAY",
        "DCPH",
        "CDTX",
    }
    by_tkr = {e["ticker"]: e for e in bt["historical_events"]}
    assert purged_tickers.isdisjoint(set(by_tkr.keys()))

    # Verify post-8K topping wars ($MTSR, $AVDL) are excluded from pre-8K 6-gate setups
    assert by_tkr["MTSR"]["is_pre_8k_rumor"] is False
    assert by_tkr["MTSR"]["cleared_6_biopharma_gates"] is False
    assert by_tkr["AVDL"]["is_pre_8k_rumor"] is False
    assert by_tkr["AVDL"]["cleared_6_biopharma_gates"] is False

    # Verify all 9 qualified Pre-8K Named-Buyer + Dollar-Bid setups (5 winners + 4 walk-aways)
    qualified_tickers = [
        e["ticker"] for e in bt["historical_events"] if e["cleared_6_biopharma_gates"]
    ]
    assert qualified_tickers == [
        "GBT",
        "HZNP",
        "SGEN",
        "RNA",
        "SAGE",
        "RVMD",
        "CYTK",
        "MLTX",
        "PTGX",
    ]
    assert by_tkr["GBT"]["realized_return_pct"] == 8.73
    assert by_tkr["GBT"]["hold_trading_days"] == 1
    assert by_tkr["SGEN"]["hold_trading_days"] == 11
    assert by_tkr["RNA"]["hold_trading_days"] == 57
    assert by_tkr["SAGE"]["hold_trading_days"] == 97
    assert by_tkr["BMRN"]["realized_return_pct"] == -20.0
    assert by_tkr["ALNY"]["realized_return_pct"] == -15.0
    assert by_tkr["VKTX"]["realized_return_pct"] == -45.0

    # Verify >92% anchor chases ($VTYX, $SWTX, $MRTX) fail Gate 5
    assert by_tkr["VTYX"]["passes_anchor_92pct_gate"] is False
    assert by_tkr["VTYX"]["cleared_6_biopharma_gates"] is False
    assert by_tkr["SWTX"]["passes_anchor_92pct_gate"] is False
    assert by_tkr["SWTX"]["cleared_6_biopharma_gates"] is False
    assert by_tkr["MRTX"]["passes_anchor_92pct_gate"] is False
    assert by_tkr["MRTX"]["realized_return_pct"] == -3.65

    # Verify Regime B radar contains RYTM, SRRK, COGT
    reg_b_tickers = [r["ticker"] for r in bt["regime_b_pre_leak_radar"]]
    assert reg_b_tickers == ["RYTM", "SRRK", "COGT"]

    # Verify Live $100,000 @ $113.00 (885 shares) $RYTM scenario matrix and bimodal exit windows
    assert bt["live_rytm_audit"]["positive_ev_87pct_ceiling"] == 107.88
    live_lot = bt["live_rytm_audit"]["live_100k_lot_scenarios"]
    assert live_lot["shares"] == 885
    assert live_lot["entry_price"] == 113.00
    assert live_lot["scenarios"][0]["ira_0pct_tax_pnl_usd"] == 9735.0
    assert live_lot["scenarios"][1]["ira_0pct_tax_pnl_usd"] == 18585.0
    assert live_lot["scenarios"][2]["ira_0pct_tax_pnl_usd"] == -18585.0
    assert live_lot["scenarios"][2]["pct_of_4m_net_worth"] == -0.46
    assert live_lot["probability_weighted_ev_usd"] == 311.52
    assert live_lot["probability_weighted_ev_pct"] == 0.31
    assert len(bt["live_rytm_audit"]["deal_timeline_windows"]) == 3

    # Verify $RYTM live audit via calculate_deal_mechanics in BIOPHARMA_BOLT_ON mode
    rytm_calc = calculate_deal_mechanics(
        ticker="RYTM",
        input_mode="PER_SHARE",
        value=124.0,
        clip_usd=190000.0,
        coc_dilution_pct=1.5,
        use_live_network=False,
        strategy_mode="BIOPHARMA_BOLT_ON",
        sweetened_ceiling_per_share=134.0,
    )
    assert rytm_calc["strategy_mode"] == "BIOPHARMA_BOLT_ON"
    assert [t["limit_price"] for t in rytm_calc["tranche_ladder"]] == [
        112.73,
        110.22,
        107.83,
    ]
    bio_audit = rytm_calc["biopharma_bolt_on_audit"]
    assert bio_audit is not None
    assert bio_audit["hard_ceiling_92pct"] == 114.08
    assert bio_audit["entry_pct_of_anchor"] <= 0.92
    assert bio_audit["passes_anchor_92pct_gate"] is True
    assert bio_audit["all_biopharma_gates_passed"] is True
    assert bio_audit["passed_gates_count"] == 6
    assert bio_audit["verdict"] == "BIO_PASS_HOT"
    assert (
        bio_audit["pnl_summary"]["ira_sweetened_bid_net_profit_usd"]
        > bio_audit["pnl_summary"]["ira_base_bid_net_profit_usd"]
    )

    # Verify paying above $114.08 (>92% of $124 anchor) fails BIO_GATE_5
    overpay_audit = evaluate_biopharma_bolt_on_candidate(
        ticker="RYTM",
        current_price=116.50,
        unaffected_price=86.44,
        base_cash_bid_per_share=124.00,
        sweetened_ceiling_per_share=134.00,
        deal_ev_billions=10.0,
        fda_approved_commercial_anchor=True,
    )
    assert overpay_audit["passes_anchor_92pct_gate"] is False
    assert overpay_audit["all_biopharma_gates_passed"] is False
    assert overpay_audit["verdict"] == "BIO_FAIL_OVER_92PCT_CEILING"






def test_scanner_biotech_signal_rechecks_92pct_ceiling_at_live_price() -> None:
    """A 6/6 biotech audit is only actionable while the live price is at or under the 92% max buy price."""
    audit = run_biopharma_backtest()["live_rytm_audit"]
    base_row = {
        "ticker": "RYTM",
        "company_name": "Rhythm Pharmaceuticals, Inc.",
        "verdict": "PASS_HOT",
        "is_stale_leak": True,
        "leak_age_human": "5.9d ago",
    }

    under = _build_opportunity({**base_row, "extended_hours_price": 113.0, "regular_market_price": 113.0}, audit)
    assert under["biotech_signal"]["is_actionable"] is True
    assert under["biotech_signal"]["gates_passed"] == 6
    assert (under["decision_key"], under["decision_label"]) == ("go", "Actionable")
    assert "4-hour news rule doesn't apply" in under["decision_text"]

    over = _build_opportunity({**base_row, "extended_hours_price": 114.2, "regular_market_price": 114.2}, audit)
    signal = over["biotech_signal"]
    assert signal["is_actionable"] is False
    assert signal["label"] == "Biotech M&A rumor · price above max buy"
    assert signal["gates_passed"] == 5
    assert [c["passed"] for c in signal["checks"]].index(False) == 4
    assert (over["decision_key"], over["decision_label"]) == ("wait", "Wait for dip")
    assert "$114.20 price is above the $114.08 max buy price" in over["decision_text"]

    other = _build_opportunity({**base_row, "ticker": "GPN", "extended_hours_price": 80.0}, None)
    assert other["biotech_signal"] is None
