"""
Arb Cannon: Strategy Backtests UI (backtest_ui.py)

Light backtest page served at GET /backtest. Reads GET /api/backtest for the
30-event biopharma 6-gate backtest and the PE all-cash leak strategy benchmarks.
"""

from ui_shell import render_page

_STYLES = r"""
    .pane-kpis { margin-top: 0; }
    .event-filters { display: flex; align-items: center; gap: 10px; }
    .check-list { list-style: none; margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; column-gap: 16px; }
    .check-list li { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; color: var(--text-2); }
    .check { width: 15px; height: 15px; flex: none; border-radius: 50%; display: grid; place-items: center; font-size: 10px; font-weight: 700; color: #fff; }
    .check.yes { background: var(--green); }
    .check.no { background: #C5CBD5; }
    .note { margin-top: 10px; padding: 9px 11px; border-left: 2px solid var(--blue-line); background: var(--bg-subtle); color: var(--text-2); font-size: 12px; line-height: 1.5; }
    .rule-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 28px; }
    .rule-grid .rule:last-child { border-bottom: 1px solid var(--line); }
    .thesis-block { margin-top: 12px; }
    .thesis-block .sub-title { margin-top: 0; font-size: 12.5px; }
    .thesis-block p { color: var(--text-2); font-size: 12px; line-height: 1.55; margin-top: 3px; }
    .radar-item { padding: 11px 0; border-bottom: 1px solid var(--line); }
    .radar-item:last-child { border-bottom: none; }
    .radar-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    .radar-head strong { font-size: 13px; }
    .radar-meta { color: var(--text-3); font-size: 11px; margin-top: 2px; }
    .radar-text { color: var(--text-2); font-size: 12px; line-height: 1.5; margin-top: 4px; }
"""

_BODY = r"""
    <header class="page-head">
      <div>
        <h1 class="page-title">Strategy Backtests</h1>
        <p class="page-sub">Historical leak-to-deal outcomes behind the scanner's win rates and scenario odds.</p>
      </div>
      <div class="head-right"><span id="bt-period" class="muted"></span></div>
    </header>

    <nav class="tabs" style="margin-top:10px;">
      <button class="tab active" data-tab="bio" onclick="switchTab('bio')">Biopharma 6-Gate</button>
      <button class="tab" data-tab="pe" onclick="switchTab('pe')">PE All-Cash</button>
    </nav>

    <div id="error-banner" class="error-banner"></div>

    <!-- BIOPHARMA -->
    <section id="pane-bio" class="tab-pane active">
      <section class="kpi-strip pane-kpis" id="bio-kpis"></section>

      <div class="pane-section">
        <h2 class="section-title">Cohort Comparison</h2>
        <p class="pane-note">Filtering to the six biopharma gates is what lifts the win rate. The broad and unfiltered cohorts show what happens without them.</p>
        <table class="data-table">
          <thead>
            <tr><th>Cohort</th><th class="num">Events</th><th class="num">Wins</th><th class="num">Losses</th><th class="num">Win Rate</th><th class="num">Median Return</th><th class="num">Avg Return</th></tr>
          </thead>
          <tbody id="cohort-body"></tbody>
        </table>
        <p class="pane-note" id="cohort-note"></p>
      </div>

      <div class="panel-grid" style="border-top:1px solid var(--line);">
        <div class="cell">
          <div class="section-head">
            <h2 class="section-title">Historical Leak Events (<span id="event-count">0</span>)</h2>
            <div class="seg" id="event-filter">
              <button class="active" data-filter="all" onclick="setEventFilter('all')">All</button>
              <button data-filter="gated" onclick="setEventFilter('gated')">6-gate</button>
              <button data-filter="commercial" onclick="setEventFilter('commercial')">Commercial</button>
              <button data-filter="losses" onclick="setEventFilter('losses')">Losses</button>
            </div>
          </div>
          <table class="data-table" id="event-table">
            <thead>
              <tr>
                <th style="width:28px;"></th>
                <th class="sortable" data-sort="ticker">Ticker<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="leak_date">Leak Date<span class="sort-ind">&#8645;</span></th>
                <th class="sortable num" data-sort="settled_post_leak_entry_price">Entry<span class="sort-ind">&#8645;</span></th>
                <th class="sortable num" data-sort="resolution_price">Exit<span class="sort-ind">&#8645;</span></th>
                <th class="sortable num" data-sort="realized_return_pct">Return<span class="sort-ind">&#8645;</span></th>
                <th class="sortable num" data-sort="hold_trading_days">Hold<span class="sort-ind">&#8645;</span></th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody id="event-body"><tr><td colspan="8" class="table-empty">Loading backtest…</td></tr></tbody>
          </table>
        </div>
        <div class="cell right" id="event-detail"><div class="muted">Select an event to see its gates and P&amp;L.</div></div>

        <div class="row-divider"></div>

        <div class="cell">
          <h2 class="section-title">6-Gate Framework</h2>
          <ol class="rule-list" id="bio-rules"></ol>
        </div>
        <div class="cell right">
          <h2 class="section-title">Pre-Leak Radar</h2>
          <p class="pane-note">Names that fit the profile before any buyout rumor has leaked.</p>
          <div id="radar-list"></div>
          <h2 class="section-title" style="margin-top:18px;">Purged Untradable Gaps (<span id="gap-count">0</span>)</h2>
          <p class="pane-note">Deals excluded because the leak landed while markets were closed, so no entry was possible.</p>
          <div id="gap-list"></div>
        </div>
      </div>
    </section>

    <!-- PE ALL-CASH -->
    <section id="pane-pe" class="tab-pane">
      <section class="kpi-strip pane-kpis" id="pe-kpis"></section>

      <div class="panel-grid">
        <div class="cell">
          <h2 class="section-title">Annual P&amp;L</h2>
          <p class="pane-note" id="pe-period"></p>
          <table class="data-table">
            <thead>
              <tr><th>Year</th><th class="num">Filtered Strategy</th><th class="num">Unfiltered (All Leaks)</th><th class="num">Idle $SGOV</th></tr>
            </thead>
            <tbody id="pe-pnl-body"></tbody>
          </table>
          <div class="sub-title">Sizing</div>
          <div class="kv-list" id="pe-sizing"></div>
        </div>
        <div class="cell right">
          <h2 class="section-title">Strategy Thesis</h2>
          <p class="pane-note" id="pe-thesis-name"></p>
          <div id="pe-thesis"></div>
        </div>
      </div>

      <div class="pane-section" style="border-top:1px solid var(--line);">
        <h2 class="section-title">8-Gate Pre-Trade Checklist</h2>
        <p class="pane-note">Every gate must clear before staging the three-tranche limit-order ladder.</p>
        <ol class="rule-list rule-grid" id="pe-rules"></ol>
      </div>
    </section>
"""

_SCRIPT = r"""
  const STATE = {
    data: null,
    eventFilter: 'all',
    eventSort: { sortKey: null, sortDir: 1 },
    selected: null,
  };

  const OUTCOMES = {
    CONVERTED_8K: ['go', 'Deal signed'],
    STALLED_WALKAWAY: ['avoid', 'Walk-away'],
    NO_DEAL_DRIFT: ['review', 'No deal, drifted'],
    TAKE_UNDER_LOSS: ['avoid', 'Take-under loss'],
    WALKAWAY_THEN_FDA_SURGE: ['review', 'Walk-away, then FDA rally'],
    WALKAWAY_COLLAPSE: ['avoid', 'Walk-away collapse'],
    NO_DEAL_BLEED: ['avoid', 'No deal, bled'],
  };
  function outcomePill(o) {
    const [cls, label] = OUTCOMES[o] || ['', humanize(o)];
    return `<span class="pill ${cls}">${esc(label)}</span>`;
  }

  const GATE_CHECKS = [
    ['named_pharma_suitor', 'Named pharma suitor'],
    ['specific_dollar_bid_leaked', 'Specific dollar bid leaked'],
    ['fda_approved_commercial_anchor', 'FDA-approved commercial drug'],
    ['clean_cap_table', 'Clean cap table'],
    ['multi_bidder_scarcity', 'Multiple bidders'],
    ['bolt_on_size_3b_to_15b', 'Bolt-on size ($3B–$15B)'],
    ['zero_moa_overlap', 'No pipeline overlap with buyer'],
    ['passes_anchor_92pct_gate', 'Entry ≤ 92% of leaked price'],
  ];

  async function loadBacktest() {
    try {
      const resp = await fetch('/api/backtest');
      if (!resp.ok) throw new Error(`Backtest request failed (HTTP ${resp.status})`);
      STATE.data = await resp.json();
      const events = STATE.data.biopharma.historical_events || [];
      STATE.selected = events.length ? events[0].ticker + '|' + events[0].leak_date : null;
      renderBio();
      renderPe();
    } catch (err) {
      const banner = document.getElementById('error-banner');
      banner.textContent = `Could not load backtest data: ${err.message}`;
      banner.style.display = 'block';
    }
  }

  const eventKey = (e) => e.ticker + '|' + e.leak_date;

  function kpi(label, value, cls = '', note = '') {
    return `<div class="kpi">${esc(label)} <strong class="${cls}">${esc(value)}</strong>${note ? `<span class="kpi-note">${esc(note)}</span>` : ''}</div>`;
  }

  function renderBio() {
    const bt = STATE.data.biopharma;
    const f = bt.filtered_6_gate_metrics || {};
    const u = bt.unfiltered_metrics || {};
    const b = bt.broad_commercial_metrics || {};
    document.getElementById('bt-period').textContent = (bt.period_covered || '').split(' (')[0];

    document.getElementById('bio-kpis').innerHTML = [
      kpi('Qualified Events', f.qualified_events ?? '—'),
      kpi('Win Rate', isNum(f.win_rate_pct) ? f.win_rate_pct.toFixed(1) + '%' : '—', '', `(${f.wins ?? '—'}W / ${f.losses_or_walkaways ?? '—'}L)`),
      kpi('Median Return', fmtPct(f.median_return_per_trade_pct, 2), signClass(f.median_return_per_trade_pct)),
      kpi('Worst Loss', fmtPct(f.worst_loss_pct, 2), signClass(f.worst_loss_pct)),
      kpi('Avg Hold', isNum(f.avg_hold_trading_days) ? `${f.avg_hold_trading_days} trading days` : '—'),
    ].join('');

    const cohortRow = (name, c, events) => `
      <tr>
        <td><strong>${esc(name)}</strong></td>
        <td class="num">${events ?? '—'}</td>
        <td class="num">${c.wins ?? '—'}</td>
        <td class="num">${c.losses_or_walkaways ?? '—'}</td>
        <td class="num"><strong>${isNum(c.win_rate_pct) ? c.win_rate_pct.toFixed(1) + '%' : '—'}</strong></td>
        <td class="num ${signClass(c.median_return_per_trade_pct)}">${fmtPct(c.median_return_per_trade_pct, 2)}</td>
        <td class="num ${signClass(c.avg_return_per_trade_pct)}">${fmtPct(c.avg_return_per_trade_pct, 2)}</td>
      </tr>`;
    document.getElementById('cohort-body').innerHTML =
      cohortRow('6-gate qualified', f, f.qualified_events) +
      cohortRow('Broad commercial', b, b.total_events) +
      cohortRow('All rumors (unfiltered)', u, u.total_events);
    document.getElementById('cohort-note').textContent = b.note || '';

    document.getElementById('bio-rules').innerHTML = (bt.gatekeeper_rules || []).map((r, i) => `
      <li class="rule">
        <span class="rule-num">${String(i + 1).padStart(2, '0')}</span>
        <div>
          <div class="rule-title">${esc(r.title)}</div>
          <div class="rule-desc">${esc(r.description)}</div>
          ${r.hard_fail ? `<div class="rule-fail">Hard fail: ${esc(r.hard_fail)}</div>` : ''}
        </div>
      </li>`).join('');

    document.getElementById('radar-list').innerHTML = (bt.regime_b_pre_leak_radar || []).map((r) => `
      <div class="radar-item">
        <div class="radar-head"><strong>${esc(r.ticker)}</strong><span class="pill monitoring">${esc(humanize(String(r.regime_status || '').replace(/^REGIME_B_/, '')))}</span></div>
        <div class="radar-meta">${esc(r.company_name)} · ${esc(r.trigger_date)}</div>
        <div class="radar-text"><strong>Anchor:</strong> ${esc(r.commercial_anchor)}</div>
        <div class="radar-text">${esc(r.walk_away_leverage_catalyst)}</div>
        <div class="radar-meta">${esc(r.pro_forma_cash_runway)}</div>
      </div>`).join('') || '<div class="muted" style="margin-top:8px;">No names on the radar.</div>';

    const gaps = bt.purged_untradable_weekend_gaps || [];
    document.getElementById('gap-count').textContent = gaps.length;
    document.getElementById('gap-list').innerHTML = gaps.map((g) => `
      <div class="radar-item">
        <div class="radar-head"><strong>${esc(g.ticker)}</strong><span class="radar-meta">${esc(fmtDate(g.date))}</span></div>
        <div class="radar-meta">${esc(g.company_name)} · ${esc(g.buyer)}</div>
        <div class="radar-text"><strong>Claimed:</strong> ${esc(g.script_claimed_entry_exit)}</div>
        <div class="radar-text"><strong>Reality:</strong> ${esc(g.actual_market_reality)}</div>
      </div>`).join('');

    renderEvents();
    renderEventDetail();
  }

  function setEventFilter(f) {
    STATE.eventFilter = f;
    document.querySelectorAll('#event-filter button').forEach((b) => b.classList.toggle('active', b.dataset.filter === f));
    renderEvents();
  }

  function filteredEvents() {
    let events = STATE.data.biopharma.historical_events || [];
    if (STATE.eventFilter === 'gated') events = events.filter((e) => e.cleared_6_biopharma_gates);
    if (STATE.eventFilter === 'commercial') events = events.filter((e) => e.in_broad_commercial_cohort);
    if (STATE.eventFilter === 'losses') events = events.filter((e) => isNum(e.realized_return_pct) && e.realized_return_pct < 0);
    return sortRows(events, STATE.eventSort, (e, k) => e[k]);
  }

  function renderEvents() {
    paintSortHeaders(document.getElementById('event-table'), STATE.eventSort);
    const events = filteredEvents();
    document.getElementById('event-count').textContent = events.length;
    const body = document.getElementById('event-body');
    if (!events.length) {
      body.innerHTML = '<tr><td colspan="8" class="table-empty">No events match this filter.</td></tr>';
      return;
    }
    body.innerHTML = events.map((e) => `
      <tr class="clickable${eventKey(e) === STATE.selected ? ' selected' : ''}" data-key="${esc(eventKey(e))}">
        <td><span class="radio"></span></td>
        <td class="tkr">${esc(e.ticker)}</td>
        <td>${esc(fmtDate(e.leak_date))}</td>
        <td class="num">${fmtPx(e.settled_post_leak_entry_price)}</td>
        <td class="num">${fmtPx(e.resolution_price)}</td>
        <td class="num ${signClass(e.realized_return_pct)}">${fmtPct(e.realized_return_pct, 2)}</td>
        <td class="num">${isNum(e.hold_trading_days) ? e.hold_trading_days + 'd' : '—'}</td>
        <td>${outcomePill(e.outcome)}</td>
      </tr>`).join('');
    body.querySelectorAll('tr[data-key]').forEach((tr) => {
      tr.addEventListener('click', () => {
        STATE.selected = tr.dataset.key;
        renderEvents();
        renderEventDetail();
      });
    });
  }

  function renderEventDetail() {
    const panel = document.getElementById('event-detail');
    const e = (STATE.data.biopharma.historical_events || []).find((x) => eventKey(x) === STATE.selected);
    if (!e) { panel.innerHTML = '<div class="muted">Select an event to see its gates and P&amp;L.</div>'; return; }
    const checks = GATE_CHECKS.map(([k, label]) => `
      <li><span class="check ${e[k] ? 'yes' : 'no'}">${e[k] ? '&#10003;' : '&#10005;'}</span>${esc(label)}</li>`).join('');
    const finalCash = isNum(e.final_deal_cash_per_share)
      ? fmtPx(e.final_deal_cash_per_share) + (isNum(e.cvr_per_share) && e.cvr_per_share > 0 ? ` + ${fmtPx(e.cvr_per_share)} CVR` : '')
      : 'No deal';
    const notes = [e.disqualification_note, e.standalone_recovery_note].filter(Boolean)
      .map((n) => `<div class="note">${esc(n)}</div>`).join('');
    panel.innerHTML = `
      <div class="det-head">
        <div>
          <div class="det-ticker">${esc(e.ticker)}</div>
          <div class="det-company">${esc(e.company_name)}</div>
        </div>
        ${outcomePill(e.outcome)}
      </div>
      <div class="det-text">${esc(e.leak_headline)}<br><span class="muted">${esc(e.leak_source)} · ${esc(fmtDate(e.leak_date))} → ${esc(fmtDate(e.resolution_date))}</span></div>
      <div class="metrics">
        <div class="metric"><div class="metric-label">Return</div><div class="metric-value ${signClass(e.realized_return_pct)}">${fmtPct(e.realized_return_pct, 2)}</div></div>
        <div class="metric"><div class="metric-label">Hold</div><div class="metric-value">${isNum(e.hold_trading_days) ? e.hold_trading_days + ' days' : '—'}</div></div>
        <div class="metric"><div class="metric-label">Entry vs Leak</div><div class="metric-value">${isNum(e.entry_pct_of_anchor_display) ? e.entry_pct_of_anchor_display.toFixed(1) + '%' : '—'}</div></div>
        <div class="metric"><div class="metric-label">Deal EV</div><div class="metric-value">${isNum(e.deal_ev_billions) ? '$' + e.deal_ev_billions + 'B' : '—'}</div></div>
      </div>

      <div class="sub-title">Price Path</div>
      <div class="kv-list">
        <div class="kv"><span class="k">Unaffected price</span><span class="v">${fmtPx(e.unaffected_price)}</span></div>
        <div class="kv"><span class="k">Leaked valuation</span><span class="v">${fmtPx(e.leaked_valuation_anchor)}</span></div>
        <div class="kv"><span class="k">Settled entry</span><span class="v">${fmtPx(e.settled_post_leak_entry_price)}</span></div>
        <div class="kv"><span class="k">Exit</span><span class="v">${fmtPx(e.resolution_price)}</span></div>
        <div class="kv"><span class="k">Final deal cash</span><span class="v">${finalCash}</span></div>
      </div>

      <div class="sub-title">Gate Checklist ${e.cleared_6_biopharma_gates ? '<span class="pill go" style="margin-left:6px;">Cleared</span>' : '<span class="pill avoid" style="margin-left:6px;">Failed</span>'}</div>
      <ul class="check-list">${checks}</ul>

      <div class="sub-title">P&amp;L on ${fmtUsdPlain(e.clip_usd)} (${isNum(e.shares) ? e.shares.toLocaleString('en-US') : '—'} shares)</div>
      <div class="kv-list">
        <div class="kv"><span class="k">IRA (0% tax)</span><span class="v ${signClass(e.ira_0pct_pnl_usd)}"><strong>${fmtUsd(e.ira_0pct_pnl_usd)}</strong></span></div>
        <div class="kv"><span class="k">NYC taxable (54.5%)</span><span class="v ${signClass(e.nyc_54_5pct_pnl_usd)}">${fmtUsd(e.nyc_54_5pct_pnl_usd)}</span></div>
      </div>
      ${e.commercial_drug_note ? `<div class="det-text"><strong>Commercial anchor:</strong> ${esc(e.commercial_drug_note)}</div>` : ''}
      ${notes}`;
  }

  function renderPe() {
    const pe = STATE.data.pe;
    const bm = pe.benchmarks || {};
    const freq = /^(\d+\s*to\s*\d+)/.exec(bm.qualified_trade_frequency || '');
    document.getElementById('pe-kpis').innerHTML = [
      kpi('Win Rate', isNum(bm.filtered_win_rate_pct) ? bm.filtered_win_rate_pct.toFixed(1) + '%' : '—'),
      kpi('Named Buyer, Sun–Tue', isNum(bm.sun_mon_tue_named_buyer_win_rate_pct) ? bm.sun_mon_tue_named_buyer_win_rate_pct.toFixed(1) + '%' : '—'),
      kpi('Avg Net Spread', fmtPct(bm.avg_net_spread_captured_pct), 'pos'),
      kpi('Avg Hold', bm.avg_hold_time || '—'),
      kpi('Qualified Trades', freq ? `${freq[1]} / yr` : (bm.qualified_trade_frequency || '—')),
    ].join('');
    document.getElementById('pe-period').textContent = bm.period_label || '';

    const rows = (bm.annual_pnl_table || []).map((r) => `
      <tr><td>${esc(r.year)}</td>
        <td class="num pos">${fmtUsd(r.filtered_strategy_usd)}</td>
        <td class="num">${fmtUsd(r.unfiltered_all_leaks_usd)}</td>
        <td class="num">${fmtUsd(r.idle_sgov_usd)}</td></tr>`);
    rows.push(`
      <tr><td><strong>3-Year Total</strong></td>
        <td class="num pos"><strong>${fmtUsd(bm.cumulative_3yr_filtered_usd)}</strong></td>
        <td class="num"><strong>${fmtUsd(bm.cumulative_3yr_unfiltered_usd)}</strong></td>
        <td class="num"><strong>${fmtUsd(bm.cumulative_3yr_sgov_usd)}</strong></td></tr>`);
    document.getElementById('pe-pnl-body').innerHTML = rows.join('');

    document.getElementById('pe-sizing').innerHTML = [
      ['Clip sizing rule', bm.clip_sizing_rule],
      ['Historical avg clip', fmtUsdPlain(bm.historical_avg_clip_usd)],
      ['Capital pool', fmtUsdPlain(bm.target_capital_pool_usd)],
      ['Idle cash parked in', bm.idle_parking_vehicle],
      ['Expected annual net', bm.realized_annual_net_dollar_expectation],
    ].map(([k, v]) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v ?? '—')}</span></div>`).join('');

    const th = pe.thesis || {};
    document.getElementById('pe-thesis-name').textContent = th.name || '';
    document.getElementById('pe-thesis').innerHTML = [
      ['The alpha window', th.alpha_window],
      ['Why the discount exists', th.structural_discount_reason],
      ['Settled entry window', th.settled_entry_window],
      ['Convergence exit', th.convergence_exit],
      ['Tax fungibility', th.cross_account_tax_fungibility],
    ].filter(([, v]) => v).map(([k, v]) => `
      <div class="thesis-block"><div class="sub-title">${esc(k)}</div><p>${esc(v)}</p></div>`).join('');

    document.getElementById('pe-rules').innerHTML = (pe.gatekeeper_rules || []).map((r) => `
      <li class="rule">
        <span class="rule-num">${esc(r.number || '')}</span>
        <div>
          <div class="rule-title">${esc(r.title)}</div>
          <div class="rule-desc">${esc(r.description)}</div>
          ${r.hard_fail ? `<div class="rule-fail">Hard fail: ${esc(r.hard_fail)}</div>` : ''}
        </div>
      </li>`).join('');
  }

  bindSortHeaders(document.getElementById('event-table'), STATE.eventSort, () => STATE.data && renderEvents());
  window.addEventListener('DOMContentLoaded', loadBacktest);
"""

BACKTEST_HTML = render_page(
    title="Strategy Backtests",
    active="backtest",
    styles=_STYLES,
    body=_BODY,
    script=_SCRIPT,
)
