"""
Arb Cannon: M&A Leak Arbitrage Command Center — Automated 5:00 PM EST Nightly Email Daemon (nightly_mailer.py)

Usage:
    python nightly_mailer.py [--dry-run]

1. Runs scan_ma_wires(), check_edgar_8k(), and calculates live spreads & 3-tranche ladders for all Watchlist tickers.
2. Builds an institutional dark/clean inline-CSS HTML email report (latest_5pm_report.html).
3. Computes dynamic subject line based on Tier-1 + 11th-Hour Trigger detection.
4. Sends via smtplib.SMTP_SSL("smtp.gmail.com", 465) when SMTP_EMAIL and SMTP_APP_PASSWORD are configured (unless --dry-run).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from arb_engine import (
    BASE_DIR,
    GATEKEEPER_RULES,
    STRATEGY_BENCHMARKS,
    check_edgar_8k,
    evaluate_watchlist,
    load_config,
    scan_ma_wires,
)

load_dotenv()

EST_TZ = ZoneInfo("America/New_York")
REPORT_HTML_PATH = BASE_DIR / "latest_5pm_report.html"


def build_subject_line(
    wire_items: List[Dict[str, Any]],
    watchlist_tickers: List[str],
    date_str: Optional[str] = None,
) -> Tuple[str, int]:
    """
    Generate the dynamic subject line required by specification:
      - If >= 1 article has both TIER-1 SOURCE and 11TH-HOUR TRIGGER:
        🚨 [ARB CANNON TRIGGER ALERT] {N} Tier-1 M&A Leak(s) Detected — Run 60s Gatekeeper ({Date})
      - Otherwise:
        📡 [Arb Cannon 5PM Sweep] {N} Wire Hits | Watchlist ($U, $WEN, $BMBL, $GPN) — {Date}
    """
    if not date_str:
        date_str = dt.datetime.now(EST_TZ).strftime("%Y-%m-%d")

    tier1_11th_hits = [
        item
        for item in wire_items
        if item.get("is_actionable_trigger")
        or (
            item.get("is_tier1")
            and item.get("is_11th_hour")
            and not item.get("is_stock_or_antitrust_trap")
            and not item.get("is_already_announced")
            and not item.get("is_stale_leak")
        )
    ]
    trigger_count = len(tier1_11th_hits)

    if trigger_count >= 1:
        subject = (
            f"🚨 [ARB CANNON TRIGGER ALERT] {trigger_count} Tier-1 M&A Leak(s) Detected "
            f"— Run 60s Gatekeeper ({date_str})"
        )
    else:
        wl_str = ", ".join(f"${t}" for t in watchlist_tickers) or "$U, $HELE, $WEN, $RYTM, $GPN"
        subject = (
            f"📡 [Arb Cannon 5PM Sweep] {len(wire_items)} Wire Hits | "
            f"Watchlist ({wl_str}) — {date_str}"
        )
    return subject, trigger_count


def render_email_html(
    subject: str,
    trigger_count: int,
    wire_items: List[Dict[str, Any]],
    watchlist_rows: List[Dict[str, Any]],
    generated_at_str: str,
) -> str:
    """Build the inline-CSS institutional HTML email report."""
    if trigger_count >= 1:
        banner_bg = "#064E3B"
        banner_border = "#10B981"
        banner_title = f"🚨 ACTIVE TIER-1 11TH-HOUR M&A LEAK TRIGGER ({trigger_count} QUALIFIED SCOOP{'S' if trigger_count != 1 else ''})"
        banner_sub = (
            "Wait for T+60m Post-Headline HFT Cooldown (5:30 PM – 7:00 PM EST Window). "
            "Verify all 8 Gatekeeper rules before staging 3-Tranche Limit Orders."
        )
    else:
        banner_bg = "#1E293B"
        banner_border = "#F59E0B"
        banner_title = "📡 5:00 PM EST EXTENDED-HOURS SWEEP — NO NEW TIER-1 11TH-HOUR TRIGGERS"
        banner_sub = (
            "Dry powder remains parked in $SGOV (~4.6% Treasury yield). Monitor percolating "
            "PE watchlist targets below."
        )

    # Render Graded M&A Wire Hits rows
    wire_rows_html = []
    for item in wire_items[:12]:
        badges_html = []
        factual_tags = item.get("factual_keyword_tags") or item.get("tags", [])
        for tag in factual_tags:
            if "TIER-1" in tag or "MON/TUE" in tag or "MID-WEEK" in tag:
                b_bg, b_fg = "#064E3B", "#34D399"
            elif "11TH-HOUR" in tag:
                b_bg, b_fg = "#78350F", "#FBBF24"
            elif "TRAP" in tag or "ALREADY" in tag:
                b_bg, b_fg = "#7F1D1D", "#FCA5A5"
            else:
                b_bg, b_fg = "#1E293B", "#94A3B8"
            badges_html.append(
                f'<span style="display:inline-block;padding:2px 7px;margin:2px 4px 2px 0;'
                f'border-radius:4px;background:{b_bg};color:{b_fg};font-size:11px;'
                f'font-family:monospace;font-weight:600;">{html.escape(tag)}</span>'
            )

        link_url = html.escape(str(item.get("link") or "#"))
        detected_tkr = html.escape(str(item.get("detected_ticker") or "M&A"))
        wire_rows_html.append(
            f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #1E293B;color:#F8FAFC;font-size:13px;">
                <div style="font-weight:600;margin-bottom:4px;">
                  <span style="color:#38BDF8;font-family:monospace;">[${detected_tkr}]</span>
                  <a href="{link_url}" style="color:#F8FAFC;text-decoration:underline;">{html.escape(str(item.get('title') or ''))}</a>
                </div>
                <div>{''.join(badges_html)}</div>
              </td>
              <td style="padding:10px 12px;border-bottom:1px solid #1E293B;color:#94A3B8;font-size:12px;white-space:nowrap;">
                {html.escape(str(item.get('source') or ''))}<br/>
                <span style="color:#64748B;font-family:monospace;">{html.escape(str(item.get('published_at') or ''))}</span>
              </td>
            </tr>
            """
        )

    # Render Watchlist Spread & Net-Debt Audit Table
    watchlist_html_rows = []
    for row in watchlist_rows:
        tkr = html.escape(row["ticker"])
        verdict = row["verdict"]
        if verdict == "PASS_HOT":
            v_bg, v_fg = "#064E3B", "#10B981"
        elif verdict == "FAIL_TAKE_UNDER":
            v_bg, v_fg = "#7F1D1D", "#EF4444"
        else:
            v_bg, v_fg = "#78350F", "#F59E0B"

        tranches = row.get("tranche_ladder", [])
        t1 = tranches[0] if len(tranches) > 0 else {"limit_price": 0, "shares": 0}
        t2 = tranches[1] if len(tranches) > 1 else {"limit_price": 0, "shares": 0}
        t3 = tranches[2] if len(tranches) > 2 else {"limit_price": 0, "shares": 0}

        net_debt_b = row["net_debt_usd"] / 1e9
        edgar_badge = html.escape(
            row.get("edgar_8k", {}).get(
                "status_badge", "🟢 NO 8-K ITEM 1.01 (OPEN)"
            )
        )

        implied_price = row.get("implied_deal_price")
        gross_spread = row.get("gross_spread_pct")
        rumored_val = row.get("rumored_value")
        rumor_note = html.escape(row.get("rumor_headline", ""))

        if implied_price is None or gross_spread is None:
            input_summary = "UNPRICED: Awaiting price leak"
            implied_cell = f'<strong>AWAITING PRICE LEAK</strong><br/><span style="font-size:11px;color:#94A3B8;">Net Debt: ${net_debt_b:.2f}B</span>'
            spread_badge_text = f"UNPRICED ({verdict})"
            ladder_cell = '<span style="color:#94A3B8;">AWAITING PER-SHARE PRICE LEAK</span>'
            pnl_cell = '<span style="color:#94A3B8;">AWAITING PRICE LEAK</span>'
        else:
            input_summary = f"{html.escape(row.get('input_mode', ''))}: {rumored_val}"
            implied_cell = f'<strong>${implied_price:.2f}/sh</strong><br/><span style="font-size:11px;color:#94A3B8;">Net Debt: ${net_debt_b:.2f}B</span>'
            spread_badge_text = f"{gross_spread:+.2f}% ({verdict})"
            ladder_cell = (
                f"T1 (5.5%): <strong>${t1['limit_price']:.2f}</strong> ({t1['shares']:,} sh)<br/>"
                f"T2 (6.5%): <strong>${t2['limit_price']:.2f}</strong> ({t2['shares']:,} sh)<br/>"
                f"T3 (8.0%): <strong>${t3['limit_price']:.2f}</strong> ({t3['shares']:,} sh)"
            )
            pnl_cell = (
                f'<span style="color:#10B981;font-weight:700;">IRA (0%): +${row["ira_tax_free_net_profit_usd"]:,.0f}</span><br/>'
                f'<span style="color:#F59E0B;">NYC (54.5%): +${row["nyc_taxable_net_profit_usd"]:,.0f}</span>'
            )

        watchlist_html_rows.append(
            f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;font-weight:700;color:#F8FAFC;">
                ${tkr}<br/>
                <span style="font-size:11px;color:#94A3B8;font-weight:400;">{input_summary}</span>
                <div style="font-size:10px;color:#CBD5E1;font-weight:400;margin-top:4px;max-width:250px;">{rumor_note}</div>
              </td>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;color:#E2E8F0;text-align:right;">
                Reg: ${row['regular_market_price']:.2f}<br/>
                <strong>AH: ${row['extended_hours_price']:.2f}</strong>
              </td>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;color:#E2E8F0;text-align:right;">
                {implied_cell}
              </td>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;text-align:right;">
                <span style="display:inline-block;padding:3px 7px;border-radius:4px;background:{v_bg};color:{v_fg};font-weight:700;font-size:12px;">
                  {spread_badge_text}
                </span><br/>
                <span style="font-size:11px;color:#94A3B8;">{edgar_badge}</span>
              </td>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;color:#10B981;font-size:12px;">
                {ladder_cell}
              </td>
              <td style="padding:10px;border-bottom:1px solid #1E293B;font-family:monospace;text-align:right;font-size:12px;">
                {pnl_cell}
              </td>
            </tr>
            """
        )

    # Render 8-Point Gatekeeper Checklist
    gate_items_html = []
    for g in GATEKEEPER_RULES:
        gate_items_html.append(
            f"""
            <li style="margin-bottom:8px;color:#CBD5E1;font-size:12px;line-height:1.45;">
              <strong style="color:#10B981;font-family:monospace;">[{html.escape(g['name'])}] {html.escape(g['title'])}:</strong>
              {html.escape(g['description'])}
              <span style="color:#F87171;">(Fail: {html.escape(g['hard_fail'])})</span>
            </li>
            """
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(subject)}</title>
</head>
<body style="margin:0;padding:24px;background-color:#0B0F19;color:#F8FAFC;font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',Roboto,sans-serif;">
  <div style="max-width:960px;margin:0 auto;background-color:#111827;border:1px solid #1E293B;border-radius:8px;overflow:hidden;">
    
    <!-- Header Bar -->
    <div style="padding:18px 24px;background-color:#0F172A;border-bottom:1px solid #1E293B;">
      <div style="font-size:11px;font-family:monospace;color:#38BDF8;letter-spacing:1px;text-transform:uppercase;">
        ARB CANNON: M&amp;A LEAK ARBITRAGE COMMAND CENTER // 5:00 PM EST NIGHTLY BRIEFING
      </div>
      <h1 style="margin:6px 0 0 0;font-size:20px;color:#F8FAFC;">{html.escape(subject)}</h1>
      <div style="margin-top:4px;font-size:12px;color:#94A3B8;font-family:monospace;">
        Generated: {html.escape(generated_at_str)} | Dry Powder: $400,000 ($SGOV) | Standard Clip: $380,000 | 84.2% Filtered Win Rate (+5.8% Avg Net Spread)
      </div>
    </div>

    <!-- Top Trigger Status Banner -->
    <div style="margin:20px 24px;padding:16px 18px;background-color:{banner_bg};border-left:4px solid {banner_border};border-radius:4px;">
      <div style="font-size:15px;font-weight:700;color:#F8FAFC;margin-bottom:4px;">{banner_title}</div>
      <div style="font-size:13px;color:#E2E8F0;">{banner_sub}</div>
    </div>

    <!-- Section 1: Graded M&A Wire Hits -->
    <div style="padding:0 24px 20px 24px;">
      <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.8px;color:#94A3B8;border-bottom:1px solid #1E293B;padding-bottom:8px;">
        1. Graded M&amp;A Wire Hits (Last 24–48 Hours)
      </h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background-color:#0F172A;text-align:left;font-size:11px;color:#94A3B8;text-transform:uppercase;">
            <th style="padding:8px 12px;border-bottom:1px solid #1E293B;">Headline &amp; Gatekeeper Classification Badges</th>
            <th style="padding:8px 12px;border-bottom:1px solid #1E293B;">Source &amp; Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {''.join(wire_rows_html)}
        </tbody>
      </table>
    </div>

    <!-- Section 2: Watchlist Spread & Net-Debt Audit Table -->
    <div style="padding:0 24px 20px 24px;">
      <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.8px;color:#94A3B8;border-bottom:1px solid #1E293B;padding-bottom:8px;">
        2. Watchlist Spread, SEC XBRL Net-Debt Audit &amp; 5:30 PM 3-Tranche Limit Ladder ($U, $HELE, $WEN, $RYTM, $GPN)
      </h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background-color:#0F172A;font-size:11px;color:#94A3B8;text-transform:uppercase;">
            <th style="padding:8px 10px;text-align:left;border-bottom:1px solid #1E293B;">Target</th>
            <th style="padding:8px 10px;text-align:right;border-bottom:1px solid #1E293B;">Reg / AH Price</th>
            <th style="padding:8px 10px;text-align:right;border-bottom:1px solid #1E293B;">Implied Cash / Net Debt</th>
            <th style="padding:8px 10px;text-align:right;border-bottom:1px solid #1E293B;">Gross Spread &amp; 8-K</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:1px solid #1E293B;">5:30 PM Limit Ladder ($380k Clip)</th>
            <th style="padding:8px 10px;text-align:right;border-bottom:1px solid #1E293B;">Expected P&amp;L (IRA vs NYC)</th>
          </tr>
        </thead>
        <tbody>
          {''.join(watchlist_html_rows)}
        </tbody>
      </table>
    </div>

    <!-- Section 3: 8-Point Pre-Trade Gatekeeper Checklist -->
    <div style="padding:0 24px 24px 24px;">
      <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.8px;color:#94A3B8;border-bottom:1px solid #1E293B;padding-bottom:8px;">
        3. Mandatory 8-Point Pre-Trade Gatekeeper Checklist
      </h2>
      <ul style="margin:10px 0 0 0;padding-left:20px;">
        {''.join(gate_items_html)}
      </ul>
      <div style="margin-top:14px;padding:12px;background-color:#0F172A;border:1px solid #1E293B;border-radius:4px;font-size:12px;color:#94A3B8;font-family:monospace;">
        <strong>Cross-Account Tax Fungibility Rule:</strong> Execute 100% of clip inside Tax-Sheltered IRA (0.0% tax) to avoid the 54.5% NYC short-term marginal tax drag. Withdraw matching dollar amount from Taxable $SGOV principal at $0 capital gains tax.
      </div>
    </div>

  </div>
</body>
</html>
"""
    return html_doc


def generate_and_send_nightly_report(
    dry_run: bool = False,
    use_live_network: bool = True,
    output_path: Path = REPORT_HTML_PATH,
) -> Dict[str, Any]:
    """
    Execute the 5:00 PM EST sweep, write latest_5pm_report.html to disk,
    and optionally transmit via SMTP_SSL (smtp.gmail.com:465) if configured.
    """
    cfg = load_config()
    now_est = dt.datetime.now(EST_TZ)
    date_str = now_est.strftime("%Y-%m-%d")
    generated_at_str = now_est.strftime("%Y-%m-%d %H:%M:%S EST")

    watchlist_tickers = [
        w.get("ticker", "") for w in cfg.get("watchlist", []) if w.get("ticker")
    ]
    edgar_status = check_edgar_8k(watchlist_tickers, use_live_sec=use_live_network)
    watchlist_rows = evaluate_watchlist(use_live_network=use_live_network)
    wire_items = scan_ma_wires(
        use_live_rss=use_live_network, include_curated_fallback=not use_live_network
    )

    subject, trigger_count = build_subject_line(
        wire_items=wire_items,
        watchlist_tickers=watchlist_tickers,
        date_str=date_str,
    )

    html_content = render_email_html(
        subject=subject,
        trigger_count=trigger_count,
        wire_items=wire_items,
        watchlist_rows=watchlist_rows,
        generated_at_str=generated_at_str,
    )

    output_path.write_text(html_content, encoding="utf-8")

    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_APP_PASSWORD", "").strip()
    recipient_email = (
        os.getenv("ALERT_RECIPIENT_EMAIL", "").strip() or smtp_email
    )

    delivery_status = "DRY_RUN_SAVED_HTML"
    smtp_sent = False
    smtp_error: Optional[str] = None

    if not dry_run and smtp_email and smtp_password and "your_" not in smtp_email:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_email
            msg["To"] = recipient_email
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, [recipient_email], msg.as_string())
            smtp_sent = True
            delivery_status = f"SENT_SMTP_SSL_TO_{recipient_email}"
        except Exception as exc:
            smtp_error = str(exc)
            delivery_status = f"SMTP_ERROR_FALLBACK_SAVED ({exc})"
    elif not dry_run:
        delivery_status = "SAVED_HTML_ONLY (SMTP credentials not set in .env)"

    return {
        "subject": subject,
        "trigger_count": trigger_count,
        "wire_hits_count": len(wire_items),
        "watchlist_count": len(watchlist_rows),
        "edgar_checked_tickers": list(edgar_status.keys()),
        "report_path": str(output_path),
        "delivery_status": delivery_status,
        "smtp_sent": smtp_sent,
        "smtp_error": smtp_error,
        "generated_at": generated_at_str,
        "html_content": html_content,
        " benchmarks_included": STRATEGY_BENCHMARKS["period_label"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Arb Cannon 5:00 PM EST Nightly M&A Leak Report Generator & Mailer"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate latest_5pm_report.html and print summary without sending SMTP email.",
    )
    args = parser.parse_args(argv)

    result = generate_and_send_nightly_report(dry_run=args.dry_run)
    print("=" * 78)
    print("ARB CANNON 5:00 PM EST NIGHTLY SWEEP COMPLETE")
    print("=" * 78)
    print(f"Subject Line    : {result['subject']}")
    print(f"Tier-1 Triggers : {result['trigger_count']}")
    print(f"Total Wire Hits : {result['wire_hits_count']}")
    print(f"Watchlist Audit : {result['watchlist_count']} targets audited")
    print(f"Delivery Status : {result['delivery_status']}")
    print(f"HTML Report Out : {result['report_path']}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
