// Vitiligo Initiative — Evidence Engine UI

const tabs = document.querySelectorAll('.tab');
const panels = {
  search: document.getElementById('panel-search'),
  ask: document.getElementById('panel-ask'),
  hypothesize: document.getElementById('panel-hypothesize'),
};

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    Object.values(panels).forEach(p => p.classList.add('hidden'));
    panels[tab.dataset.tab].classList.remove('hidden');
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
  if (item.source && item.source_id) {
    if (item.source === 'pubmed') {
      bits.push(`<a href="https://pubmed.ncbi.nlm.nih.gov/${escapeHtml(item.source_id)}/" target="_blank">PMID ${escapeHtml(item.source_id)}</a>`);
    } else if (item.source === 'pmc') {
      bits.push(`<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/${escapeHtml(item.source_id)}/" target="_blank">${escapeHtml(item.source_id)}</a>`);
    }
  }
  return bits.join(' • ');
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
      if (data.detail) detail = data.detail;
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
          <span class="hit-score">score ${r.score.toFixed(3)}</span>
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

// ---- ask ------------------------------------------------------------

document.getElementById('form-ask').addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = document.getElementById('ask-question').value.trim();
  const topK = parseInt(document.getElementById('ask-topk').value, 10);
  const out = document.getElementById('ask-result');
  if (!question) return;

  showLoading(out, 'Reasoning over the corpus…');
  try {
    const data = await postJson('/api/ask', { question, top_k: topK });
    const linkified = linkifyCitations(escapeHtml(data.answer));
    out.innerHTML = `
      <div class="answer">${linkified}</div>
      <div class="citations">
        <h3>Sources (${data.citations.length})</h3>
        ${data.citations.map(renderCitation).join('')}
      </div>
    `;
  } catch (err) {
    showError(out, err.message);
  }
});

function linkifyCitations(html) {
  // Turn [1], [2], [1, 3] into clickable cite spans pointing to the citation list anchors.
  return html.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (m, group) => {
    const indices = group.split(',').map(s => s.trim());
    return indices.map(i => `<a class="cite" href="#cite-${i}">[${i}]</a>`).join('');
  });
}

function renderCitation(c) {
  const meta = metaBits(c);
  return `
    <div class="citation" id="cite-${c.index}">
      <span class="citation-index">[${c.index}]</span>
      <span>${escapeHtml(c.title || '(no title)')}</span>
      <div class="citation-meta">${meta}</div>
    </div>
  `;
}

// ---- hypothesize ----------------------------------------------------

document.getElementById('form-hypothesize').addEventListener('submit', async (e) => {
  e.preventDefault();
  const intent = document.getElementById('hyp-intent').value.trim();
  const topK = parseInt(document.getElementById('hyp-topk').value, 10);
  const out = document.getElementById('hyp-result');
  if (!intent) return;

  showLoading(out, 'Generating ranked candidates… this may take 20–60s');
  try {
    const data = await postJson('/api/hypothesize', { intent, top_k: topK });
    const candidatesHtml = (data.candidates || []).map(renderCandidate).join('');
    const citationsHtml = (data.citations || []).map(renderCitation).join('');
    out.innerHTML = `
      ${data.notes ? `<div class="hyp-notes">${escapeHtml(data.notes)}</div>` : ''}
      ${candidatesHtml || '<div class="empty">No candidates returned.</div>'}
      <div class="citations">
        <h3>Retrieved papers (${data.citations ? data.citations.length : 0})</h3>
        ${citationsHtml}
      </div>
    `;
  } catch (err) {
    showError(out, err.message);
  }
});

function renderCandidate(c) {
  const evidenceClass = ['strong', 'moderate', 'weak', 'speculative'].includes(c.evidence_strength) ? c.evidence_strength : 'speculative';
  const cites = (c.citation_indices || []).map(i => `<a class="cite" href="#cite-${i}">[${i}]</a>`).join(' ');
  return `
    <article class="candidate">
      <div class="candidate-header">
        <span class="candidate-name">${escapeHtml(c.name || '(unnamed)')}</span>
        <span class="candidate-kind">${escapeHtml(c.kind || '')}</span>
        <span class="evidence ${evidenceClass}">${escapeHtml(c.evidence_strength || 'speculative')}</span>
      </div>
      ${c.mechanism ? `<div class="candidate-section"><div class="candidate-label">Mechanism</div><div class="candidate-text">${escapeHtml(c.mechanism)}</div></div>` : ''}
      ${c.rationale ? `<div class="candidate-section"><div class="candidate-label">Rationale</div><div class="candidate-text">${escapeHtml(c.rationale)}</div></div>` : ''}
      ${c.risks_or_caveats ? `<div class="candidate-section"><div class="candidate-label">Risks &amp; caveats</div><div class="candidate-text">${escapeHtml(c.risks_or_caveats)}</div></div>` : ''}
      ${cites ? `<div class="candidate-citations">${cites}</div>` : ''}
    </article>
  `;
}
