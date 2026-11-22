"""
Arb Cannon: Strategy Backtests UI (backtest_ui.py)

Light backtest page served at GET /backtest. Reads GET /api/backtest for the
forensically audited 25-event biopharma 6-gate backtest (9 overnight gaps purged)
and the PE all-cash leak strategy benchmarks.
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

    /* PE YEARLY LEDGER */
    .pe-summary-row { cursor: pointer; }
    .pe-summary-row:hover { background: var(--bg-hover); }
    .pe-summary-row.active { background: var(--bg-selected); }
    .ledger-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-top: 12px; padding: 10px 12px; background: var(--bg-subtle); border: 1px solid var(--line); border-radius: 8px; }
    .ledger-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
    .filter-chip { padding: 4px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 500; color: var(--text-2); background: #fff; border: 1px solid var(--line); }
    .filter-chip:hover { border-color: var(--blue-line); color: var(--text); }
    .filter-chip.active { background: var(--blue-soft); border-color: var(--blue); color: var(--blue); font-weight: 600; }
    .filter-chip.pass-chip.active { background: var(--green-soft); border-color: var(--green); color: var(--green); }
    .ledger-search { min-width: 220px; padding: 5px 10px; border: 1px solid var(--line); border-radius: 6px; background: #fff; font: inherit; font-size: 12px; color: var(--text); }
    .year-ledger { margin-top: 14px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #fff; }
    .year-ledger > summary { list-style: none; cursor: pointer; padding: 11px 14px; background: var(--bg-sidebar); border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; user-select: none; }
    .year-ledger > summary::-webkit-details-marker { display: none; }
    .year-ledger:not([open]) > summary { border-bottom: none; }
    .year-head-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .year-caret { font-size: 11px; color: var(--text-2); transition: transform 0.15s ease; display: inline-block; }
    .year-ledger[open] .year-caret { transform: rotate(90deg); }
    .year-head-title { font-size: 14px; font-weight: 700; color: var(--text); }
    .year-head-meta { font-size: 12px; color: var(--text-2); }
    .year-head-right { display: flex; align-items: center; gap: 14px; font-size: 12px; flex-wrap: wrap; }
    .ledger-scroll { overflow-x: auto; }
    .deal-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .deal-table th { text-align: left; font-weight: 600; color: var(--text-2); font-size: 11.5px; padding: 8px 10px; border-bottom: 1px solid var(--line); background: #FAFBFD; white-space: nowrap; }
    .deal-table th.num, .deal-table td.num { text-align: right; white-space: nowrap; }
    .deal-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
    .deal-row { cursor: pointer; }
    .deal-row:hover { background: var(--bg-hover); }
    .deal-row.passed { background: #F2FBF5; }
    .deal-row.passed td:first-child { box-shadow: inset 3px 0 0 var(--green); }
    .deal-row.expanded { background: var(--bg-selected); }
    .deal-sub { color: var(--text-3); font-size: 11px; margin-top: 2px; line-height: 1.35; }
    .deal-reason { color: var(--text-2); font-size: 11.5px; margin-top: 4px; line-height: 1.38; max-width: 390px; }
    .cat-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; margin-left: 6px; background: var(--bg-subtle); color: var(--text-2); vertical-align: 1px; }
    .cat-tag.pe { background: var(--blue-soft); color: var(--blue); }
    .cat-tag.busted { background: var(--amber-soft); color: var(--amber); }
    .sec-gate-chip { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; background: var(--bg-subtle); color: var(--text-2); margin-left: 4px; }
    .drawer-row td { background: #F9FAFC; padding: 12px 16px; border-bottom: 1px solid var(--line); }
    .drawer-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; }
    .drawer-gates { display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px 14px; list-style: none; margin-top: 6px; }
    .drawer-gates li { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--text-2); }
    .g-dot { width: 15px; height: 15px; border-radius: 50%; flex: none; display: grid; place-items: center; font-size: 9.5px; font-weight: 700; color: #fff; }
    .g-dot.pass { background: var(--green); }
    .g-dot.fail { background: var(--red); }
    .g-dot.na { background: #C5CBD5; }
    .drawer-kvs { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 18px; margin-top: 6px; font-size: 11.5px; }
    .drawer-kv { display: flex; justify-content: space-between; gap: 8px; padding: 3px 0; border-bottom: 1px dashed var(--line); }
    .drawer-kv span:first-child { color: var(--text-2); }
    .drawer-kv span:last-child { font-weight: 600; text-align: right; }
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
          <h2 class="section-title">Annual P&amp;L &amp; Deal Audit Summary</h2>
          <p class="pane-note" id="pe-period"></p>
          <table class="data-table">
            <thead>
              <tr><th>Year</th><th class="num">Deals</th><th>Gate Outcomes</th><th class="num">Filtered Strategy</th><th class="num">Unfiltered (72h)</th><th class="num">Idle $SGOV</th></tr>
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
        <div class="section-head">
          <div>
            <h2 class="section-title">Yearly Acquisition Breakdown (Every Deal &amp; Gate Verdict)</h2>
            <p class="pane-note">Click any acquisition to inspect its 8-gate audit, overnight entry/volume/clip, and DA-day premarket/opening price.</p>
          </div>
          <div class="seg" id="pe-year-seg">
            <button class="active" data-yr="ALL" onclick="setPeYear('ALL')">All Years</button>
            <button data-yr="2026 YTD" onclick="setPeYear('2026 YTD')">2026 YTD</button>
            <button data-yr="2025" onclick="setPeYear('2025')">2025</button>
            <button data-yr="2024" onclick="setPeYear('2024')">2024</button>
          </div>
        </div>
        <div class="ledger-toolbar">
          <div class="ledger-filters" id="pe-gate-filters"></div>
          <input type="search" id="pe-search" class="ledger-search" placeholder="Filter ticker, target, or buyer…" oninput="setPeSearch(this.value)" />
        </div>
        <div id="pe-yearly-ledgers"></div>
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
    peYear: 'ALL',
    peGate: 'ALL',
    peSearch: '',
    peExpandedDeal: 'OPCH|2026 YTD',
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
    ['is_pre_8k_rumor', 'Pre-8K unannounced rumor'],
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
        <div class="metric"><div class="metric-label">Hold</div><div class="metric-value">${isNum(e.hold_trading_days) ? `${e.hold_trading_days} TDs${isNum(e.calendar_days) ? ` (${e.calendar_days} cal d)` : ''}` : '—'}</div></div>
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

  const PE_GATE_MAP = {
    GATE_2_TIER1_SOURCE: 'Gate 2 · No Leak',
    GATE_3_TIMING_AND_PRICE: 'Gate 3 · Timing / Session',
    GATE_4_ALL_CASH: 'Gate 4 · Stock / CVR',
    GATE_5_CLEAN_BUYER: 'Gate 5 · Strategic / CFIUS',
    GATE_6_NET_DEBT_AUDIT: 'Gate 6 · Take-Under',
    GATE_7_LIQUIDITY_AND_TRANCHES: 'Gate 7 · Spread <5.5%',
    GATE_8_EXIT_PROTOCOL: 'Gate 8 · >72h / Busted',
  };

  function fmtSharesCompact(v) {
    if (!isNum(v)) return '—';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M sh';
    if (v >= 1e3) return Math.round(v / 1e3).toLocaleString('en-US') + 'k sh';
    return v.toLocaleString('en-US') + ' sh';
  }

  function fmtAhVolUsd(v) {
    if (!isNum(v)) return '—';
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
    return fmtUsdPlain(v);
  }

  function setPeYear(yr) {
    STATE.peYear = yr;
    document.querySelectorAll('#pe-year-seg button').forEach((b) => b.classList.toggle('active', b.dataset.yr === yr));
    renderPe();
  }

  function setPeGate(g) {
    STATE.peGate = g;
    renderPe();
  }

  function setPeSearch(q) {
    STATE.peSearch = String(q || '');
    renderPeLedgers();
  }

  function peDealMatches(d) {
    if (STATE.peGate === 'PASSED' && !d.passed_all_gates) return false;
    if (STATE.peGate === 'LEAKED' && !d.had_pre_da_leak) return false;
    if (STATE.peGate.startsWith('GATE_') && !d.passed_all_gates) {
      if (d.primary_failed_gate !== STATE.peGate && !(d.failed_gates || []).includes(STATE.peGate)) return false;
    } else if (STATE.peGate.startsWith('GATE_') && d.passed_all_gates) {
      return false;
    }
    const q = STATE.peSearch.trim().toLowerCase();
    if (q) {
      const hay = `${d.ticker} ${d.company_name} ${d.buyer} ${d.category} ${d.primary_failed_gate_label || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  function renderPeDealRow(d) {
    const key = `${d.ticker}|${d.year}`;
    const isExp = STATE.peExpandedDeal === key;
    const catCls = d.category === 'PE Take-Private' ? 'pe' : d.category === 'Busted PE Leak' ? 'busted' : '';
    const daMeta = d.da_date
      ? `DA: ${fmtDate(d.da_date)}${d.da_timing ? ' (' + d.da_timing + ')' : ''}`
      : 'No DA signed (Busted / Rejected)';
    const evMeta = isNum(d.deal_ev_billions) && d.deal_ev_billions > 0 ? `$${d.deal_ev_billions.toFixed(2).replace(/\.00$/, '.0')}B EV` : '';
    const termsMeta = isNum(d.deal_price_per_share) ? `${fmtPx(d.deal_price_per_share)}/sh · ${d.consideration}` : d.consideration;

    let gateCell = '';
    if (d.passed_all_gates) {
      gateCell = `<span class="pill open">&#10003; Passed All 8 Gates</span><div class="deal-reason">${esc(d.gate_fail_reason)}</div>`;
    } else {
      const other = (d.failed_gates || [])
        .filter((g) => g !== d.primary_failed_gate)
        .slice(0, 2)
        .map((g) => `<span class="sec-gate-chip">+ ${esc((PE_GATE_MAP[g] || g).split(' · ')[0])}</span>`)
        .join('');
      gateCell = `<div><span class="pill avoid">&#10005; ${esc(d.primary_failed_gate_label)}</span>${other}</div><div class="deal-reason">${esc(d.gate_fail_reason)}</div>`;
    }

    let entryCell = '<span class="muted">—</span>';
    if (d.passed_all_gates && isNum(d.overnight_entry_price)) {
      entryCell = `<strong>${fmtPx(d.overnight_entry_price)}</strong><div class="deal-sub">Pre-leak: ${fmtPx(d.unaffected_close_price)}${isNum(d.gross_discount_to_deal_pct) ? ` · ${fmtPct(d.gross_discount_to_deal_pct, 1)} to DA` : ''}</div>`;
    } else if (isNum(d.overnight_entry_price)) {
      entryCell = `<span class="muted">Obs: ${fmtPx(d.overnight_entry_price)}</span><div class="deal-sub">Pre-leak: ${fmtPx(d.unaffected_close_price)}</div>`;
    } else if (isNum(d.unaffected_close_price)) {
      entryCell = `<span class="muted">—</span><div class="deal-sub">Unaff: ${fmtPx(d.unaffected_close_price)}</div>`;
    }

    let volCell = '<span class="muted">—</span>';
    if (isNum(d.overnight_share_volume) && d.overnight_share_volume > 0) {
      volCell = `<span>${esc(fmtSharesCompact(d.overnight_share_volume))}</span><div class="deal-sub">${esc(fmtAhVolUsd(d.overnight_dollar_volume))} AH vol</div>`;
    } else if (d.had_pre_da_leak && (d.leak_session === 'Weekend' || d.ticker === 'VRNA')) {
      volCell = `<span class="muted">0 sh</span><div class="deal-sub">Markets closed</div>`;
    }

    let clipCell = `<span class="muted">$0</span><div class="deal-sub">Blocked</div>`;
    if (d.passed_all_gates && d.deployment_clip_usd > 0) {
      clipCell = `<strong>${fmtUsdPlain(d.deployment_clip_usd)}</strong><div class="deal-sub">${d.deployed_shares.toLocaleString('en-US')} sh${isNum(d.clip_pct_of_ah_volume) ? ` · ${d.clip_pct_of_ah_volume}% AH vol` : ''}</div>`;
    }

    let openCell = '<span class="muted">—</span>';
    if (isNum(d.da_premarket_price) && isNum(d.da_open_price) && d.da_premarket_price !== d.da_open_price) {
      openCell = `<strong>${fmtPx(d.da_premarket_price)} PM / ${fmtPx(d.da_open_price)} Open</strong><div class="deal-sub">DA Offer: ${fmtPx(d.deal_price_per_share)}</div>`;
    } else if (isNum(d.da_open_price)) {
      const lbl = d.da_date === '2026-11-19' && d.da_timing === 'After-Hours' ? 'Post-DA AH' : 'Open';
      openCell = `<strong>${fmtPx(d.da_open_price)} ${lbl}</strong><div class="deal-sub">DA Offer: ${fmtPx(d.deal_price_per_share)}</div>`;
    } else if (!d.da_date && isNum(d.observed_exit_price)) {
      openCell = `<span class="muted">${fmtPx(d.observed_exit_price)} (72h stop)</span><div class="deal-sub">No DA signed</div>`;
    } else if (isNum(d.deal_price_per_share) && d.da_date) {
      openCell = `<span class="muted">—</span><div class="deal-sub">DA Offer: ${fmtPx(d.deal_price_per_share)}</div>`;
    }

    let pnlCell = '<span class="muted">$0</span>';
    if (d.passed_all_gates) {
      pnlCell = `<strong class="${signClass(d.realized_pnl_usd)}">${fmtUsd(d.realized_pnl_usd)}</strong><div class="deal-sub ${signClass(d.realized_return_pct)}">${fmtPct(d.realized_return_pct, 2)} at open${isNum(d.premarket_return_pct) ? ` (${fmtPct(d.premarket_return_pct, 2)} PM)` : ''}</div>`;
    } else if (isNum(d.unfiltered_leak_pnl_usd) && d.unfiltered_leak_pnl_usd < 0) {
      pnlCell = `<span class="pill open" style="font-size:10.5px;">Avoided ${fmtUsd(d.unfiltered_leak_pnl_usd)}</span><div class="deal-sub neg">Unfiltered: ${fmtPct(d.observed_leak_return_pct, 1)}</div>`;
    } else if (isNum(d.unfiltered_leak_pnl_usd) && d.unfiltered_leak_pnl_usd > 0) {
      pnlCell = `<span class="muted">$0</span><div class="deal-sub">Obs: ${fmtPct(d.observed_leak_return_pct, 1)} (${fmtUsd(d.unfiltered_leak_pnl_usd)})</div>`;
    }

    let drawerHtml = '';
    if (isExp) {
      const gatesHtml = (d.gate_checks || []).map((g) => {
        const cls = g.status === 'PASS' ? 'pass' : g.status === 'FAIL' ? 'fail' : 'na';
        const sym = g.status === 'PASS' ? '&#10003;' : g.status === 'FAIL' ? '&#10005;' : '—';
        return `<li><span class="g-dot ${cls}">${sym}</span><span><strong>Gate ${esc(g.number)}:</strong> ${esc(g.title)} (${esc(g.status)})</span></li>`;
      }).join('');
      const kvs = [
        ['Pre-Leak Close', fmtPx(d.unaffected_close_price)],
        ['Overnight Settled Entry', fmtPx(d.overnight_entry_price)],
        ['Overnight Share Vol', fmtSharesCompact(d.overnight_share_volume)],
        ['Overnight Dollar Vol', fmtAhVolUsd(d.overnight_dollar_volume)],
        ['10% AH Liquidity Cap', fmtUsdPlain(d.max_10pct_ah_clip_usd)],
        ['Deployment Clip', d.passed_all_gates ? `${fmtUsdPlain(d.deployment_clip_usd)} (${d.deployed_shares.toLocaleString('en-US')} sh)` : '$0 (Blocked by gates)'],
        ['DA Premarket Print', fmtPx(d.da_premarket_price)],
        ['DA Day 9:30 AM Open', fmtPx(d.da_open_price)],
        ['Signed DA Deal Price', d.da_date ? `${fmtPx(d.deal_price_per_share)} (${d.consideration})` : 'No DA signed'],
        ['Filtered vs Unfiltered P&L', `${fmtUsd(d.realized_pnl_usd)} vs ${fmtUsd(d.unfiltered_leak_pnl_usd)}`],
      ].map(([k, v]) => `<div class="drawer-kv"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join('');
      drawerHtml = `
        <tr class="drawer-row">
          <td colspan="7">
            <div class="drawer-grid">
              <div>
                <div style="font-weight:700;font-size:12px;">8-Gate Audit (${d.passed_gates_count}/${d.total_gates_count} Passed) &amp; Leak Chronology</div>
                <div class="deal-sub" style="color:var(--text-2);margin-top:4px;font-size:11.5px;">${esc(d.leak_summary)}</div>
                <ul class="drawer-gates">${gatesHtml}</ul>
              </div>
              <div>
                <div style="font-weight:700;font-size:12px;">Overnight Sizing &amp; DA Convergence Telemetry</div>
                <div class="drawer-kvs">${kvs}</div>
              </div>
            </div>
          </td>
        </tr>`;
    }

    return `
      <tr class="deal-row${d.passed_all_gates ? ' passed' : ''}${isExp ? ' expanded' : ''}" data-pekey="${esc(key)}">
        <td>
          <div><span class="tkr">$${esc(d.ticker)}</span> <span>${esc(d.company_name)}</span><span class="cat-tag ${catCls}">${esc(d.category)}</span></div>
          <div class="deal-sub"><strong>${esc(d.buyer)}</strong> · ${esc(daMeta)}${evMeta ? ' · ' + esc(evMeta) : ''} · ${esc(termsMeta)}</div>
        </td>
        <td>${gateCell}</td>
        <td class="num">${entryCell}</td>
        <td class="num">${volCell}</td>
        <td class="num">${clipCell}</td>
        <td class="num">${openCell}</td>
        <td class="num">${pnlCell}</td>
      </tr>${drawerHtml}`;
  }

  function renderPeLedgers() {
    const bm = STATE.data?.pe?.benchmarks || {};
    const blocks = (bm.yearly_breakdown || []).slice().reverse();
    const container = document.getElementById('pe-yearly-ledgers');
    if (!container) return;

    const visibleBlocks = STATE.peYear === 'ALL' ? blocks : blocks.filter((b) => b.year === STATE.peYear);
    container.innerHTML = visibleBlocks.map((yrBlock) => {
      const deals = (yrBlock.deals || []).filter(peDealMatches);
      const rowsHtml = deals.length
        ? deals.map(renderPeDealRow).join('')
        : `<tr><td colspan="7" class="table-empty">No ${esc(yrBlock.year)} acquisitions match the active filter.</td></tr>`;
      return `
        <details class="year-ledger" open>
          <summary>
            <div class="year-head-left">
              <span class="year-caret">&#9654;</span>
              <span class="year-head-title">${esc(yrBlock.year)} Acquisitions (${deals.length}${deals.length !== yrBlock.total_deals ? ' of ' + yrBlock.total_deals : ''})</span>
              <span class="pill ${yrBlock.passed_count > 0 ? 'open' : ''}">${yrBlock.passed_count} Passed</span>
              <span class="pill avoid">${yrBlock.failed_count} Failed Gates</span>
              <span class="year-head-meta">${yrBlock.signed_da_count} signed DAs + ${yrBlock.busted_leak_count} busted PE leaks</span>
            </div>
            <div class="year-head-right">
              <span>Deployed: <strong>${fmtUsdPlain(yrBlock.deployed_capital_usd)}</strong></span>
              <span>Filtered P&amp;L: <strong class="${signClass(yrBlock.filtered_strategy_usd)}">${fmtUsd(yrBlock.filtered_strategy_usd)}</strong></span>
              <span>Unfiltered: <strong class="${signClass(yrBlock.unfiltered_all_leaks_usd)}">${fmtUsd(yrBlock.unfiltered_all_leaks_usd)}</strong></span>
            </div>
          </summary>
          <div class="ledger-scroll">
            <table class="deal-table">
              <thead>
                <tr>
                  <th>Acquisition / Buyer &amp; Terms</th>
                  <th>Gate Verdict / Exact Gate Failed</th>
                  <th class="num">Overnight Entry</th>
                  <th class="num">Overnight Volume</th>
                  <th class="num">Deployment Clip</th>
                  <th class="num">DA Premarket / Open</th>
                  <th class="num">Strategy P&amp;L</th>
                </tr>
              </thead>
              <tbody>${rowsHtml}</tbody>
            </table>
          </div>
        </details>`;
    }).join('');

    container.querySelectorAll('tr.deal-row[data-pekey]').forEach((tr) => {
      tr.addEventListener('click', () => {
        STATE.peExpandedDeal = STATE.peExpandedDeal === tr.dataset.pekey ? null : tr.dataset.pekey;
        renderPeLedgers();
      });
    });
  }

  function renderPe() {
    const pe = STATE.data.pe;
    const bm = pe.benchmarks || {};
    document.getElementById('pe-kpis').innerHTML = [
      kpi('Audited Events', bm.total_ma_events_audited ?? '—', '', `(${bm.total_signed_das ?? 0} DAs + ${bm.total_busted_pe_leaks ?? 0} busted)`),
      kpi('Passed All 8 Gates', bm.qualified_passed_count ?? '—', 'pos'),
      kpi('Win Rate', isNum(bm.filtered_win_rate_pct) ? bm.filtered_win_rate_pct.toFixed(1) + '%' : '—', '', `(${bm.qualified_wins ?? 0}W / ${bm.qualified_losses ?? 0}L)`),
      kpi('Realized Overnight Move', fmtPct(bm.avg_net_spread_captured_pct, 2), 'pos'),
      kpi('Avg Hold', bm.avg_hold_time ? bm.avg_hold_time.split(' (')[0] : '—'),
    ].join('');
    document.getElementById('pe-period').textContent = bm.period_label || '';

    const rows = (bm.annual_pnl_table || []).map((r) => `
      <tr class="pe-summary-row${STATE.peYear === r.year ? ' active' : ''}" onclick="setPeYear('${esc(r.year)}')">
        <td><strong>${esc(r.year)}</strong></td>
        <td class="num">${r.total_deals ?? '—'}</td>
        <td><span class="pill ${(r.passed_count || 0) > 0 ? 'open' : ''}">${r.passed_count || 0}P</span> <span class="pill avoid">${r.failed_count || 0}F</span></td>
        <td class="num ${signClass(r.filtered_strategy_usd)}"><strong>${fmtUsd(r.filtered_strategy_usd)}</strong></td>
        <td class="num ${signClass(r.unfiltered_all_leaks_usd)}">${fmtUsd(r.unfiltered_all_leaks_usd)}</td>
        <td class="num pos">${fmtUsd(r.idle_sgov_usd)}</td></tr>`);
    rows.push(`
      <tr class="pe-summary-row${STATE.peYear === 'ALL' ? ' active' : ''}" onclick="setPeYear('ALL')">
        <td><strong>3-Year Total</strong></td>
        <td class="num"><strong>${bm.total_ma_events_audited ?? '—'}</strong></td>
        <td><span class="pill open">${bm.qualified_passed_count || 0}P</span> <span class="pill avoid">${Math.max(0, (bm.total_ma_events_audited || 0) - (bm.qualified_passed_count || 0))}F</span></td>
        <td class="num ${signClass(bm.cumulative_3yr_filtered_usd)}"><strong>${fmtUsd(bm.cumulative_3yr_filtered_usd)}</strong></td>
        <td class="num ${signClass(bm.cumulative_3yr_unfiltered_usd)}"><strong>${fmtUsd(bm.cumulative_3yr_unfiltered_usd)}</strong></td>
        <td class="num pos"><strong>${fmtUsd(bm.cumulative_3yr_sgov_usd)}</strong></td></tr>`);
    document.getElementById('pe-pnl-body').innerHTML = rows.join('');

    const activeDeals = (bm.yearly_breakdown || [])
      .filter((b) => STATE.peYear === 'ALL' || b.year === STATE.peYear)
      .flatMap((b) => b.deals || []);
    const passCnt = activeDeals.filter((d) => d.passed_all_gates).length;
    const leakCnt = activeDeals.filter((d) => d.had_pre_da_leak).length;
    const countGate = (gid) => activeDeals.filter((d) => !d.passed_all_gates && (d.primary_failed_gate === gid || (d.failed_gates || []).includes(gid))).length;
    const chips = [
      ['ALL', `All (${activeDeals.length})`, ''],
      ['PASSED', `Passed (${passCnt})`, 'pass-chip'],
      ['LEAKED', `Pre-DA Leaks (${leakCnt})`, ''],
      ...Object.entries(PE_GATE_MAP).map(([gid, lbl]) => [gid, `${lbl} (${countGate(gid)})`, '']),
    ];
    document.getElementById('pe-gate-filters').innerHTML = chips.map(([id, label, cls]) =>
      `<button class="filter-chip ${cls}${STATE.peGate === id ? ' active' : ''}" onclick="setPeGate('${id}')">${esc(label)}</button>`
    ).join('');

    renderPeLedgers();

    document.getElementById('pe-sizing').innerHTML = [
      ['Clip sizing rule', bm.clip_sizing_rule],
      ['Deployed clip ($OPCH)', fmtUsdPlain(bm.historical_avg_clip_usd)],
      ['Capital pool', fmtUsdPlain(bm.target_capital_pool_usd)],
      ['Idle cash parked in', bm.idle_parking_vehicle],
      ['3-year net extraction', bm.realized_annual_net_dollar_expectation],
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
