// Vitiligo Initiative — Evidence Engine UI

const tabs = document.querySelectorAll('.tab');
const panels = {
  evidence: document.getElementById('panel-evidence'),
  search: document.getElementById('panel-search'),
  candidates: document.getElementById('panel-candidates'),
  graph: document.getElementById('panel-graph'),
  trials: document.getElementById('panel-trials'),
};

let candidatesLoaded = false;
let evidenceRows = null;

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    Object.values(panels).forEach(p => p.classList.add('hidden'));
    panels[tab.dataset.tab].classList.remove('hidden');
    if (tab.dataset.tab === 'trials' && !trialsStatsLoaded) {
      loadTrialsStats();
    }
    if (tab.dataset.tab === 'graph' && !graphStatsLoaded) {
      loadGraphStats();
    }
    if (tab.dataset.tab === 'candidates' && !candidatesLoaded) {
      loadCandidatesReport();
    }
    if (tab.dataset.tab === 'evidence' && evidenceRows === null) {
      loadEvidence();
    }
  });
});

// ---- helpers --------------------------------------------------------

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function showError(container, message) {
  container.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
}

function showLoading(container, label) {
  container.innerHTML = `<div class="empty"><span class="spinner"></span>${escapeHtml(label)}</div>`;
}

function metaBits(item) {
  const bits = [];
  if (item.journal) bits.push(item.journal);
  if (item.year) bits.push(item.year);
  if (item.doi) bits.push(`<a href="https://doi.org/${escapeHtml(item.doi)}" target="_blank">doi:${escapeHtml(item.doi)}</a>`);
  if (item.evidence_level_label) bits.push(`<span class="tag tag-evidence">${escapeHtml(item.evidence_level_label)}</span>`);
  if (item.source && item.source_id) {
    if (item.source === 'pubmed') {
      bits.push(`<a href="https://pubmed.ncbi.nlm.nih.gov/${escapeHtml(item.source_id)}/" target="_blank">PMID ${escapeHtml(item.source_id)}</a>`);
    } else if (item.source === 'pmc') {
      bits.push(`<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/${escapeHtml(item.source_id)}/" target="_blank">${escapeHtml(item.source_id)}</a>`);
    } else if (item.source === 'geo') {
      bits.push(`<a href="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${encodeURIComponent(item.source_id)}" target="_blank">${escapeHtml(item.source_id)}</a>`);
    }
  }
  return bits.join(' • ');
}

function formatApiError(detail) {
  if (detail == null) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => {
      if (typeof item === 'string') return item;
      if (item && typeof item === 'object' && item.msg) return item.msg;
      return JSON.stringify(item);
    }).join('; ');
  }
  if (typeof detail === 'object') return JSON.stringify(detail);
  return String(detail);
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data.detail) detail = formatApiError(data.detail);
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---- search ---------------------------------------------------------

document.getElementById('form-search').addEventListener('submit', async (e) => {
  e.preventDefault();
  const query = document.getElementById('search-query').value.trim();
  const topK = parseInt(document.getElementById('search-topk').value, 10);
  const out = document.getElementById('search-results');
  if (!query) return;

  showLoading(out, `Searching for "${query}"…`);
  try {
    const data = await postJson('/api/search', { query, top_k: topK });
    if (!data.results.length) {
      out.innerHTML = '<div class="empty">No results.</div>';
      return;
    }
    out.innerHTML = data.results.map(r => `
      <article class="hit">
        <div class="hit-header">
          <span class="hit-rank">#${r.rank}</span>
          <span class="hit-score" title="Evidence-adjusted cosine similarity (mouse −0.08, in vitro −0.05)">score ${r.score.toFixed(3)}</span>
          <span class="hit-source">${escapeHtml(r.source)}:${escapeHtml(r.source_id)}</span>
        </div>
        <div class="hit-title">${escapeHtml(r.title || '(no title)')}</div>
        <div class="hit-meta">${metaBits(r)}</div>
        ${r.abstract ? `<div class="hit-abstract">${escapeHtml(truncate(r.abstract, 600))}</div>` : ''}
        ${r.mesh_terms && r.mesh_terms.length ? `<div class="hit-mesh">${r.mesh_terms.slice(0, 8).map(m => `<span class="tag">${escapeHtml(m)}</span>`).join('')}</div>` : ''}
      </article>
    `).join('');
  } catch (err) {
    showError(out, err.message);
  }
});

function truncate(s, n) {
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function renderNotesBlock(notes, className) {
  if (!notes) return '';
  let items;
  if (Array.isArray(notes)) {
    items = notes;
  } else {
    items = String(notes).split(/\n+/);
  }
  const cleaned = items.map(item => String(item).trim()).filter(Boolean);
  if (!cleaned.length) return '';
  return `<ul class="${className}">${cleaned.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

// ---- trial results (posted registry figures, no model) ---------------

const EV_REGION = document.getElementById('ev-region');
const EV_ENDPOINT = document.getElementById('ev-endpoint');
const EV_UNCONTROLLED = document.getElementById('ev-uncontrolled');

[EV_REGION, EV_ENDPOINT, EV_UNCONTROLLED].forEach(el => {
  el.addEventListener('change', renderEvidence);
});

async function loadEvidence() {
  const out = document.getElementById('ev-results');
  showLoading(out, 'Reading posted trial results…');
  try {
    const res = await fetch('/api/evidence');
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) detail = formatApiError(data.detail);
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    const data = await res.json();
    evidenceRows = data.rows || [];
    renderEvidence();
  } catch (err) {
    evidenceRows = null;
    showError(out, err.message);
  }
}

function howGiven(row) {
  const bits = [];
  if (row.dose) bits.push(row.dose);
  if (row.loading_dose) bits.push(`after ${row.loading_dose}mg for 4 weeks`);
  const route = row.route
    ? row.route
    : '<span class="ev-unknown" title="The registry record does not state the route">route not recorded</span>';
  const photo = row.phototherapy
    ? ' <span class="ev-flag">with NB-UVB phototherapy</span>'
    : '';
  return `${escapeHtml(bits.join(', '))} · ${route}${photo}`;
}

function renderEvidence() {
  const out = document.getElementById('ev-results');
  const summary = document.getElementById('ev-summary');
  if (evidenceRows === null) return;

  const region = EV_REGION.value;
  const threshold = EV_ENDPOINT.value;
  const withUncontrolled = EV_UNCONTROLLED.checked;
  const instrument = region === 'Face' ? 'F-VASI' : 'T-VASI';
  const endpoint = `${instrument}${threshold}`;

  const rows = evidenceRows.filter(r =>
    r.endpoint === endpoint && (withUncontrolled || r.controlled));

  const hidden = evidenceRows.filter(r => r.endpoint === endpoint && !r.controlled).length;
  summary.innerHTML = `
    <span class="trial-stat trial-stat-total"><strong>${rows.length}</strong>
      arm${rows.length === 1 ? '' : 's'} reporting ${escapeHtml(endpoint)} at week 24</span>
    <span class="trial-stat">${region === 'Face' ? 'Facial' : 'Whole-body'} score</span>
    ${hidden && !withUncontrolled
      ? `<span class="trial-stat ev-stat-muted">${hidden} arm${hidden === 1 ? '' : 's'} hidden: no comparator</span>`
      : ''}
  `;

  if (!rows.length) {
    out.innerHTML = `<div class="empty">No trial posted ${escapeHtml(endpoint)} at week 24.
      Not every trial reports every threshold on both scales.</div>`;
    return;
  }

  out.innerHTML = `
    <div class="ev-table-wrap">
      <table class="ev-table">
        <thead>
          <tr>
            <th>Drug</th>
            <th>How it was given</th>
            <th>Reached ${escapeHtml(threshold)}%</th>
            <th>Comparator arm</th>
            <th>Difference</th>
            <th>At one year</th>
            <th>Trial</th>
          </tr>
        </thead>
        <tbody>${rows.map(evidenceRow).join('')}</tbody>
      </table>
    </div>
  `;
}

function pct(value) {
  return value == null ? '—' : `${Number(value).toFixed(1)}%`;
}

function evidenceRow(r) {
  const control = r.controlled
    ? `${pct(r.control_percent)} <span class="ev-denom">of ${r.control_analysed}</span>`
    : '<span class="ev-unknown" title="This trial had no comparator arm at this endpoint">none</span>';
  const diffClass = r.difference > 0 ? 'ev-diff' : (r.difference < 0 ? 'ev-diff-neg' : 'ev-diff-flat');
  const diff = r.difference != null
    ? `<span class="${diffClass}">${r.difference > 0 ? '+' : ''}${Number(r.difference).toFixed(1)} pts</span>`
    : '<span class="ev-unknown">—</span>';
  const later = r.later
    ? `<span class="ev-later">${pct(r.later.percent)} <span class="ev-denom">of ${r.later.analysed}</span></span>
       <span class="ev-later-note">week ${r.later.week}, no comparator;
       ${Math.round(r.later.retention * 100)}% of the ${r.later.started} still counted</span>`
    : '<span class="ev-unknown">not reported</span>';
  const also = (r.also_reported || []).length
    ? `<span class="ev-also">also ${r.also_reported.map(o =>
        `${escapeHtml(o.trial)}: ${pct(o.percent)} of ${o.analysed}` +
        (o.control_percent != null ? ` vs ${pct(o.control_percent)}` : '')
      ).join(' · ')}</span>`
    : '';
  const url = `https://clinicaltrials.gov/study/${encodeURIComponent(r.trial)}`;
  const primary = r.primary_endpoint
    ? ' <span class="ev-badge" title="This was the trial\'s primary endpoint">primary</span>'
    : '';
  const central = r.assessor === 'central'
    ? ' <span class="ev-badge ev-badge-quiet" title="Blinded central reading, not the site\'s own">central read</span>'
    : '';
  return `
    <tr>
      <td class="ev-agent">${escapeHtml(r.agent)}</td>
      <td class="ev-given">${howGiven(r)}</td>
      <td class="ev-active"><strong>${pct(r.percent)}</strong>
        <span class="ev-denom">of ${r.analysed}</span>${primary}${central}${also}</td>
      <td>${control}</td>
      <td>${diff}</td>
      <td>${later}</td>
      <td><a href="${url}" target="_blank" rel="noopener">${escapeHtml(r.trial)}</a></td>
    </tr>
  `;
}

// ---- candidates (deterministic report) ------------------------------

document.getElementById('btn-candidates-load').addEventListener('click', () => {
  candidatesLoaded = false;
  loadCandidatesReport();
});

async function loadCandidatesReport() {
  const topN = parseInt(document.getElementById('candidates-topn').value, 10);
  const meta = document.getElementById('candidates-meta');
  const out = document.getElementById('candidates-results');
  showLoading(out, `Building evidence-scored candidate report (top ${topN})… this may take 20–40s`);
  meta.innerHTML = '';
  try {
    const res = await fetch(`/api/report/candidates?top_n=${topN}`);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) detail = data.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    const data = await res.json();
    candidatesLoaded = true;
    const corpus = data.corpus || {};
    meta.innerHTML = `
      <span class="trial-stat trial-stat-total"><strong>${(corpus.documents || 0).toLocaleString()}</strong> documents</span>
      <span class="trial-stat"><strong>${corpus.trials || 0}</strong> trials</span>
      <span class="trial-stat"><strong>${corpus.graph_entities || 0}</strong> graph entities</span>
      <span class="trial-stat">Engine v${escapeHtml(data.engine_version || '?')}</span>
    `;
    if (!data.global_top || !data.global_top.length) {
      out.innerHTML = '<div class="empty">No candidates returned.</div>';
      return;
    }
    out.innerHTML = `
      ${renderNotesBlock(data.notes, 'report-notes')}
      ${data.global_top.map(renderReportCandidate).join('')}
    `;
  } catch (err) {
    showError(out, err.message);
  }
}

function renderReportCandidate(c) {
  const evidenceClass = ['strong', 'moderate', 'weak', 'speculative'].includes(c.evidence_strength)
    ? c.evidence_strength : 'speculative';
  const score = c.score || {};
  const scoreLine = `prior ${score.prior_stage || 0} + graph ${score.graph || 0} + trials ${score.trials || 0} + literature ${score.literature || 0}`;
  const mechs = (c.mechanisms || []).slice(0, 3).join(' · ');
  const trials = (c.trial_refs || []).slice(0, 4).map(t => {
    const url = trialExternalUrl(t);
    const id = url
      ? `<a href="${url}" target="_blank">${escapeHtml(t.source_id)}</a>`
      : escapeHtml(t.source_id);
    const phase = (t.phases && t.phases.length) ? t.phases.join(', ') : '—';
    return `<li>${escapeHtml(t.source)}:${id} — ${escapeHtml(t.status || '?')}, ${escapeHtml(phase)}${t.has_results ? ', results' : ''}</li>`;
  }).join('');
  const graph = (c.graph_refs || []).slice(0, 3).map(g =>
    `<li>${escapeHtml(g.subject_name)} —[${escapeHtml(g.predicate)}]→ ${escapeHtml(g.object_name)} (conf=${Number(g.confidence).toFixed(2)})</li>`
  ).join('');
  const papers = (c.literature_refs || []).slice(0, 3).map(p => {
    let link = `${escapeHtml(p.source)}:${escapeHtml(p.source_id)}`;
    if (p.source === 'pubmed') {
      link = `<a href="https://pubmed.ncbi.nlm.nih.gov/${escapeHtml(p.source_id)}/" target="_blank">PMID ${escapeHtml(p.source_id)}</a>`;
    } else if (p.source === 'pmc') {
      link = `<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/${escapeHtml(p.source_id)}/" target="_blank">${escapeHtml(p.source_id)}</a>`;
    }
    return `<li>${link} — ${escapeHtml(truncate(p.title || '(no title)', 120))} (${escapeHtml(String(p.year || '?'))})</li>`;
  }).join('');
  const caveats = (c.caveats || []).map(x => `<li>${escapeHtml(x)}</li>`).join('');
  return `
    <article class="candidate report-candidate">
      <div class="candidate-header">
        <span class="candidate-rank">#${c.rank}</span>
        <span class="candidate-name">${escapeHtml(c.name || '(unnamed)')}</span>
        <span class="evidence ${evidenceClass}">${escapeHtml(c.evidence_strength || 'speculative')}</span>
        <span class="report-score">score ${score.total || 0}</span>
      </div>
      <div class="score-breakdown">${escapeHtml(scoreLine)} · stage ${escapeHtml(c.clinical_stage || '—')}</div>
      ${mechs ? `<div class="candidate-section"><div class="candidate-label">Mechanisms</div><div class="candidate-text">${escapeHtml(mechs)}</div></div>` : ''}
      ${trials ? `<div class="candidate-section"><div class="candidate-label">Trials</div><ul class="report-list">${trials}</ul></div>` : ''}
      ${graph ? `<div class="candidate-section"><div class="candidate-label">Graph</div><ul class="report-list">${graph}</ul></div>` : ''}
      ${papers ? `<div class="candidate-section"><div class="candidate-label">Literature</div><ul class="report-list">${papers}</ul></div>` : ''}
      ${caveats ? `<div class="candidate-section"><div class="candidate-label">Caveats</div><ul class="report-list report-caveats">${caveats}</ul></div>` : ''}
    </article>
  `;
}

// ---- graph ----------------------------------------------------------

let graphStatsLoaded = false;

async function loadGraphStats() {
  const out = document.getElementById('graph-stats');
  out.innerHTML = '<span class="empty">Loading graph stats…</span>';
  try {
    const res = await fetch('/api/graph/stats');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const totals = Object.fromEntries((data.total || []).map(r => [r.label, r.count]));
    const kindBadges = (data.by_kind || []).slice(0, 5).map(r =>
      `<span class="trial-stat"><strong>${r.count}</strong> ${escapeHtml(r.label)}</span>`
    ).join('');
    const predBadges = (data.by_predicate || []).slice(0, 4).map(r =>
      `<span class="trial-stat"><strong>${r.count}</strong> ${escapeHtml(r.label.replace(/_/g, ' '))}</span>`
    ).join('');
    out.innerHTML = `
      <span class="trial-stat trial-stat-total"><strong>${totals.entities || 0}</strong> entities</span>
      <span class="trial-stat trial-stat-total"><strong>${totals.edges || 0}</strong> edges</span>
      ${kindBadges}
      ${predBadges}
    `;
    graphStatsLoaded = true;
  } catch (err) {
    out.innerHTML = `<span class="error">${escapeHtml(err.message)}</span>`;
  }
}

async function loadGraphNeighbors(name) {
  const out = document.getElementById('graph-neighbors');
  showLoading(out, `Loading neighbors of "${name}"…`);
  try {
    const res = await fetch(`/api/graph/neighbors?name=${encodeURIComponent(name)}&limit=40`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.results.length) {
      out.innerHTML = '<div class="empty">No neighbors found.</div>';
      return;
    }
    out.innerHTML = `
      <h3>Neighbors of ${escapeHtml(data.name)}</h3>
      ${data.results.map(renderGraphEdgeRow).join('')}
    `;
  } catch (err) {
    showError(out, err.message);
  }
}

function renderGraphEdgeRow(e) {
  const predicate = String(e.predicate || '').replace(/_/g, ' ');
  const conf = e.confidence != null ? Number(e.confidence).toFixed(2) : '—';
  return `
    <div class="graph-citation">
      <span class="graph-edge">
        <span class="graph-entity">${escapeHtml(e.subject_name)}</span>
        <span class="graph-entity-kind">${escapeHtml(e.subject_kind || '')}</span>
        <span class="graph-predicate">→ ${escapeHtml(predicate)} →</span>
        <span class="graph-entity">${escapeHtml(e.object_name)}</span>
        <span class="graph-entity-kind">${escapeHtml(e.object_kind || '')}</span>
      </span>
      <div class="citation-meta">confidence ${escapeHtml(conf)} · ${escapeHtml(e.extraction_method || '')}</div>
    </div>
  `;
}

document.getElementById('form-graph').addEventListener('submit', async (e) => {
  e.preventDefault();
  const query = document.getElementById('graph-query').value.trim();
  const out = document.getElementById('graph-results');
  const neighbors = document.getElementById('graph-neighbors');
  neighbors.innerHTML = '';
  if (!query) return;

  showLoading(out, `Searching entities for "${query}"…`);
  try {
    const res = await fetch(`/api/graph/search?q=${encodeURIComponent(query)}&limit=25`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.results.length) {
      out.innerHTML = '<div class="empty">No entities match. Run <code>vitiligo graph seed</code> first.</div>';
      return;
    }
    const entities = data.results;
    out.innerHTML = `
      <h3>Entities (${entities.length})</h3>
      ${entities.map((entity, idx) => `
        <article class="hit graph-entity-hit">
          <div class="hit-header">
            <span class="hit-source">${escapeHtml(entity.kind)}:${escapeHtml(entity.key)}</span>
          </div>
          <div class="hit-title">
            <button type="button" class="link-button graph-entity-link" data-idx="${idx}">
              ${escapeHtml(entity.name)}
            </button>
          </div>
          ${entity.aliases && entity.aliases.length ? `<div class="hit-meta">${entity.aliases.slice(0, 4).map(a => escapeHtml(a)).join(' · ')}</div>` : ''}
        </article>
      `).join('')}
    `;
    out.querySelectorAll('.graph-entity-link').forEach(btn => {
      const idx = Number(btn.dataset.idx);
      const name = entities[idx]?.name;
      if (name) btn.addEventListener('click', () => loadGraphNeighbors(name));
    });
  } catch (err) {
    showError(out, err.message);
  }
});

// ---- trials ---------------------------------------------------------

let trialsStatsLoaded = false;

async function loadTrialsStats() {
  const out = document.getElementById('trials-stats');
  out.innerHTML = '<span class="empty">Loading trial stats…</span>';
  try {
    const res = await fetch('/api/trials/stats');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const sourceBadges = (data.by_source || []).map(r =>
      `<span class="trial-stat trial-stat-source"><strong>${r.count}</strong> ${escapeHtml(sourceLabel(r.label))}</span>`
    ).join('');
    const statusBadges = (data.by_status || []).slice(0, 5).map(r =>
      `<span class="trial-stat"><strong>${r.count}</strong> ${escapeHtml(r.label)}</span>`
    ).join('');
    const resultsBadges = (data.by_results || []).map(r =>
      `<span class="trial-stat"><strong>${r.count}</strong> ${escapeHtml(r.label)}</span>`
    ).join('');
    out.innerHTML = `
      <span class="trial-stat trial-stat-total"><strong>${data.total}</strong> total trials</span>
      ${sourceBadges}
      ${statusBadges}
      ${resultsBadges}
    `;
    trialsStatsLoaded = true;
  } catch (err) {
    out.innerHTML = `<span class="error">${escapeHtml(err.message)}</span>`;
  }
}

function sourceLabel(s) {
  if (s === 'ctgov') return 'ClinicalTrials.gov';
  if (s === 'euctr') return 'EU CTR (CTIS)';
  if (s === 'ictrp') return 'WHO ICTRP';
  return s;
}

function trialExternalUrl(t) {
  if (t.source === 'ctgov') return `https://clinicaltrials.gov/study/${encodeURIComponent(t.source_id)}`;
  if (t.source === 'euctr') return `https://euclinicaltrials.eu/ctis-public/view/${encodeURIComponent(t.source_id)}`;
  if (t.source === 'ictrp') {
    return `https://trialsearch.who.int/Trial2.aspx?TrialID=${encodeURIComponent(t.source_id)}`;
  }
  return null;
}

document.getElementById('form-trials').addEventListener('submit', async (e) => {
  e.preventDefault();
  const out = document.getElementById('trials-results');
  const payload = {
    query: document.getElementById('trials-query').value.trim() || null,
    source: document.getElementById('trials-source').value || null,
    status: document.getElementById('trials-status').value || null,
    phase: document.getElementById('trials-phase').value || null,
    country: document.getElementById('trials-country').value.trim() || null,
    has_results: (() => {
      const v = document.getElementById('trials-has-results').value || '';
      if (v === 'true') return true;
      if (v === 'false') return false;
      return null;
    })(),
    limit: parseInt(document.getElementById('trials-limit').value, 10),
    offset: 0,
  };
  showLoading(out, 'Filtering trials…');
  try {
    const data = await postJson('/api/trials/search', payload);
    if (!data.results.length) {
      out.innerHTML = '<div class="empty">No trials match the filters.</div>';
      return;
    }
    const header = `<div class="trials-summary">Showing ${data.results.length} of ${data.total} matching trials</div>`;
    out.innerHTML = header + data.results.map(renderTrial).join('');
  } catch (err) {
    showError(out, err.message);
  }
});

function renderTrial(t) {
  const externalUrl = trialExternalUrl(t);
  const sourceTag = `<span class="trial-source-tag source-${escapeHtml(t.source)}">${escapeHtml(sourceLabel(t.source))}</span>`;
  const phaseLabel = (t.phases && t.phases.length) ? t.phases.join(', ') : '—';
  const interventions = (t.interventions || []).slice(0, 4).map(iv =>
    `<span class="trial-iv"><span class="trial-iv-type">${escapeHtml(iv.type || '?')}</span> ${escapeHtml(iv.name || '?')}</span>`
  ).join('');
  const sponsorText = (t.sponsors || []).slice(0, 2).map(s =>
    `${s.name || '?'}${s.role === 'lead' ? ' (lead)' : ''}`
  ).join(' · ');
  const countries = (t.countries || []).slice(0, 8).map(c =>
    `<span class="tag">${escapeHtml(c)}</span>`
  ).join('');
  const conditions = (t.conditions || []).slice(0, 5).map(c =>
    `<span class="tag">${escapeHtml(c)}</span>`
  ).join('');
  const status = (t.status || 'UNKNOWN').toLowerCase();
  return `
    <article class="trial">
      <div class="trial-header">
        ${sourceTag}
        <span class="trial-id">${externalUrl ? `<a href="${externalUrl}" target="_blank">${escapeHtml(t.source_id)}</a>` : escapeHtml(t.source_id)}</span>
        <span class="trial-status status-${escapeHtml(status)}">${escapeHtml(t.status || 'UNKNOWN')}</span>
        <span class="trial-phase">${escapeHtml(phaseLabel)}</span>
        ${t.has_results ? '<span class="trial-results-badge">has results</span>' : ''}
      </div>
      <div class="trial-title">${escapeHtml(t.brief_title || t.official_title || '(no title)')}</div>
      ${conditions ? `<div class="trial-section"><span class="trial-label">Conditions:</span> ${conditions}</div>` : ''}
      ${interventions ? `<div class="trial-section"><span class="trial-label">Interventions:</span> ${interventions}</div>` : ''}
      ${sponsorText ? `<div class="trial-section"><span class="trial-label">Sponsors:</span> ${escapeHtml(sponsorText)}</div>` : ''}
      ${countries ? `<div class="trial-section"><span class="trial-label">Countries:</span> ${countries}</div>` : ''}
      ${t.summary ? `<div class="trial-summary">${escapeHtml(truncate(t.summary, 600))}</div>` : ''}
      <div class="trial-footer">
        ${t.start_date ? `Started ${escapeHtml(t.start_date)}` : ''}
        ${t.completion_date ? ` · Completion ${escapeHtml(t.completion_date)}` : ''}
        ${t.enrollment_count ? ` · n=${t.enrollment_count}` : ''}
      </div>
    </article>
  `;
}

// ---- init -----------------------------------------------------------

// Trial results is the default panel, so it loads without a tab click.
loadEvidence();
