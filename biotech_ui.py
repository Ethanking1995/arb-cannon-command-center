"""
Arb Cannon: Biotech M&A Rumors UI (biotech_ui.py)

Light page served at GET /biotech-rumors. Reads GET /api/biopharma-backtest for the
live position audit, scenarios, buy plan, and pre-rumor radar; GET /api/scanner for
live biotech prices; and POSTs to /api/biopharma-evaluate to check any biotech rumor
against the six biotech checks.
"""

from ui_shell import render_page

_STYLES = r"""
    .pane-kpis { margin-top: 0; }
    .head-right .btn-secondary { text-decoration: none; }
    .det-position { color: var(--text-2); font-size: 12px; margin-top: 8px; }
    .det-position strong { color: var(--text); }

    .price-map { position: relative; height: 72px; margin: 16px 0 2px; }
    .pm-track { position: absolute; left: 0; right: 0; top: 30px; height: 6px; border-radius: 3px; background: var(--bg-subtle); overflow: hidden; }
    .pm-zone { position: absolute; top: 0; bottom: 0; }
    .pm-zone.down { background: #F5C6C6; }
    .pm-zone.up { background: #C4E7CF; }
    .pm-zone.up2 { background: #8FD3A6; }
    .pm-tick { position: absolute; top: 26px; width: 1px; height: 14px; background: #9AA3B2; }
    .pm-label { position: absolute; top: 44px; transform: translateX(-50%); text-align: center; font-size: 10.5px; color: var(--text-2); white-space: nowrap; line-height: 1.3; }
    .pm-label strong { display: block; color: var(--text); font-size: 11.5px; }
    .pm-now { position: absolute; top: 9px; transform: translateX(-50%); text-align: center; font-size: 10.5px; color: var(--blue); font-weight: 600; white-space: nowrap; }
    .pm-now::after { content: ''; display: block; width: 10px; height: 10px; margin: 3px auto 0; border-radius: 50%; background: var(--blue); border: 2px solid #fff; box-shadow: 0 0 0 1px var(--blue); }

    .gate-list { list-style: none; margin-top: 6px; }
    .gate { display: grid; grid-template-columns: 24px 1fr; padding: 9px 0; border-bottom: 1px solid var(--line); }
    .gate:last-child { border-bottom: none; }
    .check { width: 15px; height: 15px; margin-top: 1px; border-radius: 50%; display: grid; place-items: center; font-size: 9.5px; font-weight: 700; color: #fff; }
    .check.yes { background: var(--green); }
    .check.no { background: var(--red); }
    .gate-label { font-weight: 600; font-size: 12.5px; }
    .gate-fact { font-size: 12px; margin-top: 3px; }
    .gate-hint { color: var(--text-3); font-size: 11.5px; margin-top: 2px; line-height: 1.45; }
    .count-pill { font-size: 11.5px; font-weight: 600; }

    .timeline { list-style: none; margin-top: 10px; }
    .tl-item { position: relative; padding: 0 0 14px 20px; }
    .tl-item::before { content: ''; position: absolute; left: 1px; top: 4px; width: 9px; height: 9px; border-radius: 50%; background: var(--blue); }
    .tl-item::after { content: ''; position: absolute; left: 5px; top: 16px; bottom: 2px; width: 1px; background: var(--line); }
    .tl-item:last-child { padding-bottom: 0; }
    .tl-item:last-child::after { display: none; }
    .tl-item.stop::before { background: var(--red); }
    .tl-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    .tl-title { font-weight: 600; font-size: 12.5px; }
    .tl-dates { font-size: 12px; margin-top: 2px; }
    .tl-desc { color: var(--text-2); font-size: 12px; margin-top: 3px; line-height: 1.45; }

    .note { margin-top: 12px; padding: 9px 11px; border-left: 2px solid var(--blue-line); background: var(--bg-subtle); color: var(--text-2); font-size: 12px; line-height: 1.5; }
    .verdict-box { margin-top: 12px; padding: 10px 12px; border-radius: 6px; font-size: 12.5px; line-height: 1.5; background: var(--bg-subtle); color: var(--text-2); }
    .verdict-box strong { display: block; font-size: 13px; margin-bottom: 1px; }
    .verdict-box.go { background: var(--green-soft); } .verdict-box.go strong { color: var(--green); }
    .verdict-box.wait { background: var(--blue-soft); } .verdict-box.wait strong { color: var(--blue); }
    .verdict-box.review { background: var(--amber-soft); } .verdict-box.review strong { color: var(--amber); }
    .verdict-box.avoid { background: var(--red-soft); } .verdict-box.avoid strong { color: var(--red); }
    .data-table tfoot td { font-weight: 700; border-bottom: none; }
    .radar-why { max-width: 440px; line-height: 1.45; }
    .radar-why .muted { display: block; margin-top: 2px; font-size: 11.5px; }

    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 14px; margin-top: 14px; }
    .field label { display: block; color: var(--text-2); font-size: 11.5px; margin-bottom: 4px; }
    .field input[type=text], .field input[type=number] { width: 100%; padding: 6px 9px; border: 1px solid var(--line); border-radius: 6px; font: inherit; font-size: 12.5px; color: var(--text); background: #fff; }
    .field input:focus { outline: none; border-color: var(--blue-line); box-shadow: 0 0 0 3px var(--blue-soft); }
    .field.full { grid-column: 1 / -1; }
    .field-hint { color: var(--text-3); font-size: 11px; margin-top: 3px; }
    .check-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; cursor: pointer; }
    .check-row input { width: 14px; height: 14px; accent-color: var(--blue); }
    .form-actions { display: flex; gap: 10px; align-items: center; }
    .form-actions .btn-primary { width: auto; padding: 8px 16px; }
    .form-actions .btn-secondary { margin-top: 16px; padding: 7px 12px; }
    .btn-primary:disabled { background: var(--blue-line); cursor: default; }
    .check-grid { grid-template-columns: minmax(330px, 1fr) minmax(0, 1.55fr); }
    @media (max-width: 1100px) { .check-grid { grid-template-columns: 1fr; } }
"""

_BODY = r"""
    <header class="page-head">
      <div>
        <h1 class="page-title">Biotech M&amp;A Rumors</h1>
        <p class="page-sub">Follow buyout rumors on biotech companies, run them through six safety checks, and see what you could make or lose.</p>
      </div>
      <div class="head-right">
        <span id="live-pill" class="live-pill loading">Loading</span>
        <span id="last-update">Last update: —</span>
        <button id="btn-refresh" class="icon-btn" title="Refresh" onclick="loadAll()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></svg>
        </button>
        <a class="btn-secondary" href="/biotech" title="Full Biotech M&amp;A Rumor Command Center in the original dark terminal">
          Classic view
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="8 7 17 7 17 16"/></svg>
        </a>
      </div>
    </header>

    <section class="kpi-strip">
      <div class="kpi" title="Biotech buyout rumors the scanner is tracking right now">Live Biotech Setups <strong id="kpi-setups">—</strong><span class="kpi-note" id="kpi-setups-note"></span></div>
      <div class="kpi" title="Share of past rumors that passed all six checks and ended in a deal">6-Check Win Rate <strong id="kpi-win">—</strong><span class="kpi-note" id="kpi-win-note"></span></div>
      <div class="kpi" title="Typical gain on the winning trades in the backtest">Median Winner Gain <strong id="kpi-winner" class="pos">—</strong></div>
      <div class="kpi" title="How long these trades usually take to resolve">Expected Hold <strong id="kpi-hold">—</strong></div>
    </section>

    <nav class="tabs">
      <button class="tab active" data-tab="live" onclick="switchTab('live')">Live Rumor</button>
      <button class="tab" data-tab="radar" onclick="switchTab('radar')">Pre-Rumor Radar<span class="tab-count" id="tab-radar-count"></span></button>
      <button class="tab" data-tab="check" onclick="switchTab('check')">Check a Rumor</button>
    </nav>

    <div id="error-banner" class="error-banner"></div>

    <!-- LIVE RUMOR -->
    <section id="pane-live" class="tab-pane active">
      <div class="pane-section">
        <h2 class="section-title">Biotech Rumors on the Scanner</h2>
        <p class="pane-note">Live prices from the scanner. A biotech rumor is only worth buying when it passes all six checks at today's price.</p>
        <table class="data-table">
          <thead>
            <tr><th>Ticker</th><th>Company</th><th>Rumored Buyer</th><th class="num">Price</th><th class="num">Offer</th><th class="num">Gain to Offer</th><th class="num">Checks Passed</th><th>Decision</th></tr>
          </thead>
          <tbody id="setups-body"><tr><td colspan="8" class="table-empty">Loading live prices…</td></tr></tbody>
        </table>
      </div>

      <div class="panel-grid" style="border-top:1px solid var(--line);">
        <div class="cell" id="live-main"><div class="muted">Loading the live position…</div></div>
        <div class="cell right" id="live-side"></div>
      </div>
    </section>

    <!-- PRE-RUMOR RADAR -->
    <section id="pane-radar" class="tab-pane">
      <div class="pane-section">
        <h2 class="section-title">Pre-Rumor Radar</h2>
        <p class="pane-note">Biotechs that fit the profile of past buyout targets: an approved or nearly approved drug and plenty of cash, so they can afford to say no to a low offer.</p>
        <table class="data-table">
          <thead>
            <tr><th>Ticker</th><th>Company</th><th>Status</th><th>Why It's on the Radar</th><th>Cash Cushion</th></tr>
          </thead>
          <tbody id="radar-body"><tr><td colspan="5" class="table-empty">Loading radar…</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- CHECK A RUMOR -->
    <section id="pane-check" class="tab-pane">
      <div class="panel-grid check-grid">
        <div class="cell">
          <h2 class="section-title">Check a Biotech Rumor</h2>
          <p class="pane-note">Enter the numbers from a buyout rumor to see if it passes the six biotech checks, what you could make or lose, and how to stage your buys. Prefilled with the live RYTM rumor.</p>
          <form id="eval-form" autocomplete="off">
            <div class="form-grid">
              <div class="field"><label for="f-ticker">Ticker</label><input id="f-ticker" type="text" value="RYTM" required></div>
              <div class="field"><label for="f-buyer">Rumored buyer</label><input id="f-buyer" type="text" placeholder="e.g. AstraZeneca" value=""></div>
              <div class="field"><label for="f-price">Current price ($)</label><input id="f-price" type="number" step="0.01" min="0" value="113.00" required></div>
              <div class="field"><label for="f-unaffected">Price before the rumor ($)</label><input id="f-unaffected" type="number" step="0.01" min="0" value="86.44" required></div>
              <div class="field"><label for="f-base">Offer price ($ per share)</label><input id="f-base" type="number" step="0.01" min="0" value="124.00" required></div>
              <div class="field"><label for="f-higher">Higher offer ($, optional)</label><input id="f-higher" type="number" step="0.01" min="0" value="134.00"><div class="field-hint">If a second bidder is reported</div></div>
              <div class="field"><label for="f-floor">Walk-away floor ($)</label><input id="f-floor" type="number" step="0.01" min="0" value="92.00" required><div class="field-hint">Where the stock likely lands if talks fail</div></div>
              <div class="field"><label for="f-size">Deal size ($ billions)</label><input id="f-size" type="number" step="0.1" min="0" value="10" required></div>
              <div class="field"><label for="f-clip">Amount to invest ($)</label><input id="f-clip" type="number" step="1000" min="0" value="100000" required></div>
              <div class="field" style="align-self:end;padding-bottom:6px;"><label class="check-row"><input id="f-fda" type="checkbox" checked>Has an FDA-approved drug on the market</label></div>
            </div>
            <div class="form-actions">
              <button id="btn-eval" class="btn-primary" type="submit">Check this rumor</button>
              <button class="btn-secondary" type="button" onclick="prefillForm(); runEvaluate();">Reset to RYTM</button>
            </div>
          </form>
        </div>
        <div class="cell right" id="eval-result"><div class="muted">Results will appear here.</div></div>
      </div>
    </section>
"""

_SCRIPT = r"""
  const STATE = { bt: null, scanner: null, lastLoad: null, loading: false };

  const GATE_TEXT = [
    ['Named big-pharma buyer with a specific price', 'A known drug company was reported with a real dollar offer, not just "interest".'],
    ['Approved drug props up the stock if talks fail', 'A drug that is already approved and selling keeps the stock from collapsing if the buyer walks away.'],
    ['Clean ownership and drug rights', 'The company owns its drug rights outright, with no partner or royalty strings that could scare a buyer off.'],
    ['Second bidder could push the price higher', 'A rejected first offer or a rival bidder makes a higher final price more likely.'],
    ['Buying at or below 92% of the offer', 'Only buy when the price leaves at least an 8% gain to the offer.'],
    ['Small position with a set time limit', 'Keep the bet small and sell if no deal is announced within about 20 trading days.'],
  ];
  const SCENARIO_TEXT = ['Deal closes at the offer', 'Bidding war raises the price', 'Talks fail, stock drops to the floor'];
  const LADDER_TEXT = ['Buy now', 'Buy on a pullback', 'Buy on a deeper pullback'];
  const WINDOW_TEXT = [
    ['Most likely window', 'past deals', 'Most past deals were announced in this window, usually on a Monday before the market opens. A news story saying the buyer is "nearing a deal" often comes a few days earlier.'],
    ['If a bidding war starts', 'past deals', 'If a second buyer needs more time to look at the books, signing tends to slip a few weeks, often at a higher price.'],
    ['Give-up date', 'rumors stalled', 'If there is no new news and no deal filing by these dates, sell and move the money back to cash.'],
  ];
  const VERDICTS = {
    BIO_PASS_HOT: ['go', 'Ready to buy'],
    BIO_FAIL_OVER_92PCT_CEILING: ['wait', 'Wait for dip'],
    BIO_FAIL_TAKE_UNDER: ['avoid', 'Avoid'],
    BIO_WARN_GATES: ['review', 'Needs review'],
  };

  const pill = (cls, label, hint = '') => `<span class="pill ${esc(cls)}" title="${esc(hint)}">${esc(label)}</span>`;
  const gainPct = (from, to) => isNum(from) && isNum(to) && from > 0 ? (to / from - 1) * 100 : null;
  const shortCompany = (s) => String(s || '').split(' (')[0];
  const shortHold = (s) => String(s || '').split(' (')[0];

  // The backend reports the price-ceiling failure ahead of other failed checks; only call it
  // "Wait for dip" when the price is the sole problem.
  const otherGatesFailed = (r) => r.verdict === 'BIO_FAIL_OVER_92PCT_CEILING' && r.passed_gates_count < r.total_gates_count - 1;
  const verdictOf = (r) => otherGatesFailed(r) ? VERDICTS.BIO_WARN_GATES : (VERDICTS[r.verdict] || ['', humanize(r.verdict)]);

  function verdictText(r) {
    const passed = r.passed_gates_count, total = r.total_gates_count;
    if (otherGatesFailed(r)) return `Passes only ${passed} of ${total} checks, and ${fmtPx(r.current_price)} is also above the max buy price of ${fmtPx(r.hard_ceiling_92pct)}. Review the failed checks before buying.`;
    switch (r.verdict) {
      case 'BIO_PASS_HOT': return `Passes all ${total} checks, and ${fmtPx(r.current_price)} is at or below the max buy price of ${fmtPx(r.hard_ceiling_92pct)}.`;
      case 'BIO_FAIL_OVER_92PCT_CEILING': return `${fmtPx(r.current_price)} is above the max buy price of ${fmtPx(r.hard_ceiling_92pct)} (92% of the ${fmtPx(r.base_cash_bid_per_share)} offer). Only buy at or below ${fmtPx(r.hard_ceiling_92pct)}. Passes ${passed} of ${total} checks.`;
      case 'BIO_FAIL_TAKE_UNDER': return `The stock already trades at or above the ${fmtPx(r.base_cash_bid_per_share)} offer, so there is no profit left if the deal closes at that price.`;
      default: return `Passes only ${passed} of ${total} checks. Review the failed checks before buying.`;
    }
  }

  // Normalize gate rows from /api/biopharma-* (gate_checks) or the scanner's biotech_signal.checks.
  function gateRows(checks, ctx) {
    return (checks || []).map((c, i) => {
      const [label, hint] = GATE_TEXT[i] || [c.label || humanize(c.id), ''];
      let fact = '';
      if (i === 0 && ctx.suitor) fact = `Buyer: ${ctx.suitor}`;
      if (i === 1) fact = c.passed ? `If talks fail, the stock should hold around ${fmtPx(ctx.floor)}.` : 'No approved drug, so the stock could fall back to its pre-rumor price or lower.';
      if (i === 4 && isNum(ctx.price) && isNum(ctx.base) && ctx.base > 0) fact = `${fmtPx(ctx.price)} is ${(ctx.price / ctx.base * 100).toFixed(1)}% of the ${fmtPx(ctx.base)} offer. Max buy price: ${fmtPx(ctx.ceiling)}.`;
      return { label: c.label || label, hint, fact, passed: !!c.passed, detail: c.detail || '' };
    });
  }

  function gateList(rows) {
    return `<ul class="gate-list">${rows.map((g) => `
      <li class="gate" title="${esc(g.detail)}">
        <span class="check ${g.passed ? 'yes' : 'no'}">${g.passed ? '&#10003;' : '&#10005;'}</span>
        <div>
          <div class="gate-label">${esc(g.label)}</div>
          ${g.fact ? `<div class="gate-fact">${esc(g.fact)}</div>` : ''}
          <div class="gate-hint">${esc(g.hint)}</div>
        </div>
      </li>`).join('')}</ul>`;
  }

  function priceMap(p) {
    const pts = [p.floor, p.ceiling, p.base, p.higher, p.price].filter(isNum);
    if (pts.length < 3) return '';
    const min = Math.min(...pts), max = Math.max(...pts);
    const pad = (max - min) * 0.11 || 1;
    const lo = min - pad, hi = max + pad;
    const x = (v) => ((v - lo) / (hi - lo) * 100).toFixed(2) + '%';
    const zone = (cls, a, b) => isNum(a) && isNum(b) && b > a ? `<span class="pm-zone ${cls}" style="left:${x(a)};width:${((b - a) / (hi - lo) * 100).toFixed(2)}%"></span>` : '';
    const mark = (v, label) => isNum(v) ? `<span class="pm-tick" style="left:${x(v)}"></span><span class="pm-label" style="left:${x(v)}"><strong>${fmtPxShort(v)}</strong>${esc(label)}</span>` : '';
    const top = isNum(p.higher) && p.higher > p.base ? p.higher : null;
    return `
      <div class="price-map" aria-label="Price map">
        <div class="pm-track">${zone('down', p.floor, p.price)}${zone('up', p.price, p.base)}${zone('up2', p.base, top)}</div>
        ${mark(p.floor, 'Walk-away floor')}
        ${mark(p.ceiling, 'Max buy price')}
        ${mark(p.base, 'Offer')}
        ${top ? mark(top, 'Higher offer') : ''}
        ${isNum(p.price) ? `<span class="pm-now" style="left:${x(p.price)}">${esc(p.nowLabel || 'Today')} ${fmtPxShort(p.price)}</span>` : ''}
      </div>`;
  }

  function scenarioTable(lot) {
    const rows = (lot.scenarios || []).map((s, i) => `
      <tr title="${esc(s.notes || '')}">
        <td>${esc(SCENARIO_TEXT[i] || s.scenario)}</td>
        <td class="num">${isNum(s.probability_pct) ? s.probability_pct.toFixed(0) + '%' : '—'}</td>
        <td class="num">${fmtPx(s.exit_price)}</td>
        <td class="num ${signClass(s.return_pct)}">${fmtPct(s.return_pct, 1)}</td>
        <td class="num ${signClass(s.ira_0pct_tax_pnl_usd)}"><strong>${fmtUsd(s.ira_0pct_tax_pnl_usd)}</strong></td>
      </tr>`).join('');
    return `
      <table class="data-table">
        <thead><tr><th>What happens</th><th class="num">Chance</th><th class="num">Exit Price</th><th class="num">Return</th><th class="num">P&amp;L on ${fmtUsdPlain(lot.position_usd)}</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5" class="table-empty">No scenarios.</td></tr>'}</tbody>
        <tfoot><tr><td>Average, weighted by chance</td><td></td><td></td>
          <td class="num ${signClass(lot.probability_weighted_ev_pct)}">${fmtPct(lot.probability_weighted_ev_pct, 1)}</td>
          <td class="num ${signClass(lot.probability_weighted_ev_usd)}">${fmtUsd(lot.probability_weighted_ev_usd)}</td></tr></tfoot>
      </table>`;
  }

  function ladderTable(ladder) {
    const rows = (ladder || []).map((t, i) => `
      <tr title="${esc(t.label || '')}">
        <td><strong>${esc(LADDER_TEXT[i] || 'Step ' + (i + 1))}</strong><div class="muted" style="font-size:11px;">${isNum(t.target_discount_pct) ? t.target_discount_pct + '% below the offer' : ''}</div></td>
        <td class="num">${isNum(t.weight_pct) ? t.weight_pct.toFixed(0) + '%' : '—'}</td>
        <td class="num">${fmtPx(t.limit_price)}</td>
        <td class="num">${isNum(t.shares) ? t.shares.toLocaleString('en-US') : '—'}</td>
        <td class="num">${fmtUsdPlain(t.deployed_usd)}</td>
        <td class="num pos">${fmtUsd(t.base_bid_profit_usd)}</td>
        <td class="num pos">${fmtUsd(t.sweetened_bid_profit_usd)}</td>
      </tr>`).join('');
    return `
      <table class="data-table">
        <thead><tr><th>Step</th><th class="num">Share</th><th class="num">Buy At or Below</th><th class="num">Shares</th><th class="num">Amount</th><th class="num">Profit at Offer</th><th class="num">Profit if Higher</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="table-empty">No buy plan.</td></tr>'}</tbody>
      </table>`;
  }

  function timeline(windows) {
    return `<ol class="timeline">${(windows || []).map((w, i) => {
      const [title, unit, desc] = WINDOW_TEXT[i] || [w.window_name || w.window, '', w.catalyst_note || ''];
      const pct = /(\d+)%/.exec(w.window_name || w.window || '');
      return `
        <li class="tl-item${i === 2 ? ' stop' : ''}" title="${esc(w.catalyst_note || w.catalysts_and_mechanics || '')}">
          <div class="tl-head"><span class="tl-title">${esc(title)}</span>${pct ? `<span class="muted" style="font-size:11.5px;">${esc(pct[1])}% of ${esc(unit)}</span>` : ''}</div>
          <div class="tl-dates">${esc(w.target_dates)}</div>
          <div class="tl-desc">${esc(desc)}</div>
        </li>`;
    }).join('')}</ol>`;
  }

  async function fetchJson(url, opts) {
    const resp = await fetch(url, opts);
    if (!resp.ok) throw new Error(`${url} failed (HTTP ${resp.status})`);
    return resp.json();
  }

  function showError(msg) {
    const banner = document.getElementById('error-banner');
    banner.textContent = msg;
    banner.style.display = msg ? 'block' : 'none';
  }

  async function loadAll() {
    if (STATE.loading) return;
    STATE.loading = true;
    const btn = document.getElementById('btn-refresh');
    const livePill = document.getElementById('live-pill');
    btn.classList.add('spinning');
    livePill.className = 'live-pill loading';
    livePill.textContent = 'Loading';
    showError('');
    const errors = [];
    const btReq = fetchJson('/api/biopharma-backtest').then((d) => {
      STATE.bt = d;
      renderBacktest();
      renderLive();
    }).catch((e) => { errors.push(`Could not load the biotech rumor data: ${e.message}`); });
    const scReq = fetchJson('/api/scanner').then((d) => {
      STATE.scanner = d;
    }).catch((e) => { errors.push(`Could not load live prices: ${e.message}`); });
    await btReq;
    await scReq;
    renderSetups();
    renderLive();
    STATE.loading = false;
    btn.classList.remove('spinning');
    STATE.lastLoad = Date.now();
    livePill.className = STATE.scanner && !errors.length ? 'live-pill' : 'live-pill offline';
    livePill.textContent = STATE.scanner && !errors.length ? 'Live' : 'Offline';
    if (!STATE.bt) {
      document.getElementById('live-main').innerHTML = '<div class="muted">The live position could not be loaded.</div>';
      document.getElementById('radar-body').innerHTML = '<tr><td colspan="5" class="table-empty">The radar could not be loaded.</td></tr>';
    }
    showError(errors.join(' · '));
    tickLastUpdate();
  }

  const biotechOpps = () => ((STATE.scanner && STATE.scanner.opportunities) || []).filter((o) => o.sector === 'Biotech');

  function renderBacktest() {
    const f = STATE.bt.filtered_6_gate_metrics || {};
    document.getElementById('kpi-win').textContent = isNum(f.win_rate_pct) ? f.win_rate_pct.toFixed(0) + '%' : '—';
    document.getElementById('kpi-win-note').textContent = isNum(f.wins) ? `(${f.wins}W / ${f.losses_or_walkaways}L)` : '';
    document.getElementById('kpi-winner').textContent = fmtPct(f.winner_median_spread_pct, 1);
    document.getElementById('kpi-hold').textContent = shortHold(f.expected_hold_clock) || '—';
    renderRadar();
  }

  function renderSetups() {
    const body = document.getElementById('setups-body');
    const setups = document.getElementById('kpi-setups');
    const note = document.getElementById('kpi-setups-note');
    if (!STATE.scanner) {
      setups.textContent = '—';
      note.textContent = '';
      body.innerHTML = '<tr><td colspan="8" class="table-empty">Live prices are unavailable right now.</td></tr>';
      return;
    }
    const opps = biotechOpps();
    const ready = opps.filter((o) => o.biotech_signal && o.biotech_signal.is_actionable).length;
    setups.textContent = opps.length;
    note.textContent = `(${ready} ready to buy)`;
    if (!opps.length) {
      body.innerHTML = '<tr><td colspan="8" class="table-empty">No biotech buyout rumors on the scanner right now.</td></tr>';
      return;
    }
    body.innerHTML = opps.map((o) => {
      const s = o.biotech_signal || {};
      return `
        <tr>
          <td class="tkr">${esc(o.ticker)}</td>
          <td>${esc(o.company_name)}</td>
          <td class="wrap" style="max-width:260px;">${esc(o.buyer || '—')}</td>
          <td class="num">${fmtPx(o.entry_price)}</td>
          <td class="num">${fmtPx(o.base_offer)}</td>
          <td class="num ${signClass(o.upside_low_pct)}">${fmtPct(o.upside_low_pct, 1)}</td>
          <td class="num">${isNum(s.gates_passed) ? `${esc(s.gates_passed)} / ${esc(s.gates_total)}` : '—'}</td>
          <td>${o.decision_label ? pill(o.decision_key, o.decision_label, o.decision_text) : '—'}</td>
        </tr>`;
    }).join('');
  }

  function renderLive() {
    if (!STATE.bt) return;
    const a = STATE.bt.live_rytm_audit || {};
    const lot = a.live_100k_lot_scenarios || {};
    const o = biotechOpps().find((x) => x.ticker === a.ticker) || null;
    const sig = o && o.biotech_signal;
    const price = o && isNum(o.entry_price) ? o.entry_price : a.current_price;
    const radar = (STATE.bt.regime_b_pre_leak_radar || []).find((r) => r.ticker === a.ticker);
    const company = (o && o.company_name) || shortCompany(radar && radar.company_name);
    const [vCls, vLabel] = verdictOf(a);
    const statusPill = o && o.decision_label ? pill(o.decision_key, o.decision_label, o.decision_text) : pill(vCls, vLabel);
    const toOffer = gainPct(price, a.base_cash_bid_per_share);
    const toHigher = gainPct(price, a.sweetened_ceiling_per_share);
    const toFloor = gainPct(price, a.fundamental_walkaway_floor);

    document.getElementById('live-main').innerHTML = `
      <div class="det-head">
        <div>
          <div class="det-ticker">${esc(a.ticker)}</div>
          <div class="det-company">${esc(company)}</div>
        </div>
        ${statusPill}
      </div>
      <div class="det-text">${esc((o && o.rumor_headline) || `Rumored buyer: ${a.named_pharma_suitor || '—'}`)}</div>
      <div class="det-position">Your position: <strong>${isNum(lot.shares) ? lot.shares.toLocaleString('en-US') : '—'} shares</strong> bought at <strong>${fmtPx(lot.entry_price)}</strong> (${fmtUsdPlain(lot.position_usd)})</div>
      ${priceMap({ floor: a.fundamental_walkaway_floor, ceiling: a.hard_ceiling_92pct, base: a.base_cash_bid_per_share, higher: a.sweetened_ceiling_per_share, price, nowLabel: o ? 'Today' : 'Entry' })}
      <div class="metrics">
        <div class="metric"><div class="metric-label">${o ? "Today's Price" : 'Entry Price'}</div><div class="metric-value">${fmtPx(price)}${o && isNum(o.change_pct) ? ` <span class="${signClass(o.change_pct)}" style="font-size:11.5px;">${fmtPct(o.change_pct)}</span>` : ''}</div></div>
        <div class="metric"><div class="metric-label">Gain at Offer</div><div class="metric-value ${signClass(toOffer)}">${fmtPct(toOffer, 1)}</div></div>
        <div class="metric"><div class="metric-label">Gain if Higher</div><div class="metric-value ${signClass(toHigher)}">${fmtPct(toHigher, 1)}</div></div>
        <div class="metric"><div class="metric-label">Loss if Talks Fail</div><div class="metric-value ${signClass(toFloor)}">${fmtPct(toFloor, 1)}</div></div>
      </div>

      <div class="sub-title">What Could Happen to Your ${fmtUsdPlain(lot.position_usd)}</div>
      ${scenarioTable(lot)}
      <div class="note">Hold the ${fmtUsdPlain(lot.position_usd)} position, but don't buy more above the max buy price of <strong>${fmtPx(a.hard_ceiling_92pct)}</strong>. If talks fail, the expected loss is about ${isNum(lot.walkaway_pct_of_4m_net_worth) ? lot.walkaway_pct_of_4m_net_worth.toFixed(2) + '% of a $4M portfolio' : 'the walk-away row above'}.</div>

      <div class="sub-title">3-Step Buy Plan</div>
      <p class="pane-note">Spread buys across three limit orders so pullbacks lower your average price.</p>
      ${ladderTable(a.tranche_ladder)}`;

    const rows = sig && sig.checks && sig.checks.length ? sig.checks : a.gate_checks;
    const passed = rows ? rows.filter((c) => c.passed).length : 0;
    const total = rows ? rows.length : 0;
    const ctx = { suitor: a.named_pharma_suitor, floor: a.fundamental_walkaway_floor, price, base: a.base_cash_bid_per_share, ceiling: a.hard_ceiling_92pct };
    const checkedNote = sig
      ? `Checked at today's price of ${fmtPx(price)}. Your ${fmtPx(a.current_price)} entry passed ${a.passed_gates_count} of ${a.total_gates_count}.`
      : `Checked at your ${fmtPx(a.current_price)} entry price.`;
    document.getElementById('live-side').innerHTML = `
      <div class="section-head">
        <h2 class="section-title">The 6 Biotech Checks</h2>
        <span class="pill ${passed === total && total ? 'go' : 'review'} count-pill">${passed} of ${total} passed</span>
      </div>
      <p class="pane-note">${esc(checkedNote)} Hover a check for the full detail.</p>
      ${gateList(gateRows(rows, ctx))}

      <h2 class="section-title" style="margin-top:20px;">When a Deal Could Be Announced</h2>
      <p class="pane-note">Expected hold: ${esc(shortHold(a.expected_hold_clock))}.</p>
      ${timeline(a.deal_timeline_windows)}`;
  }

  function radarStatus(s) {
    const v = String(s || '');
    if (/^LIVE_POSITION/.test(v)) return ['go', 'You own it'];
    if (/PRE_PDUFA/.test(v)) return ['review', 'FDA decision ahead'];
    if (/PRE_RUMOR/.test(v)) return ['monitoring', 'No rumor yet'];
    return ['', humanize(v.replace(/^REGIME_B_/, ''))];
  }

  function renderRadar() {
    const radar = STATE.bt.regime_b_pre_leak_radar || [];
    document.getElementById('tab-radar-count').textContent = radar.length;
    const body = document.getElementById('radar-body');
    if (!radar.length) {
      body.innerHTML = '<tr><td colspan="5" class="table-empty">No biotechs on the radar right now.</td></tr>';
      return;
    }
    body.innerHTML = radar.map((r) => {
      const [cls, label] = radarStatus(r.regime_status);
      return `
        <tr>
          <td class="tkr">${esc(r.ticker)}</td>
          <td class="wrap" style="max-width:200px;">${esc(shortCompany(r.company_name))}<div class="muted" style="font-size:11px;margin-top:2px;">${esc(r.trigger_date)}</div></td>
          <td>${pill(cls, label, r.regime_status)}</td>
          <td class="wrap radar-why"><strong>Drug:</strong> ${esc(r.commercial_anchor)}<span class="muted">${esc(r.walk_away_leverage_catalyst)}</span></td>
          <td class="wrap" style="max-width:220px;">${esc(r.pro_forma_cash_runway)}</td>
        </tr>`;
    }).join('');
  }

  const RYTM_DEFAULTS = { ticker: 'RYTM', buyer: 'AstraZeneca', price: 113, unaffected: 86.44, base: 124, higher: 134, floor: 92, size: 10, clip: 100000, fda: true };

  function prefillForm() {
    const a = (STATE.bt && STATE.bt.live_rytm_audit) || {};
    const lot = a.live_100k_lot_scenarios || {};
    const v = {
      ticker: a.ticker || RYTM_DEFAULTS.ticker,
      buyer: RYTM_DEFAULTS.buyer,
      price: isNum(a.current_price) ? a.current_price : RYTM_DEFAULTS.price,
      unaffected: isNum(a.unaffected_price) ? a.unaffected_price : RYTM_DEFAULTS.unaffected,
      base: isNum(a.base_cash_bid_per_share) ? a.base_cash_bid_per_share : RYTM_DEFAULTS.base,
      higher: isNum(a.sweetened_ceiling_per_share) ? a.sweetened_ceiling_per_share : RYTM_DEFAULTS.higher,
      floor: isNum(a.fundamental_walkaway_floor) ? a.fundamental_walkaway_floor : RYTM_DEFAULTS.floor,
      size: isNum(a.deal_ev_billions) ? a.deal_ev_billions : RYTM_DEFAULTS.size,
      clip: isNum(lot.position_usd) ? lot.position_usd : RYTM_DEFAULTS.clip,
      fda: RYTM_DEFAULTS.fda,
    };
    const set = (id, val) => { document.getElementById(id).value = val; };
    set('f-ticker', v.ticker);
    set('f-buyer', v.buyer);
    set('f-price', v.price.toFixed(2));
    set('f-unaffected', v.unaffected.toFixed(2));
    set('f-base', v.base.toFixed(2));
    set('f-higher', v.higher.toFixed(2));
    set('f-floor', v.floor.toFixed(2));
    set('f-size', v.size);
    set('f-clip', Math.round(v.clip));
    document.getElementById('f-fda').checked = v.fda;
  }

  function readForm() {
    const num = (id, label, optional = false) => {
      const raw = document.getElementById(id).value.trim();
      if (!raw && optional) return null;
      const n = Number(raw);
      if (!raw || !isFinite(n) || n <= 0) throw new Error(`Enter a positive number for "${label}".`);
      return n;
    };
    const ticker = document.getElementById('f-ticker').value.trim().toUpperCase();
    if (!ticker) throw new Error('Enter a ticker.');
    const base = num('f-base', 'Offer price');
    const higher = num('f-higher', 'Higher offer', true);
    const price = num('f-price', 'Current price');
    const clip = num('f-clip', 'Amount to invest');
    const buyer = document.getElementById('f-buyer').value.trim();
    const body = {
      ticker,
      current_price: price,
      unaffected_price: num('f-unaffected', 'Price before the rumor'),
      walk_away_floor_price: num('f-floor', 'Walk-away floor'),
      base_cash_bid_per_share: base,
      sweetened_ceiling_per_share: higher && higher > base ? higher : base,
      deal_ev_billions: num('f-size', 'Deal size'),
      fda_approved_commercial_anchor: document.getElementById('f-fda').checked,
      clip_usd: clip,
      live_position_usd: clip,
      live_position_entry_price: price,
    };
    if (buyer) body.named_pharma_suitor = `${buyer} (${fmtPx(base)}/sh offer)${higher && higher > base ? ` + higher bid ${fmtPx(higher)}/sh` : ''}`;
    if (ticker !== 'RYTM') body.commercial_drug_name = 'FDA-approved commercial drug';
    return { body, hasHigher: !!(higher && higher > base) };
  }

  async function runEvaluate(ev) {
    if (ev) ev.preventDefault();
    const panel = document.getElementById('eval-result');
    const btn = document.getElementById('btn-eval');
    let req;
    try { req = readForm(); } catch (err) {
      panel.innerHTML = `<div class="verdict-box avoid"><strong>Check the form</strong>${esc(err.message)}</div>`;
      return;
    }
    btn.disabled = true;
    btn.textContent = 'Checking…';
    panel.innerHTML = '<div class="muted">Running the six biotech checks…</div>';
    try {
      const r = await fetchJson('/api/biopharma-evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body),
      });
      renderEvaluate(r, req);
    } catch (err) {
      panel.innerHTML = `<div class="verdict-box avoid"><strong>Could not check this rumor</strong>${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Check this rumor';
    }
  }

  function renderEvaluate(r, req) {
    const [cls, label] = verdictOf(r);
    const lot = r.live_100k_lot_scenarios || {};
    const price = r.current_price;
    const higher = req.hasHigher ? r.sweetened_ceiling_per_share : null;
    const ctx = { suitor: req.body.named_pharma_suitor || r.named_pharma_suitor, floor: r.fundamental_walkaway_floor, price, base: r.base_cash_bid_per_share, ceiling: r.hard_ceiling_92pct };
    document.getElementById('eval-result').innerHTML = `
      <div class="det-head">
        <div>
          <div class="det-ticker">${esc(r.ticker)}</div>
          <div class="det-company">${esc(r.passed_gates_count)} of ${esc(r.total_gates_count)} biotech checks passed</div>
        </div>
      </div>
      <div class="verdict-box ${esc(cls)}"><strong>${esc(label)}</strong>${esc(verdictText(r))}</div>
      ${priceMap({ floor: r.fundamental_walkaway_floor, ceiling: r.hard_ceiling_92pct, base: r.base_cash_bid_per_share, higher, price, nowLabel: 'Price' })}
      <div class="metrics">
        <div class="metric"><div class="metric-label">Max Buy Price</div><div class="metric-value">${fmtPx(r.hard_ceiling_92pct)}</div></div>
        <div class="metric"><div class="metric-label">Gain at Offer</div><div class="metric-value ${signClass(r.base_spread_pct)}">${fmtPct(r.base_spread_pct, 1)}</div></div>
        <div class="metric"><div class="metric-label">Gain if Higher</div><div class="metric-value ${higher ? signClass(r.sweetened_spread_pct) : 'muted'}">${higher ? fmtPct(r.sweetened_spread_pct, 1) : '—'}</div></div>
        <div class="metric"><div class="metric-label">Loss if Talks Fail</div><div class="metric-value ${signClass(r.downside_to_fundamental_floor_pct)}">${fmtPct(r.downside_to_fundamental_floor_pct, 1)}</div></div>
      </div>

      <div class="sub-title">The 6 Biotech Checks</div>
      ${gateList(gateRows(r.gate_checks, ctx))}

      <div class="sub-title">What Could Happen to ${fmtUsdPlain(lot.position_usd)}</div>
      ${scenarioTable(lot)}
      ${higher ? '' : '<p class="pane-note">No higher offer entered, so the bidding-war row assumes the original offer.</p>'}

      <div class="sub-title">3-Step Buy Plan</div>
      ${ladderTable(r.tranche_ladder)}`;
  }

  function tickLastUpdate() {
    const el = document.getElementById('last-update');
    el.textContent = STATE.lastLoad ? `Last update: ${relativeAgo(STATE.lastLoad)}` : 'Last update: —';
  }

  document.getElementById('eval-form').addEventListener('submit', runEvaluate);
  setInterval(tickLastUpdate, 1000);
  window.addEventListener('DOMContentLoaded', async () => {
    await loadAll();
    prefillForm();
    runEvaluate();
  });
"""

BIOTECH_HTML = render_page(
    title="Biotech M&amp;A Rumors",
    active="biotech",
    styles=_STYLES,
    body=_BODY,
    script=_SCRIPT,
)
