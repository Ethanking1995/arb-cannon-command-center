"""
Arb Cannon: M&A Wire & EDGAR Research UI (research_ui.py)

Light research page served at GET /research. Runs POST /api/scan and shows the
four scan stages, every M&A wire headline with its gate audit, and the watchlist
net-debt / SEC EDGAR 8-K audit.
"""

from ui_shell import render_page

_STYLES = r"""
    .stage-strip { display: grid; grid-template-columns: repeat(4, 1fr); padding: 11px 0; border-bottom: 1px solid var(--line); }
    .stage { display: flex; gap: 9px; padding: 0 14px; border-left: 1px solid var(--line); min-width: 0; }
    .stage:first-child { border-left: none; padding-left: 2px; }
    .stage-dot { width: 16px; height: 16px; flex: none; margin-top: 1px; border-radius: 50%; border: 1.5px solid #C5CBD5; display: grid; place-items: center; }
    .stage.active .stage-dot { border-color: var(--blue); border-top-color: transparent; animation: spin 0.8s linear infinite; }
    .stage.done .stage-dot { border: none; background: var(--green); }
    .stage.done .stage-dot::after { content: ''; width: 4px; height: 8px; border: solid #fff; border-width: 0 2px 2px 0; transform: translateY(-1px) rotate(45deg); }
    .stage-label { font-weight: 600; font-size: 12px; }
    .stage.pending .stage-label { color: var(--text-3); }
    .stage-sub { color: var(--text-3); font-size: 11px; margin-top: 2px; }
    .headline a { color: var(--text); font-weight: 500; white-space: normal; }
    .headline a:hover { color: var(--blue); text-decoration: underline; }
    tr.expand-row td { background: var(--bg-subtle); padding: 10px 14px 12px; white-space: normal; }
    .expand-caret { color: var(--text-3); font-size: 10px; margin-right: 6px; display: inline-block; transition: transform 0.15s; }
    tr.open .expand-caret { transform: rotate(90deg); }
    .chip.gate { background: var(--red-soft); color: var(--red); }
    .chip.ok { background: var(--green-soft); color: var(--green); }
    .ext-link { color: var(--blue); font-weight: 500; }
    .ext-link:hover { text-decoration: underline; }
"""

_BODY = r"""
    <header class="page-head">
      <div>
        <h1 class="page-title">M&amp;A Wire &amp; EDGAR Research</h1>
        <p class="page-sub">Sweep M&amp;A news wires, apply the 4-hour freshness gate, and check SEC EDGAR for definitive merger filings.</p>
      </div>
      <div class="head-right">
        <span id="live-pill" class="live-pill loading">Scanning</span>
        <span id="last-update">Last scan: —</span>
        <button id="btn-scan" class="btn-secondary" onclick="runScan()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></svg>
          Run scan
        </button>
      </div>
    </header>

    <section class="kpi-strip">
      <div class="kpi">Fresh Triggers <strong id="kpi-triggers" class="pos">—</strong></div>
      <div class="kpi">Filtered Headlines <strong id="kpi-filtered">—</strong></div>
      <div class="kpi">Fresh Watchlist Leaks <strong id="kpi-fresh-wl">—</strong></div>
      <div class="kpi">Stale Watchlist <strong id="kpi-stale-wl">—</strong></div>
      <div class="kpi">Deals Announced (8-K) <strong id="kpi-8k">—</strong></div>
    </section>

    <section class="stage-strip" id="stage-strip">
      <div class="stage pending" data-stage="1"><span class="stage-dot"></span><div><div class="stage-label">RSS wire sweep</div><div class="stage-sub" data-sub>Google News, last 48 hours</div></div></div>
      <div class="stage pending" data-stage="2"><span class="stage-dot"></span><div><div class="stage-label">Freshness &amp; headline gate</div><div class="stage-sub" data-sub>&le; 4h old, Tier-1 desk, hard M&amp;A phrase</div></div></div>
      <div class="stage pending" data-stage="3"><span class="stage-dot"></span><div><div class="stage-label">SEC EDGAR 8-K check</div><div class="stage-sub" data-sub>Form 8-K Item 1.01 filings</div></div></div>
      <div class="stage pending" data-stage="4"><span class="stage-dot"></span><div><div class="stage-label">Net debt &amp; quotes</div><div class="stage-sub" data-sub>10-Q waterfall, extended-hours price</div></div></div>
    </section>

    <nav class="tabs">
      <button class="tab active" data-tab="wires" onclick="switchTab('wires')">Wire Headlines<span class="tab-count" id="tab-wire-count"></span></button>
      <button class="tab" data-tab="watchlist" onclick="switchTab('watchlist')">Watchlist Audit<span class="tab-count" id="tab-wl-count"></span></button>
    </nav>

    <div id="error-banner" class="error-banner"></div>

    <section id="pane-wires" class="tab-pane active">
      <div class="pane-section">
        <div class="section-head">
          <h2 class="section-title">M&amp;A Wire Headlines</h2>
          <div class="seg" id="wire-filter">
            <button class="active" data-filter="all" onclick="setWireFilter('all')">All</button>
            <button data-filter="actionable" onclick="setWireFilter('actionable')">Actionable</button>
            <button data-filter="filtered" onclick="setWireFilter('filtered')">Filtered</button>
          </div>
        </div>
        <p class="pane-note">Only headlines under 4 hours old from a Tier-1 desk with a hard M&amp;A phrase are actionable. Click a row to see which gates it failed.</p>
        <table class="data-table" id="wire-table">
          <thead>
            <tr>
              <th>Headline</th>
              <th class="sortable" data-sort="detected_ticker">Ticker<span class="sort-ind">&#8645;</span></th>
              <th class="sortable" data-sort="source">Source<span class="sort-ind">&#8645;</span></th>
              <th class="sortable" data-sort="published_iso">Published<span class="sort-ind">&#8645;</span></th>
              <th class="sortable" data-sort="leak_age_hours">Age<span class="sort-ind">&#8645;</span></th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="wire-body"><tr><td colspan="6" class="table-empty">Running scan…</td></tr></tbody>
        </table>
      </div>
    </section>

    <section id="pane-watchlist" class="tab-pane">
      <div class="panel-grid">
        <div class="cell">
          <h2 class="section-title">Watchlist Audit (<span id="wl-count">0</span>)</h2>
          <table class="data-table" id="wl-table">
            <thead>
              <tr>
                <th style="width:28px;"></th>
                <th class="sortable" data-sort="ticker">Ticker<span class="sort-ind">&#8645;</span></th>
                <th>Buyer</th>
                <th class="sortable" data-sort="leak_age_hours">Leak Age<span class="sort-ind">&#8645;</span></th>
                <th class="sortable num" data-sort="gross_spread_pct">Spread<span class="sort-ind">&#8645;</span></th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="wl-body"><tr><td colspan="6" class="table-empty">Running scan…</td></tr></tbody>
          </table>
        </div>
        <div class="cell right" id="wl-detail"><div class="muted">Select a watchlist name to see its audit.</div></div>
      </div>
    </section>
"""

_SCRIPT = r"""
  const STATE = {
    data: null,
    wireFilter: 'all',
    wireSort: { sortKey: 'leak_age_hours', sortDir: 1 },
    wlSort: { sortKey: null, sortDir: 1 },
    expanded: new Set(),
    selected: null,
    lastScan: null,
    elapsedMs: null,
    stageTimer: null,
  };

  function setStage(active) {
    document.querySelectorAll('#stage-strip .stage').forEach((el) => {
      const n = Number(el.dataset.stage);
      el.className = 'stage ' + (n < active ? 'done' : n === active ? 'active' : 'pending');
    });
  }

  function setStageSub(n, text) {
    const el = document.querySelector(`#stage-strip .stage[data-stage="${n}"] [data-sub]`);
    if (el) el.textContent = text;
  }

  async function runScan() {
    const btn = document.getElementById('btn-scan');
    const pill = document.getElementById('live-pill');
    btn.disabled = true;
    btn.classList.add('spinning');
    pill.className = 'live-pill loading';
    pill.textContent = 'Scanning';
    let stage = 1;
    setStage(stage);
    clearInterval(STATE.stageTimer);
    STATE.stageTimer = setInterval(() => { if (stage < 4) setStage(++stage); }, 1200);
    const started = performance.now();
    try {
      const resp = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_live_network: true }),
      });
      if (!resp.ok) throw new Error(`Scan request failed (HTTP ${resp.status})`);
      STATE.data = await resp.json();
      STATE.elapsedMs = performance.now() - started;
      STATE.lastScan = Date.now();
      clearInterval(STATE.stageTimer);
      setStage(5);
      document.getElementById('error-banner').style.display = 'none';
      pill.className = 'live-pill';
      pill.textContent = 'Live';
      const wl = STATE.data.watchlist || [];
      if (!STATE.selected || !wl.some((w) => w.ticker === STATE.selected)) {
        STATE.selected = wl.length ? wl[0].ticker : null;
      }
      renderAll();
    } catch (err) {
      clearInterval(STATE.stageTimer);
      setStage(0);
      pill.className = 'live-pill offline';
      pill.textContent = 'Offline';
      const banner = document.getElementById('error-banner');
      banner.textContent = `Could not run the scan: ${err.message}`;
      banner.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.classList.remove('spinning');
      tickLastScan();
    }
  }

  function renderAll() {
    const wires = STATE.data.wire_items || [];
    const wl = STATE.data.watchlist || [];
    const actionable = wires.filter((w) => w.is_actionable_trigger).length;
    const freshWl = wl.filter((w) => !w.is_stale_leak).length;
    const filed = wl.filter((w) => w.edgar_8k && w.edgar_8k.has_recent_item_1_01).length;
    const priced = wl.filter((w) => isNum(w.implied_deal_price)).length;

    document.getElementById('kpi-triggers').textContent = actionable;
    document.getElementById('kpi-filtered').textContent = wires.length - actionable;
    document.getElementById('kpi-fresh-wl').textContent = freshWl;
    document.getElementById('kpi-stale-wl').textContent = wl.length - freshWl;
    document.getElementById('kpi-8k').textContent = filed;
    document.getElementById('tab-wire-count').textContent = wires.length;
    document.getElementById('tab-wl-count').textContent = wl.length;

    setStageSub(1, `${wires.length} M&A headline${wires.length === 1 ? '' : 's'} matched`);
    setStageSub(2, `${actionable} actionable, ${wires.length - actionable} filtered`);
    setStageSub(3, `${filed} of ${wl.length} watchlist names have a filed 8-K`);
    setStageSub(4, `${priced} of ${wl.length} names priced against a rumored deal`);

    renderWires();
    renderWatchlist();
    renderWlDetail();
  }

  function setWireFilter(f) {
    STATE.wireFilter = f;
    document.querySelectorAll('#wire-filter button').forEach((b) => b.classList.toggle('active', b.dataset.filter === f));
    renderWires();
  }

  function wireStatusPill(w) {
    if (w.is_actionable_trigger) return '<span class="pill go">Actionable</span>';
    if (w.is_stale_leak) return '<span class="pill" title="Older than the 4-hour actionable window">Stale</span>';
    return '<span class="pill review">Filtered</span>';
  }

  const wireKey = (w) => w.link || w.title;

  function gateChips(failed) {
    const unique = [...new Set(failed || [])];
    if (!unique.length) return '<span class="chip ok">All gates passed</span>';
    return unique.map((g) => `<span class="chip gate">${esc(gateLabel(g))}</span>`).join('');
  }

  function renderWires() {
    const table = document.getElementById('wire-table');
    paintSortHeaders(table, STATE.wireSort);
    let wires = STATE.data.wire_items || [];
    if (STATE.wireFilter === 'actionable') wires = wires.filter((w) => w.is_actionable_trigger);
    if (STATE.wireFilter === 'filtered') wires = wires.filter((w) => !w.is_actionable_trigger);
    wires = sortRows(wires, STATE.wireSort, (w, k) => w[k]);
    const body = document.getElementById('wire-body');
    if (!wires.length) {
      body.innerHTML = '<tr><td colspan="6" class="table-empty">No headlines match this filter.</td></tr>';
      return;
    }
    body.innerHTML = wires.map((w) => {
      const key = wireKey(w);
      const open = STATE.expanded.has(key);
      const chips = (w.factual_keyword_tags || []).map((t) => `<span class="chip">${esc(String(t).replace(/^\[|\]$/g, ''))}</span>`).join('');
      const gates = gateChips(w.failed_gates);
      const reasons = (w.rejection_reasons || []).map((r) => `<li>${esc(r)}</li>`).join('');
      return `
        <tr class="clickable${open ? ' open' : ''}" data-key="${esc(key)}">
          <td class="wrap headline"><span class="expand-caret">&#9654;</span><a href="${esc(w.link)}" target="_blank" rel="noopener">${esc(w.title)}</a><div>${chips}</div></td>
          <td class="tkr">${w.detected_ticker ? esc(w.detected_ticker) : '<span class="muted">—</span>'}</td>
          <td>${esc(w.source)}</td>
          <td>${esc(fmtLeakTime(w.published_at))}</td>
          <td>${esc(shortAge(w.leak_age_human))}</td>
          <td>${wireStatusPill(w)}</td>
        </tr>
        ${open ? `<tr class="expand-row"><td colspan="6"><div>${gates}</div>${reasons ? `<ul class="reason-list">${reasons}</ul>` : ''}</td></tr>` : ''}`;
    }).join('');
    body.querySelectorAll('tr[data-key]').forEach((tr) => {
      tr.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        const key = tr.dataset.key;
        if (STATE.expanded.has(key)) STATE.expanded.delete(key); else STATE.expanded.add(key);
        renderWires();
      });
    });
  }

  function renderWatchlist() {
    const table = document.getElementById('wl-table');
    paintSortHeaders(table, STATE.wlSort);
    const rows = sortRows(STATE.data.watchlist || [], STATE.wlSort, (w, k) => w[k]);
    document.getElementById('wl-count').textContent = rows.length;
    const body = document.getElementById('wl-body');
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6" class="table-empty">The watchlist is empty.</td></tr>';
      return;
    }
    body.innerHTML = rows.map((w) => {
      const key = statusKeyFor(w.verdict, w.edgar_8k && w.edgar_8k.has_recent_item_1_01);
      return `
        <tr class="clickable${w.ticker === STATE.selected ? ' selected' : ''}" data-ticker="${esc(w.ticker)}">
          <td><span class="radio"></span></td>
          <td class="tkr">${esc(w.ticker)}</td>
          <td class="wrap" style="max-width:260px;">${esc(w.buyer_type || '—')}</td>
          <td>${esc(shortAge(w.leak_age_human))}</td>
          <td class="num ${signClass(w.gross_spread_pct)}">${fmtPct(w.gross_spread_pct, 2)}</td>
          <td>${statusPill(key)}</td>
        </tr>`;
    }).join('');
    body.querySelectorAll('tr[data-ticker]').forEach((tr) => {
      tr.addEventListener('click', () => {
        STATE.selected = tr.dataset.ticker;
        renderWatchlist();
        renderWlDetail();
      });
    });
  }

  function renderWlDetail() {
    const panel = document.getElementById('wl-detail');
    const w = (STATE.data.watchlist || []).find((r) => r.ticker === STATE.selected);
    if (!w) { panel.innerHTML = '<div class="muted">Select a watchlist name to see its audit.</div>'; return; }
    const edgar = w.edgar_8k || {};
    const key = statusKeyFor(w.verdict, edgar.has_recent_item_1_01);
    const gates = gateChips(w.failed_gates);
    const reasons = (w.rejection_reasons || []).map((r) => `<li>${esc(r)}</li>`).join('');
    const edgarStatus = edgar.has_recent_item_1_01 ? 'Definitive agreement filed' : edgar.leak_window_status === 'OPEN_PRE_8K' ? 'No merger 8-K yet (window open)' : humanize(edgar.leak_window_status);
    const params = new URLSearchParams({ ticker: w.ticker });
    if (w.rumored_value !== null && w.rumored_value !== undefined) { params.set('mode', w.input_mode); params.set('value', w.rumored_value); }
    panel.innerHTML = `
      <div class="det-head">
        <div>
          <div class="det-ticker">${esc(w.ticker)}</div>
          <div class="det-company">${esc(w.company_name)}</div>
        </div>
        ${statusPill(key)}
      </div>
      <div class="det-text">${esc(w.rumor_headline || w.gate_notes || '')}</div>
      <div class="metrics">
        <div class="metric"><div class="metric-label">Market Price</div><div class="metric-value">${fmtPx(w.extended_hours_price)}</div></div>
        <div class="metric"><div class="metric-label">Implied Deal</div><div class="metric-value">${fmtPx(w.implied_deal_price)}</div></div>
        <div class="metric"><div class="metric-label">Gross Spread</div><div class="metric-value ${signClass(w.gross_spread_pct)}">${fmtPct(w.gross_spread_pct, 2)}</div></div>
        <div class="metric"><div class="metric-label">Net Spread</div><div class="metric-value ${signClass(w.net_spread_pct)}">${fmtPct(w.net_spread_pct, 2)}</div></div>
      </div>

      <div class="sub-title">Leak</div>
      <div class="kv-list">
        <div class="kv"><span class="k">Broke</span><span class="v">${esc(fmtLeakTime(w.leak_timestamp_est))} (${esc(shortAge(w.leak_age_human))})</span></div>
        <div class="kv"><span class="k">Buyer</span><span class="v">${esc(w.buyer_type || '—')}</span></div>
        <div class="kv"><span class="k">Max clip (10% of AH volume)</span><span class="v">${fmtUsdPlain(w.max_clip_10pct_volume_usd)}</span></div>
      </div>

      <div class="sub-title">Net-Debt Waterfall</div>
      <div class="kv-list">
        <div class="kv"><span class="k">Debt + preferred</span><span class="v">${fmtBillions(w.total_debt_and_preferred_usd)}</span></div>
        <div class="kv"><span class="k">Cash</span><span class="v">${fmtBillions(w.total_cash_usd)}</span></div>
        <div class="kv"><span class="k">Net debt</span><span class="v">${fmtBillions(w.net_debt_usd)}</span></div>
        <div class="kv"><span class="k">CoC-adjusted diluted shares</span><span class="v">${isNum(w.adjusted_diluted_shares) ? (w.adjusted_diluted_shares / 1e6).toFixed(1) + 'M' : '—'}</span></div>
      </div>

      <div class="sub-title">SEC EDGAR</div>
      <div class="kv-list">
        <div class="kv"><span class="k">Status</span><span class="v ${edgar.has_recent_item_1_01 ? 'neg' : ''}">${esc(edgarStatus)}</span></div>
        <div class="kv"><span class="k">Latest 8-K</span><span class="v">${esc(fmtDate(edgar.latest_8k_date))}</span></div>
        <div class="kv"><span class="k">Items</span><span class="v">${esc((edgar.latest_8k_items || []).join(', ') || '—')}</span></div>
        <div class="kv"><span class="k">CIK</span><span class="v">${edgar.sec_url ? `<a class="ext-link" href="${esc(edgar.sec_url)}" target="_blank" rel="noopener">${esc(edgar.cik || 'View')} &#8599;</a>` : esc(edgar.cik || '—')}</span></div>
      </div>

      <div class="sub-title">Gate Audit</div>
      <div>${gates}</div>
      ${reasons ? `<ul class="reason-list">${reasons}</ul>` : ''}

      <a class="btn-primary" href="/terminal?${params.toString()}">
        Open in Calculator
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </a>`;
  }

  function tickLastScan() {
    const el = document.getElementById('last-update');
    if (!STATE.lastScan) { el.textContent = 'Last scan: —'; return; }
    const took = isNum(STATE.elapsedMs) ? ` · took ${(STATE.elapsedMs / 1000).toFixed(1)}s` : '';
    el.textContent = `Last scan: ${relativeAgo(STATE.lastScan)}${took}`;
  }

  bindSortHeaders(document.getElementById('wire-table'), STATE.wireSort, () => STATE.data && renderWires());
  bindSortHeaders(document.getElementById('wl-table'), STATE.wlSort, () => STATE.data && renderWatchlist());
  setInterval(tickLastScan, 1000);
  window.addEventListener('DOMContentLoaded', runScan);
"""

RESEARCH_HTML = render_page(
    title="M&amp;A Wire &amp; EDGAR Research",
    active="research",
    styles=_STYLES,
    body=_BODY,
    script=_SCRIPT,
)
