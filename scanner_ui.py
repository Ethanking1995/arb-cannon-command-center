"""
Arb Cannon: Biotech M&A Overnight Scanner UI (scanner_ui.py)

Light, flat single-page scanner served at GET /. Reads GET /api/scanner for the
KPI strip, ranked opportunities, wires, and performance tables, and
GET /api/price-history for the price & VWAP chart.
"""

from ui_shell import render_page

_STYLES = r"""
    .opp-table td { vertical-align: middle; }
    .bio-tag { display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; padding: 1px 6px; border-radius: 4px; background: var(--green-soft); color: var(--green); font-size: 10.5px; font-weight: 600; vertical-align: 1px; }
    .bio-tag svg { width: 10px; height: 10px; }
    .bio-tag.inactive { background: var(--amber-soft); color: var(--amber); }

    /* DETAIL */
    .bio-callout { margin-top: 10px; padding: 9px 11px; background: var(--green-soft); border: 1px solid #BFE5CB; border-radius: 6px; }
    .bio-callout-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    .bio-callout-title { display: flex; align-items: center; gap: 5px; color: var(--green); font-weight: 700; font-size: 12.5px; }
    .bio-callout-title svg { width: 13px; height: 13px; }
    .bio-callout-count { color: var(--green); font-size: 11.5px; font-weight: 600; white-space: nowrap; }
    .bio-callout-buyer { color: var(--text-2); font-size: 11.5px; margin-top: 2px; }
    .bio-checks { display: grid; grid-template-columns: 1fr 1fr; gap: 3px 14px; margin-top: 7px; padding: 0; list-style: none; }
    .bio-checks li { display: flex; align-items: flex-start; gap: 5px; font-size: 11.5px; line-height: 1.35; color: var(--text); cursor: default; }
    .bio-checks .mark { flex: none; font-weight: 700; color: var(--green); }
    .bio-checks li.fail .mark { color: var(--red); }
    .bio-callout.inactive { background: var(--amber-soft); border-color: #F2DDB4; }
    .bio-callout.inactive .bio-callout-title, .bio-callout.inactive .bio-callout-count { color: var(--amber); }
    .det-price-row { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
    .det-price { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }
    .det-change { font-size: 13px; font-weight: 600; margin-left: 8px; }
    .det-window { display: flex; align-items: center; gap: 12px; padding-left: 16px; border-left: 1px solid var(--line); }
    .det-window svg { width: 18px; height: 18px; color: var(--text-2); }
    .det-window-label { color: var(--text-2); font-size: 11.5px; }
    .det-window-value { font-weight: 700; font-size: 14px; }
    .scenarios { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 16px; }
    .scenario { padding: 0 12px; border-left: 1px solid var(--line); }
    .scenario:first-child { padding-left: 0; border-left: none; }
    .scenario-label { color: var(--text-2); font-size: 11.5px; }
    .scenario-value { margin-top: 4px; display: flex; align-items: baseline; gap: 7px; }
    .scenario-value strong { font-size: 16px; font-weight: 700; }
    .scenario-value span { font-size: 12.5px; font-weight: 600; }
    .decision { margin-top: 16px; }
    .decision-title { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 13.5px; }
    .decision-text { color: var(--text-2); font-size: 12px; margin-top: 5px; }
    .metric { text-align: center; }
    .metric:first-child { text-align: left; }

    /* CHART */
    .chart-head { display: flex; justify-content: space-between; align-items: center; }
    .chart-box { position: relative; height: 230px; margin-top: 10px; }
    .chart-box svg { width: 100%; height: 100%; display: block; }
    .chart-empty { position: absolute; inset: 0; display: grid; place-items: center; color: var(--text-3); font-size: 12.5px; text-align: center; }
    .chart-legend { display: flex; justify-content: center; gap: 22px; color: var(--text-2); font-size: 11.5px; margin-top: 2px; }
    .chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
    .lg-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--blue); }
    .lg-line { width: 18px; height: 2px; background: var(--blue-line); }

    /* POSITION */
    .pos-list { margin-top: 12px; }
    .pos-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; font-size: 12.5px; }
    .pos-row .k { color: var(--text-2); }
    .pos-row .v { font-weight: 500; }
    .pos-row .v.strong { font-weight: 700; }
    .pos-sep { height: 1px; background: var(--line); margin: 8px 8px; }
    .capital-input { width: 110px; text-align: right; border: 1px solid transparent; border-radius: 4px; padding: 1px 4px; font: inherit; font-weight: 500; color: var(--text); background: transparent; }
    .capital-input:hover { border-color: var(--line); }
    .capital-input:focus { outline: none; border-color: var(--blue); background: #fff; }

    /* RESEARCH STRIP */
    .research { display: flex; align-items: center; gap: 18px; padding: 13px 0; border-top: 1px solid var(--line); }
    .research .section-title { font-size: 13.5px; white-space: nowrap; }
    .research-link { display: flex; align-items: center; gap: 9px; flex: 1; min-width: 0; }
    .research-link svg { width: 15px; height: 15px; flex: none; color: var(--text-2); }
    .research-link a { color: var(--blue); text-decoration: underline; font-weight: 500; font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .research-meta { color: var(--text-2); font-size: 11.5px; white-space: nowrap; }

    /* OTHER TABS */
    .list-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    .list-table th { text-align: left; font-weight: 500; color: var(--text-2); font-size: 12px; padding: 8px; border-bottom: 1px solid var(--line); white-space: nowrap; }
    .list-table td { padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
    .list-table td.num, .list-table th.num { text-align: right; white-space: nowrap; }
    .list-table a { color: var(--blue); }
    .list-table a:hover { text-decoration: underline; }
    .wire-reason { color: var(--text-3); font-size: 11.5px; margin-top: 3px; }
"""

_BODY = r"""
    <header class="page-head">
      <div>
        <h1 class="page-title">Biotech M&amp;A Overnight Scanner</h1>
        <p class="page-sub">Find acquisition rumors, assess risk/reward, and capture overnight moves.</p>
      </div>
      <div class="head-right">
        <span id="live-pill" class="live-pill loading">Loading</span>
        <span id="last-update">Last update: —</span>
        <button id="btn-refresh" class="icon-btn" title="Refresh" onclick="loadScanner()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></svg>
        </button>
      </div>
    </header>

    <section class="kpi-strip">
      <div class="kpi">Active Candidates <strong id="kpi-active">—</strong></div>
      <div class="kpi">Actionable Setups <strong id="kpi-actionable">—</strong></div>
      <div class="kpi" title="Biotech rumors passing all 6 biotech checks at the current price">Actionable Biotech <strong id="kpi-biotech">—</strong></div>
      <div class="kpi">Win Rate <strong id="kpi-winrate">—</strong><span class="kpi-note" id="kpi-winrate-note"></span></div>
      <div class="kpi">Avg. Overnight Move <strong id="kpi-avgmove" class="pos">—</strong></div>
    </section>

    <nav class="tabs">
      <button class="tab active" data-tab="opportunities" onclick="switchTab('opportunities')">Opportunities</button>
      <button class="tab" data-tab="context" onclick="switchTab('context')">Market Context</button>
      <button class="tab" data-tab="performance" onclick="switchTab('performance')">Performance</button>
    </nav>

    <div id="error-banner" class="error-banner"></div>

    <!-- OPPORTUNITIES -->
    <section id="pane-opportunities" class="tab-pane active">
      <div class="panel-grid">
        <div class="cell">
          <h2 class="section-title">M&amp;A Opportunities (<span id="opp-count">0</span>)</h2>
          <table class="data-table opp-table" id="opp-table">
            <thead>
              <tr>
                <th style="width:28px;"></th>
                <th class="sortable" data-sort="ticker">Ticker<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="status_label">Status<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="entry_price">Entry<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="upside">Upside<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="downside_pct">Downside<span class="sort-ind">&#8645;</span></th>
                <th class="sortable" data-sort="ev_pct">EV<span class="sort-ind">&#8645;</span></th>
              </tr>
            </thead>
            <tbody id="opp-body">
              <tr><td colspan="7" class="table-empty">Loading opportunities…</td></tr>
            </tbody>
          </table>
        </div>

        <div class="cell right" id="detail-panel">
          <div class="muted">Select an opportunity to see its scenarios.</div>
        </div>

        <div class="row-divider"></div>

        <div class="cell">
          <div class="chart-head">
            <h2 class="section-title" id="chart-title">Price &amp; Overnight Scenarios</h2>
            <div class="seg" id="range-seg">
              <button class="active" data-range="1D" onclick="setRange('1D')">1D</button>
              <button data-range="5D" onclick="setRange('5D')">5D</button>
              <button data-range="1M" onclick="setRange('1M')">1M</button>
            </div>
          </div>
          <div class="chart-box">
            <svg id="chart-svg" preserveAspectRatio="none"></svg>
            <div class="chart-empty" id="chart-empty">Loading price history…</div>
          </div>
          <div class="chart-legend">
            <span><i class="lg-dot"></i>Price</span>
            <span><i class="lg-line"></i>VWAP</span>
          </div>
        </div>

        <div class="cell right">
          <h2 class="section-title">Overnight Position (Simulation)</h2>
          <div class="pos-list" id="position-panel"></div>
        </div>
      </div>

      <div class="research">
        <h2 class="section-title">Research &amp; Evidence</h2>
        <div class="research-link" id="research-link"><span class="muted">No related wire headlines yet.</span></div>
        <span class="research-meta" id="research-meta"></span>
        <a class="icon-btn" id="research-open" href="#" target="_blank" rel="noopener" title="Open source article" style="visibility:hidden;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </div>
    </section>

    <!-- MARKET CONTEXT -->
    <section id="pane-context" class="tab-pane">
      <div class="pane-section">
        <h2 class="section-title">M&amp;A Wire Headlines (<span id="wire-count">0</span>)</h2>
        <p class="pane-note">Google News RSS sweep filtered for hard M&amp;A phrases. Only leaks under 4 hours old are actionable.</p>
        <table class="list-table">
          <thead>
            <tr><th>Headline</th><th>Ticker</th><th>Source</th><th>Age</th><th>Status</th></tr>
          </thead>
          <tbody id="wire-body"></tbody>
        </table>
      </div>
    </section>

    <!-- PERFORMANCE -->
    <section id="pane-performance" class="tab-pane">
      <div class="pane-section">
        <h2 class="section-title">PE All-Cash Leak Strategy</h2>
        <p class="pane-note" id="perf-period"></p>
        <table class="list-table">
          <thead>
            <tr><th>Year</th><th class="num">Filtered Strategy</th><th class="num">Unfiltered (All Leaks)</th><th class="num">Idle $SGOV</th></tr>
          </thead>
          <tbody id="perf-body"></tbody>
        </table>
      </div>
      <div class="pane-section">
        <h2 class="section-title">Biopharma 6-Gate Backtest</h2>
        <p class="pane-note" id="bio-period"></p>
        <div class="stat-grid" id="bio-stats"></div>
      </div>
    </section>
"""

_SCRIPT = r"""
  const STATE = {
    data: null,
    selected: null,
    sortKey: null,
    sortDir: 1,
    range: '1D',
    capital: 100000,
    lastUpdate: null,
    historyToken: 0,
    history: null,
  };

  const BIO_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6.5L4.6 18.6A1.6 1.6 0 0 0 6 21h12a1.6 1.6 0 0 0 1.4-2.4L14 9.5V3"/><path d="M7.5 15h9"/></svg>';

  function upsideHtml(o) {
    if (!isNum(o.upside_low_pct)) return '<span class="muted">—</span>';
    if (isNum(o.upside_high_pct)) {
      return `<span class="${signClass(o.upside_low_pct)}">${fmtPct(o.upside_low_pct)} – ${Math.abs(o.upside_high_pct).toFixed(1)}%</span>`;
    }
    return `<span class="${signClass(o.upside_low_pct)}">${fmtPct(o.upside_low_pct)}</span>`;
  }

  async function loadScanner() {
    const btn = document.getElementById('btn-refresh');
    const pill = document.getElementById('live-pill');
    btn.classList.add('spinning');
    pill.className = 'live-pill loading';
    pill.textContent = 'Updating';
    try {
      const resp = await fetch('/api/scanner');
      if (!resp.ok) throw new Error(`Scanner request failed (HTTP ${resp.status})`);
      STATE.data = await resp.json();
      STATE.lastUpdate = Date.now();
      document.getElementById('error-banner').style.display = 'none';
      pill.className = 'live-pill';
      pill.textContent = 'Live';
      const opps = STATE.data.opportunities || [];
      if (!STATE.selected || !opps.some((o) => o.ticker === STATE.selected)) {
        STATE.selected = opps.length ? opps[0].ticker : null;
      }
      renderAll();
    } catch (err) {
      pill.className = 'live-pill offline';
      pill.textContent = 'Offline';
      const banner = document.getElementById('error-banner');
      banner.textContent = `Could not load scanner data: ${err.message}`;
      banner.style.display = 'block';
    } finally {
      btn.classList.remove('spinning');
    }
  }

  function renderAll() {
    renderKpis();
    renderTable();
    renderDetail();
    renderPosition();
    renderResearch();
    renderWires();
    renderPerformance();
    loadHistory();
  }

  function renderKpis() {
    const k = STATE.data.kpis || {};
    document.getElementById('kpi-active').textContent = k.active_candidates ?? '—';
    document.getElementById('kpi-actionable').textContent = k.actionable_setups ?? '—';
    const bioKpi = document.getElementById('kpi-biotech');
    bioKpi.textContent = k.actionable_biotech ?? '—';
    bioKpi.classList.toggle('pos', (k.actionable_biotech || 0) > 0);
    document.getElementById('kpi-winrate').textContent = isNum(k.backtest_win_rate_pct) ? k.backtest_win_rate_pct.toFixed(1) + '%' : '—';
    document.getElementById('kpi-winrate-note').textContent = k.backtest_period_label ? `(${k.backtest_period_label})` : '';
    document.getElementById('kpi-avgmove').textContent = fmtPct(k.avg_overnight_move_pct);
  }

  function sortValue(o, key) {
    if (key === 'upside') return isNum(o.upside_high_pct) ? o.upside_high_pct : o.upside_low_pct;
    return o[key];
  }

  function renderTable() {
    const opps = sortRows(STATE.data.opportunities || [], STATE, sortValue);
    document.getElementById('opp-count').textContent = opps.length;
    paintSortHeaders(document.getElementById('opp-table'), STATE);
    const body = document.getElementById('opp-body');
    if (!opps.length) {
      body.innerHTML = '<tr><td colspan="7" class="table-empty">No candidates on the watchlist.</td></tr>';
      return;
    }
    body.innerHTML = opps.map((o) => `
      <tr class="clickable${o.ticker === STATE.selected ? ' selected' : ''}" data-ticker="${esc(o.ticker)}">
        <td><span class="radio"></span></td>
        <td class="tkr">${esc(o.ticker)}${biotechTag(o.biotech_signal)}</td>
        <td><span class="pill ${esc(o.status_key)}" title="${esc(o.status_hint)}">${esc(o.status_label)}</span></td>
        <td>${fmtPx(o.entry_price)}</td>
        <td>${upsideHtml(o)}</td>
        <td class="${signClass(o.downside_pct)}">${fmtPct(o.downside_pct)}</td>
        <td class="${signClass(o.ev_pct)}">${fmtPct(o.ev_pct)}</td>
      </tr>`).join('');
    body.querySelectorAll('tr[data-ticker]').forEach((tr) => {
      tr.addEventListener('click', () => selectTicker(tr.dataset.ticker));
    });
  }

  function selectedOpp() {
    return (STATE.data?.opportunities || []).find((o) => o.ticker === STATE.selected) || null;
  }

  function selectTicker(ticker) {
    if (ticker === STATE.selected) return;
    STATE.selected = ticker;
    renderTable();
    renderDetail();
    renderPosition();
    renderResearch();
    loadHistory();
  }

  function scenarioCell(label, price, pct) {
    return `
      <div class="scenario">
        <div class="scenario-label">${label}</div>
        <div class="scenario-value">
          <strong>${isNum(price) ? fmtPxShort(price) : '<span class="muted">—</span>'}</strong>
          ${isNum(pct) ? `<span class="${signClass(pct)}">${fmtPct(pct)}</span>` : '<span class="muted" style="font-weight:400;font-size:11.5px;">Not modeled</span>'}
        </div>
      </div>`;
  }

  function biotechTag(s) {
    if (!s) return '';
    const text = s.is_actionable ? 'Biotech · Actionable' : `Biotech · ${s.gates_passed}/${s.gates_total}`;
    return `<span class="bio-tag${s.is_actionable ? '' : ' inactive'}" title="${esc(s.label)}: ${esc(s.gates_passed)}/${esc(s.gates_total)} biotech checks passed">${BIO_ICON}${esc(text)}</span>`;
  }

  function biotechCallout(s) {
    if (!s) return '';
    const checks = (s.checks || []).map((c) => `
      <li class="${c.passed ? '' : 'fail'}" title="${esc(c.detail)}"><span class="mark">${c.passed ? '&#10003;' : '&#10005;'}</span>${esc(c.label)}</li>`).join('');
    return `
      <div class="bio-callout${s.is_actionable ? '' : ' inactive'}">
        <div class="bio-callout-head">
          <div class="bio-callout-title">${BIO_ICON}${esc(s.label)}</div>
          <div class="bio-callout-count">${esc(s.gates_passed)}/${esc(s.gates_total)} biotech checks passed</div>
        </div>
        ${s.buyer ? `<div class="bio-callout-buyer">Buyer: ${esc(s.buyer)}</div>` : ''}
        <ul class="bio-checks">${checks}</ul>
      </div>`;
  }

  function renderDetail() {
    const panel = document.getElementById('detail-panel');
    const o = selectedOpp();
    if (!o) {
      panel.innerHTML = '<div class="muted">Select an opportunity to see its scenarios.</div>';
      return;
    }
    const windowLabel = o.rumored_window ? 'Rumored Window' : 'Leak Broke';
    const windowValue = o.rumored_window || fmtLeakTime(o.leak_timestamp_est);
    const rr = isNum(o.reward_to_risk) ? `1 : ${o.reward_to_risk.toFixed(1)}` : '—';
    const liqColor = o.liquidity_label === 'High' ? 'var(--green)' : o.liquidity_label === 'Medium' ? 'var(--amber)' : 'var(--red)';
    panel.innerHTML = `
      <div class="det-head">
        <div>
          <div class="det-ticker">${esc(o.ticker)}</div>
          <div class="det-company">${esc(o.company_name)}</div>
        </div>
        <span class="pill ${esc(o.status_key)}" title="${esc(o.status_hint)}">${esc(o.status_label)}</span>
      </div>
      ${biotechCallout(o.biotech_signal)}
      <div class="det-price-row">
        <div>
          <span class="det-price">${fmtPx(o.entry_price)}</span>
          <span class="det-change ${signClass(o.change_pct)}">${fmtPct(o.change_pct)}</span>
        </div>
        <div class="det-window">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/></svg>
          <div>
            <div class="det-window-label">${windowLabel}</div>
            <div class="det-window-value">${esc(windowValue)}</div>
          </div>
        </div>
      </div>
      <div class="scenarios">
        ${scenarioCell('Base Offer', o.base_offer, o.upside_low_pct)}
        ${scenarioCell('Higher Offer', o.higher_offer, o.upside_high_pct)}
        ${scenarioCell('Failure / Floor', o.floor_price, o.downside_pct)}
      </div>
      <div class="decision">
        <div class="decision-title">Trade Decision <span class="pill ${esc(o.decision_key)}">${esc(o.decision_label)}</span></div>
        <div class="decision-text">${esc(o.decision_text)}</div>
      </div>
      <div class="metrics">
        <div class="metric"><div class="metric-label">EV (Est.)</div><div class="metric-value ${signClass(o.ev_pct)}">${fmtPct(o.ev_pct)}</div></div>
        <div class="metric"><div class="metric-label">Risk/Reward</div><div class="metric-value">${rr}</div></div>
        <div class="metric"><div class="metric-label">Liquidity</div><div class="metric-value" title="10% of extended-hours dollar volume: ${fmtUsdPlain(o.max_clip_usd)}"><span style="color:${liqColor};">&#9679;</span> ${esc(o.liquidity_label)}</div></div>
        <div class="metric"><div class="metric-label">Catalyst</div><div class="metric-value">${esc(o.catalyst)}</div></div>
      </div>
      <a class="btn-primary" href="${esc(o.analysis_url)}">
        View Full Analysis
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </a>`;
  }

  function renderPosition() {
    const panel = document.getElementById('position-panel');
    const o = selectedOpp();
    if (!o) { panel.innerHTML = ''; return; }
    const entry = o.entry_price;
    const exit = o.base_offer;
    const fail = o.floor_price;
    const shares = isNum(entry) && entry > 0 ? Math.floor(STATE.capital / entry) : null;
    const target = isNum(shares) && isNum(exit) ? shares * (exit - entry) : null;
    const loss = isNum(shares) && isNum(fail) ? shares * (fail - entry) : null;
    panel.innerHTML = `
      <div class="pos-row"><span class="k">Capital</span>
        <input class="capital-input" id="capital-input" value="${fmtUsdPlain(STATE.capital)}" title="Edit simulated capital" /></div>
      <div class="pos-row"><span class="k">Entry</span><span class="v">${fmtPx(entry)}</span></div>
      <div class="pos-row"><span class="k">Exit (AM)</span><span class="v">${fmtPx(exit)}</span></div>
      <div class="pos-row"><span class="k">Failure</span><span class="v">${fmtPx(fail)}</span></div>
      <div class="pos-sep"></div>
      <div class="pos-row"><span class="k">Position Size</span><span class="v">${isNum(shares) ? shares.toLocaleString('en-US') + ' shares' : '—'}</span></div>
      <div class="pos-row"><span class="k">Target P&amp;L</span><span class="v strong ${signClass(target)}">${fmtUsd(target)}</span></div>
      <div class="pos-row"><span class="k">Scenario Loss</span><span class="v strong ${signClass(loss)}">${fmtUsd(loss)}</span></div>`;
    const input = document.getElementById('capital-input');
    const commit = () => {
      const val = parseFloat(input.value.replace(/[^0-9.]/g, ''));
      if (isNum(val) && val > 0) STATE.capital = val;
      renderPosition();
    };
    input.addEventListener('focus', () => { input.value = String(STATE.capital); input.select(); });
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); if (e.key === 'Escape') { input.value = String(STATE.capital); input.blur(); } });
  }

  function renderResearch() {
    const wires = STATE.data.wire_items || [];
    const o = selectedOpp();
    const related = wires.filter((w) => o && w.detected_ticker === o.ticker);
    const pick = (related.length ? related : wires)
      .slice()
      .sort((a, b) => (a.leak_age_hours ?? 1e9) - (b.leak_age_hours ?? 1e9))[0];
    const linkBox = document.getElementById('research-link');
    const meta = document.getElementById('research-meta');
    const open = document.getElementById('research-open');
    if (!pick) {
      linkBox.innerHTML = '<span class="muted">No related wire headlines yet.</span>';
      meta.textContent = '';
      open.style.visibility = 'hidden';
      return;
    }
    linkBox.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="14 3 14 9 20 9"/></svg>
      <a href="${esc(pick.link)}" target="_blank" rel="noopener" title="${esc(pick.title)}">${esc(pick.title)}</a>`;
    meta.textContent = `${shortAge(pick.leak_age_human)} · Source: ${pick.source || 'Unknown'}`;
    open.href = pick.link || '#';
    open.style.visibility = pick.link ? 'visible' : 'hidden';
  }

  function renderWires() {
    const wires = (STATE.data.wire_items || []).slice().sort((a, b) => (a.leak_age_hours ?? 1e9) - (b.leak_age_hours ?? 1e9));
    document.getElementById('wire-count').textContent = wires.length;
    const body = document.getElementById('wire-body');
    if (!wires.length) {
      body.innerHTML = '<tr><td colspan="5" class="table-empty">No M&amp;A wire headlines matched the filter.</td></tr>';
      return;
    }
    body.innerHTML = wires.map((w) => {
      const status = w.is_actionable_trigger
        ? '<span class="pill open">Actionable</span>'
        : w.is_stale_leak ? '<span class="pill">Stale</span>' : '<span class="pill review">Filtered</span>';
      const reason = !w.is_actionable_trigger && w.rejection_reasons && w.rejection_reasons.length
        ? `<div class="wire-reason">${esc(w.rejection_reasons[0])}</div>` : '';
      return `
        <tr>
          <td><a href="${esc(w.link)}" target="_blank" rel="noopener">${esc(w.title)}</a>${reason}</td>
          <td class="tkr">${w.detected_ticker ? esc(w.detected_ticker) : '<span class="muted">—</span>'}</td>
          <td style="white-space:nowrap;">${esc(w.source)}</td>
          <td style="white-space:nowrap;">${esc(shortAge(w.leak_age_human))}</td>
          <td>${status}</td>
        </tr>`;
    }).join('');
  }

  function renderPerformance() {
    const p = STATE.data.performance || {};
    document.getElementById('perf-period').textContent = p.period_label || '';
    const rows = (p.annual_pnl_table || []).map((r) => `
      <tr><td>${esc(r.year)}</td>
        <td class="num pos">${fmtUsd(r.filtered_strategy_usd)}</td>
        <td class="num">${fmtUsd(r.unfiltered_all_leaks_usd)}</td>
        <td class="num">${fmtUsd(r.idle_sgov_usd)}</td></tr>`);
    rows.push(`
      <tr><td><strong>3-Year Total</strong></td>
        <td class="num pos"><strong>${fmtUsd(p.cumulative_3yr_filtered_usd)}</strong></td>
        <td class="num"><strong>${fmtUsd(p.cumulative_3yr_unfiltered_usd)}</strong></td>
        <td class="num"><strong>${fmtUsd(p.cumulative_3yr_sgov_usd)}</strong></td></tr>`);
    document.getElementById('perf-body').innerHTML = rows.join('');

    const b = p.biopharma_filtered || {};
    document.getElementById('bio-period').textContent = p.biopharma_period || '';
    const stats = [
      ['Qualified Events', b.qualified_events ?? '—'],
      ['Win Rate', isNum(b.win_rate_pct) ? b.win_rate_pct.toFixed(1) + '%' : '—'],
      ['Median Return / Trade', fmtPct(b.median_return_per_trade_pct, 2)],
      ['Worst Loss', fmtPct(b.worst_loss_pct, 2)],
      ['Wins / Losses', `${b.wins ?? '—'} / ${b.losses_or_walkaways ?? '—'}`],
      ['Winner Median Spread', fmtPct(b.winner_median_spread_pct, 2)],
      ['Avg Hold', isNum(b.avg_hold_trading_days) ? b.avg_hold_trading_days + ' trading days' : '—'],
      ['Cumulative IRA P&L ($100k)', fmtUsd(b.cumulative_ira_pnl_100k_clip_usd)],
    ];
    document.getElementById('bio-stats').innerHTML = stats.map(([k, v]) =>
      `<div class="stat"><div class="stat-label">${esc(k)}</div><div class="stat-value">${esc(v)}</div></div>`).join('');
  }

  function setRange(r) {
    if (r === STATE.range) return;
    STATE.range = r;
    document.querySelectorAll('#range-seg button').forEach((b) => b.classList.toggle('active', b.dataset.range === r));
    loadHistory();
  }

  async function loadHistory() {
    const o = selectedOpp();
    const empty = document.getElementById('chart-empty');
    const svg = document.getElementById('chart-svg');
    document.getElementById('chart-title').textContent = o ? `${o.ticker} — Price & Overnight Scenarios` : 'Price & Overnight Scenarios';
    if (!o) { svg.innerHTML = ''; empty.textContent = 'Select an opportunity.'; empty.style.display = 'grid'; return; }
    const token = ++STATE.historyToken;
    empty.textContent = 'Loading price history…';
    empty.style.display = 'grid';
    svg.innerHTML = '';
    STATE.history = null;
    try {
      const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(o.ticker)}&range=${STATE.range}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const hist = await resp.json();
      if (token !== STATE.historyToken) return;
      if (!hist.points || hist.points.length < 2) {
        empty.textContent = 'Price history is unavailable for this ticker right now.';
        return;
      }
      empty.style.display = 'none';
      STATE.history = { points: hist.points, entry: o.entry_price };
      drawChart(hist.points, o.entry_price);
    } catch (err) {
      if (token !== STATE.historyToken) return;
      empty.textContent = `Could not load price history (${err.message}).`;
    }
  }

  function niceStep(span, target) {
    const raw = span / Math.max(1, target);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  }

  function drawChart(points, entry) {
    const svg = document.getElementById('chart-svg');
    const box = svg.getBoundingClientRect();
    const W = Math.max(320, box.width), H = Math.max(160, box.height);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const pad = { l: 46, r: 10, t: 8, b: 24 };
    const vals = points.flatMap((p) => [p.price, p.vwap]);
    if (isNum(entry)) vals.push(entry);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
    const step = niceStep(hi - lo, 4);
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;
    const x = (i) => pad.l + (i / (points.length - 1)) * (W - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
    const decimals = step < 1 ? 2 : 0;

    let out = `<defs><linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2F6BEA" stop-opacity="0.18"/><stop offset="100%" stop-color="#2F6BEA" stop-opacity="0.02"/></linearGradient></defs>`;
    const entryY = isNum(entry) && entry >= lo && entry <= hi ? y(entry) : null;
    for (let v = lo; v <= hi + step / 2; v += step) {
      out += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="#EEF0F3"/>`;
      if (entryY === null || Math.abs(y(v) - entryY) > 14) {
        out += `<text x="${pad.l - 8}" y="${y(v) + 3.5}" text-anchor="end" font-size="10.5" fill="#4B5563">${v.toFixed(decimals)}</text>`;
      }
    }

    const times = points.map((p) => new Date(p.t));
    const tickCount = Math.min(6, points.length);
    const fmtTick = (d) => {
      const opts = { timeZone: 'America/New_York' };
      if (STATE.range === '1D') return d.toLocaleTimeString('en-US', { ...opts, hour: 'numeric', minute: d.getMinutes() ? '2-digit' : undefined });
      return d.toLocaleDateString('en-US', { ...opts, month: 'short', day: 'numeric' });
    };
    let prevTick = null;
    for (let k = 0; k < tickCount; k++) {
      const i = Math.round((k / Math.max(1, tickCount - 1)) * (points.length - 1));
      const label = fmtTick(times[i]);
      if (label === prevTick) continue;
      prevTick = label;
      const anchor = k === 0 ? 'start' : k === tickCount - 1 ? 'end' : 'middle';
      out += `<text x="${x(i)}" y="${H - 6}" text-anchor="${anchor}" font-size="10.5" fill="#4B5563">${esc(label)}</text>`;
    }

    const pricePath = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join('');
    const vwapPath = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.vwap).toFixed(1)}`).join('');
    const baseY = y(lo);
    out += `<path d="${pricePath}L${x(points.length - 1).toFixed(1)},${baseY}L${x(0).toFixed(1)},${baseY}Z" fill="url(#area-grad)"/>`;
    out += `<path d="${vwapPath}" fill="none" stroke="#9DB8F3" stroke-width="1.5"/>`;
    out += `<path d="${pricePath}" fill="none" stroke="#2F6BEA" stroke-width="1.6" stroke-linejoin="round"/>`;

    if (entryY !== null) {
      const ey = entryY;
      out += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${ey}" y2="${ey}" stroke="#8A93A3" stroke-dasharray="4 4"/>`;
      out += `<rect x="2" y="${ey - 8}" width="${pad.l - 6}" height="16" rx="3" fill="#E8EFFD"/>`;
      out += `<text x="${(pad.l - 4) / 2 + 1}" y="${ey + 3.5}" text-anchor="middle" font-size="10.5" font-weight="600" fill="#2F6BEA">${entry.toFixed(2)}</text>`;
    }
    svg.innerHTML = out;
  }

  function onTabSwitched(name) {
    if (name === 'opportunities' && STATE.data) loadHistory();
  }

  function tickLastUpdate() {
    const el = document.getElementById('last-update');
    el.textContent = STATE.lastUpdate ? `Last update: ${relativeAgo(STATE.lastUpdate)}` : 'Last update: —';
  }

  bindSortHeaders(document.getElementById('opp-table'), STATE, () => STATE.data && renderTable());

  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (STATE.history) drawChart(STATE.history.points, STATE.history.entry); }, 200);
  });

  setInterval(tickLastUpdate, 1000);
  setInterval(loadScanner, 5 * 60 * 1000);
  window.addEventListener('DOMContentLoaded', loadScanner);
"""

SCANNER_HTML = render_page(
    title="Biotech M&amp;A Overnight Scanner",
    active="scanner",
    styles=_STYLES,
    body=_BODY,
    script=_SCRIPT,
)
