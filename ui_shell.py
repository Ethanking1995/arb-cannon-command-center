"""
Arb Cannon: Shared light UI shell (ui_shell.py)

Sidebar, base styles, and formatting helpers shared by the Scanner (/),
Biotech M&A Rumors (/biotech-rumors), Research (/research), and Backtest
(/backtest) pages.
"""

from __future__ import annotations

import json
from typing import Any, Tuple

from arb_engine import OPPORTUNITY_STATUS, OPPORTUNITY_STATUS_TEXT
from brand import BRAND_CSS, BRAND_LOCKUP_HTML

BIOTECH_NAV_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6.5L4.6 18.6A1.6 1.6 0 0 0 6 21h12a1.6 1.6 0 0 0 1.4-2.4L14 9.5V3"/><path d="M7.5 15h9"/></svg>'

NAV_ITEMS: Tuple[Tuple[str, str, str, str], ...] = (
    (
        "scanner",
        "Scanner",
        "/",
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>',
    ),
    (
        "biotech",
        "Biotech Rumors",
        "/biotech-rumors",
        BIOTECH_NAV_ICON,
    ),
    (
        "research",
        "Research",
        "/research",
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="14 3 14 9 20 9"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/></svg>',
    ),
    (
        "backtest",
        "Backtest",
        "/backtest",
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="20" x2="5" y2="13"/><line x1="10" y1="20" x2="10" y2="8"/><line x1="15" y1="20" x2="15" y2="11"/><line x1="20" y1="20" x2="20" y2="4"/></svg>',
    ),
    (
        "journal",
        "Trade Journal",
        "",
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="3" width="16" height="18" rx="2"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="12" y2="16"/></svg>',
    ),
    (
        "settings",
        "Settings",
        "",
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    ),
)

SHELL_CSS = r"""
    :root {
      --bg: #FFFFFF;
      --bg-sidebar: #F7F8FA;
      --bg-subtle: #F3F5F8;
      --bg-hover: #F5F8FF;
      --bg-selected: #EEF3FF;
      --line: #E6E8EC;
      --text: #111827;
      --text-2: #4B5563;
      --text-3: #8A93A3;
      --blue: #2F6BEA;
      --blue-soft: #E8EFFD;
      --blue-line: #9DB8F3;
      --green: #12963F;
      --green-soft: #E7F6EC;
      --red: #D93636;
      --red-soft: #FDECEC;
      --amber: #A86400;
      --amber-soft: #FFF4E0;
      --gray-pill: #EEF0F3;
      --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; }
    body {
      font-family: var(--font);
      font-size: 13px;
      color: var(--text);
      background: var(--bg);
      font-variant-numeric: tabular-nums;
      -webkit-font-smoothing: antialiased;
    }
    a { color: inherit; text-decoration: none; }
    button { font-family: inherit; font-size: inherit; color: inherit; background: none; border: none; cursor: pointer; }

    .app { display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }

    .sidebar { background: var(--bg-sidebar); border-right: 1px solid var(--line); padding: 14px 10px; display: flex; flex-direction: column; }
    .nav { display: flex; flex-direction: column; gap: 3px; }
    .nav-item { display: flex; align-items: center; gap: 11px; padding: 8px 10px; border-radius: 7px; color: var(--text-2); font-weight: 500; font-size: 13px; }
    .nav-item svg { width: 16px; height: 16px; flex: none; }
    .nav-item:hover { background: #EDEFF3; }
    .nav-item.active { background: var(--blue-soft); color: var(--text); font-weight: 600; }
    .nav-item.active svg { color: var(--blue); }
    .nav-item.disabled { color: var(--text-3); cursor: default; }
    .nav-item.disabled:hover { background: none; }
    .sidebar-foot { margin-top: auto; padding: 10px; border-top: 1px solid var(--line); }
    .sidebar-foot a { color: var(--text-3); font-size: 11.5px; }
    .sidebar-foot a:hover { color: var(--blue); }

    .main { padding: 14px 22px 24px; min-width: 0; }
    .page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
    .page-title { font-size: 19px; font-weight: 700; letter-spacing: -0.3px; }
    .page-sub { color: var(--text-2); font-size: 12.5px; margin-top: 3px; }
    .head-right { display: flex; align-items: center; gap: 14px; color: var(--text-2); font-size: 12px; padding-top: 4px; }
    .live-pill { display: inline-flex; align-items: center; gap: 6px; background: var(--green-soft); color: var(--green); font-weight: 600; font-size: 11.5px; padding: 3px 9px; border-radius: 999px; }
    .live-pill::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
    .live-pill.offline { background: var(--gray-pill); color: var(--text-3); }
    .live-pill.loading { background: var(--blue-soft); color: var(--blue); }
    .icon-btn { width: 26px; height: 26px; display: grid; place-items: center; border-radius: 6px; color: var(--text-2); }
    .icon-btn:hover { background: var(--bg-subtle); }
    .icon-btn svg { width: 15px; height: 15px; }
    .icon-btn.spinning svg, .btn-secondary.spinning svg { animation: spin 0.9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .kpi-strip { display: flex; align-items: center; flex-wrap: wrap; row-gap: 8px; margin-top: 14px; padding: 9px 0; border-bottom: 1px solid var(--line); }
    .kpi { display: flex; align-items: baseline; gap: 14px; padding: 0 26px; border-left: 1px solid var(--line); color: var(--text-2); font-size: 12.5px; }
    .kpi:first-child { padding-left: 2px; border-left: none; }
    .kpi strong { color: var(--text); font-size: 15px; font-weight: 700; }
    .kpi strong.pos { color: var(--green); }
    .kpi strong.neg { color: var(--red); }
    .kpi .kpi-note { color: var(--text-3); font-size: 11.5px; margin-left: -6px; }

    .tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--line); margin-top: 4px; }
    .tab { padding: 10px 10px 9px; color: var(--text-2); font-weight: 500; font-size: 13px; border-bottom: 2px solid transparent; margin-bottom: -1px; }
    .tab:hover { color: var(--text); }
    .tab.active { color: var(--blue); font-weight: 600; border-bottom-color: var(--blue); }
    .tab-count { color: var(--text-3); font-weight: 500; margin-left: 4px; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    .panel-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(330px, 1fr); }
    .cell { padding: 18px 20px 18px 0; min-width: 0; }
    .cell.right { padding: 18px 0 18px 22px; border-left: 1px solid var(--line); }
    .row-divider { grid-column: 1 / -1; border-top: 1px solid var(--line); }
    .section-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    .section-title { font-size: 15px; font-weight: 700; letter-spacing: -0.2px; }
    .sub-title { font-size: 13px; font-weight: 700; margin-top: 16px; }
    .pane-section { padding: 18px 0; }
    .pane-section + .pane-section { border-top: 1px solid var(--line); }
    .pane-note { color: var(--text-3); font-size: 11.5px; margin-top: 4px; }

    .data-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    .data-table th { text-align: left; font-weight: 500; color: var(--text-2); font-size: 12px; padding: 8px; border-bottom: 1px solid var(--line); white-space: nowrap; user-select: none; }
    .data-table th.sortable { cursor: pointer; }
    .data-table th.sortable:hover { color: var(--text); }
    .data-table th.num, .data-table td.num { text-align: right; }
    .sort-ind { color: var(--text-3); font-size: 10.5px; margin-left: 4px; }
    .sort-ind.on { color: var(--blue); }
    .data-table td { padding: 9px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: top; }
    .data-table td.wrap { white-space: normal; }
    .data-table tbody tr.clickable { cursor: pointer; }
    .data-table tbody tr.clickable:hover { background: var(--bg-hover); }
    .data-table tbody tr.selected { background: var(--bg-selected); }
    .data-table a.link { color: var(--blue); font-weight: 500; }
    .data-table a.link:hover { text-decoration: underline; }
    .radio { width: 13px; height: 13px; border-radius: 50%; border: 1.5px solid #B9C0CC; display: inline-block; vertical-align: middle; }
    tr.selected .radio { border: none; background: var(--blue); box-shadow: inset 0 0 0 3px var(--bg-selected), 0 0 0 1.5px var(--blue); }
    .tkr { font-weight: 700; }
    .table-empty { padding: 28px 8px; color: var(--text-3); text-align: center; white-space: normal; }

    .pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 500; background: var(--gray-pill); color: var(--text-2); white-space: nowrap; }
    .pill.open, .pill.go { background: var(--green-soft); color: var(--green); }
    .pill.tight, .pill.review { background: var(--amber-soft); color: var(--amber); }
    .pill.take_under, .pill.filed, .pill.avoid { background: var(--red-soft); color: var(--red); }
    .pill.monitoring, .pill.wait { background: var(--blue-soft); color: var(--blue); }
    .chip { display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 10.5px; font-weight: 500; background: var(--bg-subtle); color: var(--text-2); margin: 4px 4px 0 0; }
    .pos { color: var(--green); }
    .neg { color: var(--red); }
    .muted { color: var(--text-3); }

    .seg { display: inline-flex; background: var(--bg-subtle); border-radius: 6px; padding: 2px; }
    .seg button { padding: 3px 11px; border-radius: 5px; font-size: 11.5px; font-weight: 500; color: var(--text-2); }
    .seg button.active { background: var(--blue-soft); color: var(--blue); font-weight: 600; }

    .btn-primary { display: flex; justify-content: center; align-items: center; gap: 8px; width: 100%; margin-top: 16px; padding: 9px 12px; border-radius: 6px; background: var(--blue); color: #fff; font-weight: 600; font-size: 12.5px; }
    .btn-primary:hover { background: #2559C9; }
    .btn-primary svg, .btn-secondary svg { width: 14px; height: 14px; }
    .btn-secondary { display: inline-flex; align-items: center; gap: 7px; padding: 5px 11px; border-radius: 6px; border: 1px solid var(--line); background: #fff; color: var(--text); font-weight: 600; font-size: 12px; }
    .btn-secondary:hover { background: var(--bg-subtle); }
    .btn-secondary:disabled { color: var(--text-3); cursor: default; }

    .det-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .det-ticker { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }
    .det-company { color: var(--text-2); font-size: 12.5px; margin-top: 1px; }
    .det-text { color: var(--text-2); font-size: 12px; margin-top: 6px; line-height: 1.5; }
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 14px; }
    .metric { padding: 0 10px; border-left: 1px solid var(--line); }
    .metric:first-child { border-left: none; padding-left: 0; }
    .metric-label { color: var(--text-2); font-size: 11px; }
    .metric-value { font-weight: 700; font-size: 13.5px; margin-top: 3px; }
    .kv-list { margin-top: 8px; }
    .kv { display: flex; justify-content: space-between; gap: 16px; padding: 4px 0; font-size: 12.5px; }
    .kv .k { color: var(--text-2); }
    .kv .v { font-weight: 500; text-align: right; }
    .reason-list { list-style: none; margin-top: 6px; }
    .reason-list li { position: relative; padding: 4px 0 4px 14px; color: var(--text-2); font-size: 12px; line-height: 1.45; }
    .reason-list li::before { content: ''; position: absolute; left: 2px; top: 10px; width: 5px; height: 5px; border-radius: 50%; background: var(--text-3); }

    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-top: 12px; }
    .stat { padding: 12px 16px; border-left: 1px solid var(--line); }
    .stat:nth-child(4n + 1) { border-left: none; padding-left: 0; }
    .stat:nth-child(n + 5) { border-top: 1px solid var(--line); }
    .stat-label { color: var(--text-2); font-size: 11.5px; }
    .stat-value { font-weight: 700; font-size: 16px; margin-top: 3px; }

    .rule-list { list-style: none; margin-top: 8px; }
    .rule { display: grid; grid-template-columns: 28px 1fr; gap: 6px; padding: 11px 0; border-bottom: 1px solid var(--line); }
    .rule:last-child { border-bottom: none; }
    .rule-num { color: var(--blue); font-weight: 700; font-size: 12px; padding-top: 1px; }
    .rule-title { font-weight: 600; font-size: 12.5px; }
    .rule-desc { color: var(--text-2); font-size: 12px; margin-top: 3px; line-height: 1.45; }
    .rule-fail { color: var(--red); font-size: 11.5px; margin-top: 4px; line-height: 1.45; }

    .error-banner { margin-top: 12px; padding: 9px 12px; border-radius: 6px; background: var(--red-soft); color: var(--red); font-size: 12.5px; display: none; }

    @media (max-width: 1100px) {
      .panel-grid { grid-template-columns: 1fr; }
      .cell { padding-right: 0; }
      .cell.right { padding-left: 0; border-left: none; border-top: 1px solid var(--line); }
    }
"""

SHELL_JS = r"""
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const fmtPx = (v) => isNum(v) ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const fmtPxShort = (v) => isNum(v) ? '$' + (Number.isInteger(v) ? v.toLocaleString('en-US') : v.toFixed(2)) : '—';
  const fmtPct = (v, d = 1) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%' : '—';
  const fmtUsd = (v) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US') : '—';
  const fmtUsdPlain = (v) => isNum(v) ? '$' + Math.round(v).toLocaleString('en-US') : '—';
  const fmtBillions = (v) => isNum(v) ? (v < 0 ? '−' : '') + '$' + (Math.abs(v) / 1e9).toFixed(2) + 'B' : '—';
  const signClass = (v) => !isNum(v) ? 'muted' : v > 0 ? 'pos' : v < 0 ? 'neg' : '';
  const shortAge = (s) => String(s || '').split(' (')[0];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtLeakTime(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/.exec(String(s || ''));
    if (!m) return s || '—';
    const h = Number(m[4]);
    return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${h % 12 || 12}:${m[5]} ${h < 12 ? 'AM' : 'PM'}`;
  }
  function fmtDate(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ''));
    return m ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}` : (s || '—');
  }
  const statusKeyFor = (verdict, has8k) => has8k ? 'filed' : (VERDICT_STATUS[verdict] || 'monitoring');
  function statusPill(key) {
    const [label, hint] = STATUS_TEXT[key] || [key, ''];
    return `<span class="pill ${esc(key)}" title="${esc(hint)}">${esc(label)}</span>`;
  }
  const humanize = (s) => {
    const t = String(s || '').replace(/_/g, ' ').toLowerCase().trim();
    return t ? t[0].toUpperCase() + t.slice(1) : '—';
  };
  function gateLabel(id) {
    const m = /^(?:BIO_)?GATE_(\d+)_(.*)$/.exec(String(id || ''));
    return m ? `Gate ${Number(m[1])} · ${humanize(m[2]).toLowerCase()}` : humanize(id);
  }
  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${name}`));
    if (typeof onTabSwitched === 'function') onTabSwitched(name);
  }
  function relativeAgo(ts) {
    if (!ts) return '—';
    const s = Math.round((Date.now() - ts) / 1000);
    return `${s < 60 ? s + 's' : Math.floor(s / 60) + 'm'} ago`;
  }
  function bindSortHeaders(table, state, rerender) {
    table.querySelectorAll('th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (state.sortKey === key) {
          if (state.sortDir === -1) { state.sortKey = null; state.sortDir = 1; }
          else state.sortDir = -1;
        } else {
          state.sortKey = key;
          state.sortDir = 1;
        }
        rerender();
      });
    });
  }
  function paintSortHeaders(table, state) {
    table.querySelectorAll('th.sortable').forEach((th) => {
      const ind = th.querySelector('.sort-ind');
      const on = th.dataset.sort === state.sortKey;
      ind.classList.toggle('on', on);
      ind.innerHTML = on ? (state.sortDir > 0 ? '&#8593;' : '&#8595;') : '&#8645;';
    });
  }
  function sortRows(rows, state, valueOf) {
    if (!state.sortKey) return rows;
    return [...rows].sort((a, b) => {
      const va = valueOf(a, state.sortKey), vb = valueOf(b, state.sortKey);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'string') return va.localeCompare(vb) * state.sortDir;
      return (va - vb) * state.sortDir;
    });
  }
"""


def _sidebar_html(active: str) -> str:
    items = []
    for key, label, href, icon in NAV_ITEMS:
        if not href:
            items.append(
                f'<span class="nav-item disabled" title="Not built yet" aria-disabled="true">{icon}{label}</span>'
            )
            continue
        cls = "nav-item active" if key == active else "nav-item"
        items.append(f'<a class="{cls}" href="{href}">{icon}{label}</a>')
    return (
        '<aside class="sidebar">'
        f"{BRAND_LOCKUP_HTML}"
        f'<nav class="nav">{"".join(items)}</nav>'
        '<div class="sidebar-foot"><a href="/terminal" title="Original dark trading terminal">Classic terminal &rarr;</a></div>'
        "</aside>"
    )


def _js_const(name: str, value: Any) -> str:
    encoded = json.dumps(value).replace("</", "<\\/")
    return f"\n  const {name} = {encoded};"


def render_page(*, title: str, active: str, styles: str, body: str, script: str) -> str:
    """Wrap page-specific markup in the shared sidebar layout, styles, and JS helpers."""
    constants = _js_const("STATUS_TEXT", OPPORTUNITY_STATUS_TEXT) + _js_const(
        "VERDICT_STATUS", OPPORTUNITY_STATUS
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '  <meta charset="UTF-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"  <title>{title}</title>\n"
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
        f"  <style>{SHELL_CSS}{BRAND_CSS}{styles}</style>\n"
        "</head>\n<body>\n"
        f'<div class="app">\n{_sidebar_html(active)}\n<main class="main">\n{body}\n</main>\n</div>\n'
        f"<script>{constants}{SHELL_JS}{script}</script>\n"
        "</body>\n</html>\n"
    )
