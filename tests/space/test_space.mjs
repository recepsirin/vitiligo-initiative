// End-to-end checks for the Space, driven through headless Chrome.
// Expected values are computed here from the JSON files, independently of app.js.
//   node test_space.mjs <base url> <space dir> <download dir>
import { launch } from './cdp.mjs';
import { readFileSync, readdirSync, mkdirSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const [, , base, dir, dl] = process.argv;
const J = (f) => JSON.parse(readFileSync(join(dir, f), 'utf8'));
const D = {
  pipeline: J('data_pipeline.json'), trials: J('trials.json'), synergy: J('gnn_pairwise_synergy_matrix.json'),
  rerank: J('gnn_reranked_candidates.json'), reverse: J('reverse_target_screening.json'), gnn: J('gnn_train_results.json'),
  cost: J('maintenance-cost.json'), trm: J('trm_signature.json'), anatomy: J('anatomical_model.json'),
  results: J('trial_results.json'), genes: J('genes.json'),
};
const fixed = (n, d) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const int = (n) => fixed(Math.round(n), 0);
const pct = (f, d = 1) => fixed(f * 100, d) + '%';

let pass = 0; const fails = [];
// TRACE=1 prints every check as it passes, so a stalled run shows where it stopped.
const TRACE = !!process.env.TRACE;
function check(name, ok, detail = '') {
  if (ok) { pass++; if (TRACE) console.log(`  ok    ${name}`); }
  else { fails.push(name); console.log(`  FAIL  ${name}${detail ? '  -> ' + String(detail).slice(0, 300) : ''}`); }
}
function eq(name, got, want) { check(name, got === want, `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`); }

// RFC 4180 parser (quotes, doubled quotes, embedded newlines).
function parseCSV(text) {
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
    else if (c !== '\r') cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// The explorer's rules, restated from scratch.
const T = D.trials.trials;
const PUB = 'Published, not registered';
const isPub = (t) => t.registry === PUB;
const hay = (t) => [t.id, t.title, t.official_title, t.acronym, t.interventions, t.sponsor, t.registry, t.journal, t.pmid, t.doi]
  .concat(t.groups || [], t.countries || []).join(' ').toLowerCase();
const yearOf = (t) => { const y = String(t.start || t.year || t.completion || '').slice(0, 4); return /^\d{4}$/.test(y) ? y : null; };
const inPhase = (t, n) => !isPub(t) && (t.phases || []).includes(n);

const b = await launch();
try {
  rmSync(dl, { recursive: true, force: true }); mkdirSync(dl, { recursive: true });
  await b.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: dl, eventsEnabled: false });

  const p = await b.newPage({ width: 1440, height: 900, dark: false });
  const go = async (hash, wait = 350) => { await p.eval(`location.hash = ${JSON.stringify(hash)}`); await p.sleep(wait); };
  const text = (sel) => p.eval(`(document.querySelector(${JSON.stringify(sel)}) || {}).textContent || ''`);
  const count = (sel) => p.eval(`document.querySelectorAll(${JSON.stringify(sel)}).length`);
  const click = (sel) => p.eval(`document.querySelector(${JSON.stringify(sel)}).click()`);
  const setValue = (sel, v, ev) => p.eval(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.value = ${JSON.stringify(v)}; e.dispatchEvent(new Event(${JSON.stringify(ev)}, { bubbles: true })); })()`);
  const visibleView = () => p.eval(`[...document.querySelectorAll('main > .view')].filter(v => !v.hidden).map(v => v.dataset.view).join(',')`);
  const visibleSub = () => p.eval(`[...document.querySelectorAll('main > .view:not([hidden]) [data-subview]')].filter(v => !v.hidden).map(v => v.dataset.subview).join(',')`);

  // ---------------------------------------------------------------- boot
  console.log('boot + overview');
  await p.goto(`${base}/index.html`, { wait: 1200 });
  await p.waitFor(`document.querySelectorAll('.skeleton').length === 0`);
  eq('overview is the landing view', await visibleView(), 'overview');
  eq('no placeholder left unfilled', await count('.skeleton'), 0);
  eq('no error state', await count('.state--error'), 0);
  eq('title', await p.eval('document.title'), 'Vitiligo Translational Discovery Suite');
  const c = D.trials.counts;
  const fills = {
    'syn.screened': int(D.synergy.total_screened_pairs), 'rerank.count': int(D.rerank.candidates.length),
    'anat.sites': String(D.anatomy.sites.length), 'anat.regimens': String(D.anatomy.regimens.length),
    'trm.genes': String(D.trm.panels.core.length + D.trm.panels.circulating.length + D.trm.panels.housekeeping.length),
    'trm.patients': String(D.trm.reference.patients), 'cost.strategies': '4', 'cost.profiles': '3',
    'trials.total': int(c.trials), 'trials.registered': int(c.registered), 'trials.registries': int(c.registries),
    'trials.published': int(c.published_only), 'results.count': int(D.results.counts.results), 'files.count': '11',
    'genes.expressed': int(D.genes.counts.expressed_differently), 'genes.replicated': int(D.genes.counts.replicated),
    'genes.disagreeing': int(D.genes.genes.filter((g) => new Set((g.expression || []).map((r) => r.direction)).size > 1).length),
    'genes.cohorts': ['no', 'one', 'two', 'three', 'four', 'five'][new Set(D.genes.genes.flatMap((g) => (g.expression || []).map((r) => r.source))).size],
  };
  for (const [k, v] of Object.entries(fills)) eq(`fill ${k}`, await text(`[data-fill="${k}"]`), v);
  const got = p.log.requests.map((r) => r.url.split('?')[0].split('/').pop());
  const once = (f) => got.filter((x) => x === f).length === 1;
  check('each small data file fetched once', ['anatomical_model.json', 'gnn_pairwise_synergy_matrix.json',
    'gnn_reranked_candidates.json', 'gnn_train_results.json', 'maintenance-cost.json', 'reverse_target_screening.json', 'trm_signature.json'].every(once), got.join(' '));
  // Live, the host redirects a gzip file to its CDN, whose URL names the file only in its query.
  const fetchedAs = (name) => p.log.requests.filter((r) => {
    let u = r.url; try { u = decodeURIComponent(r.url); } catch {}
    return u.split('?')[0].endsWith('/' + name) || u.includes('filename="' + name + '"');
  });
  for (const [label, file, cap] of [['trials', 'trials.json', 350_000], ['pipeline tables', 'data_pipeline.json', 40_000], ['paper results', 'trial_results.json', 250_000], ['genes', 'genes.json', 150_000]]) {
    const gz = fetchedAs(file + '.gz');
    check(`the ${label} arrive gzipped, once, and the plain file is not fetched`, gz.length === 1 && fetchedAs(file).length === 0, got.join(' '));
    const bytes = gz[0]?.bytes || 0;
    check(`the ${label} transfer stays near the gzipped size`, bytes > 0 && bytes < cap, `${bytes} bytes`);
  }
  check('no favicon request (inline icon)', !got.some((r) => /favicon/.test(r)));

  // -------------------------------------------------------------- routing
  console.log('routing');
  for (const [hash, view, sub] of [
    ['combinations', 'combinations', 'pairs'], ['combinations-reverse', 'combinations', 'reverse'], ['anatomical', 'anatomical', ''],
    ['relapse', 'relapse', ''], ['genes', 'genes', ''], ['economics', 'economics', ''], ['pipeline', 'pipeline', 'trials'], ['pipeline-outcomes', 'pipeline', 'outcomes'],
    ['methods-data', 'methods', 'data'], ['methods-architecture', 'methods', 'architecture'], ['nonsense-route', 'overview', ''], ['PIPELINE-Outcomes', 'pipeline', 'outcomes'],
  ]) {
    await go(hash, 200);
    eq(`#${hash} -> view`, await visibleView(), view);
    eq(`#${hash} -> subview`, await visibleSub(), sub);
  }

  // ------------------------------------------------------ the site model
  // Each cell shows its own value for the chosen time, a measured one or a
  // missing one ("not curated") as well as an assumed one.
  console.log('site model');
  await go('anatomical', 400);
  await p.waitFor(`document.querySelectorAll('#anat-heat tbody td button').length > 0`);
  const shortValue = (t) => { const i = t.indexOf('%'); return i < 0 ? t : t.slice(0, i + 1); };
  for (const [i, t] of D.anatomy.timepoints.entries()) {
    await p.eval(`document.querySelectorAll('#anat-time button')[${i}].click()`);
    await p.sleep(100);
    eq(`every site-model cell shows its value at ${t.label}`,
      await p.eval(`JSON.stringify([...document.querySelectorAll('#anat-heat tbody td button')].map((b) => b.textContent))`),
      JSON.stringify(D.anatomy.sites.flatMap((s) => D.anatomy.regimens.map((r) => shortValue(s.regimens[r.key][t.text])))));
  }
  eq('a cell\'s detail carries the model\'s note', (await text('#anat-detail .card__foot')).trim(), D.anatomy.note);

  // ------------------------------------------------------ the trials view
  console.log('trials explorer');
  await go('pipeline-trials', 600);
  await p.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length > 0`);
  const pager = async () => (await text('#trial-pager span')).trim();
  const expectCount = async (label, n) => eq(label, await pager(), n ? `1–${Math.min(25, n)} of ${int(n)} ${n === 1 ? 'trial' : 'trials'}` : '0 trials');
  eq('first page', await count('#trial-body tr'), 25);
  await expectCount('every trial is listed', T.length);
  eq('rows come in file order (newest first)', await text('#trial-body tr:first-child .title-btn'), T[0].title);
  // The code links name one commit, CODE_AT in app.js; the method link must open the exporting code there.
  const codeAt = (readFileSync(join(dir, 'app.js'), 'utf8').match(/var CODE_AT = '(https:\/\/github\.com\/recepsirin\/vitiligo-initiative\/blob\/[0-9a-f]{40}\/)';/) || [])[1];
  check('the code links name one full commit', Boolean(codeAt), 'CODE_AT not found in app.js');
  eq('the method link points at the exporting code', await p.eval(`document.querySelector('#trial-method').href`),
    `${codeAt}src/vitiligo/trials/explorer.py`);

  // options carry counts computed from the rows
  const opt = (sel, value) => p.eval(`[...document.querySelectorAll('${sel} option')].find(o => o.value === ${JSON.stringify(value)})?.textContent || ''`);
  eq('treatment option counts its rows', await opt('#trial-group', 'JAK inhibitor'), `JAK inhibitor (${int(T.filter((t) => (t.groups || []).includes('JAK inhibitor')).length)})`);
  eq('registry options end with papers', await p.eval(`[...document.querySelectorAll('#trial-registry option')].pop().value`), PUB);
  eq('registry option count', await count('#trial-registry option'), c.registries + 2);

  // search
  for (const q of ['ruxolitinib', 'india', 'chictr', '41781839']) {
    await setValue('#trial-search', q, 'input');
    await expectCount(`search "${q}"`, T.filter((t) => hay(t).includes(q)).length);
  }
  await setValue('#trial-search', 'zzzz-no-such-trial', 'input');
  await expectCount('search with no match', 0);
  check('empty state shown', /No trials match/.test(await text('#trial-body')));
  await click('#trial-pager .btn--link');
  await expectCount('clear filters restores all', T.length);

  // filters, alone and together
  const filters = [
    ['#trial-group', 'JAK inhibitor', (t) => (t.groups || []).includes('JAK inhibitor')],
    ['#trial-group', 'Not classified', (t) => !(t.groups || []).length],
    ['#trial-group', 'Observational study', (t) => (t.groups || []).includes('Observational study')],
    ['#trial-registry', 'CTRI (India)', (t) => t.registry === 'CTRI (India)'],
    ['#trial-registry', PUB, isPub],
    ['#trial-phase', 'Phase 3', (t) => inPhase(t, 3)],
    ['#trial-phase', 'Not applicable', (t) => !isPub(t) && t.phase === 'Not applicable'],
    ['#trial-status', 'Recruiting', (t) => t.status === 'Recruiting'],
  ];
  for (const [sel, v, pred] of filters) {
    await setValue(sel, v, 'change');
    await expectCount(`${sel} = ${v}`, T.filter(pred).length);
    await setValue(sel, '', 'change');
  }
  check('a Phase 2/3 trial counts under Phase 3', T.some((t) => t.phase === 'Phase 2/3') && T.filter((t) => inPhase(t, 3)).length > T.filter((t) => t.phase === 'Phase 3').length);
  await setValue('#trial-group', 'JAK inhibitor', 'change');
  await setValue('#trial-phase', 'Phase 3', 'change');
  await expectCount('treatment + phase together', T.filter((t) => (t.groups || []).includes('JAK inhibitor') && inPhase(t, 3)).length);
  await p.eval(`(() => { const c = document.querySelector('#trial-results'); c.checked = true; c.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await expectCount('+ results posted', T.filter((t) => (t.groups || []).includes('JAK inhibitor') && inPhase(t, 3) && t.results).length);
  await click('#trial-pager .btn--link');
  // Results in papers: every explorer trial that a result is filed under.
  const RESULT_TRIALS = new Set(D.results.results.flatMap((r) => r.trials));
  await p.eval(`(() => { const c = document.querySelector('#trial-papers'); c.checked = true; c.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  await expectCount('results in papers', T.filter((t) => RESULT_TRIALS.has(t.id)).length);
  check('every result is filed under an explorer trial', [...RESULT_TRIALS].every((id) => T.some((t) => t.id === id)));
  await click('#trial-pager .btn--link');
  await expectCount('clear filters resets every control', T.length);
  eq('controls reset', await p.eval(`['#trial-group','#trial-registry','#trial-phase','#trial-status'].map(s => document.querySelector(s).value).join('') + document.querySelector('#trial-results').checked + document.querySelector('#trial-papers').checked`), 'falsefalse');

  // sorting
  await click('#trial-table th[data-sort="enrollment"] button'); await click('#trial-table th[data-sort="enrollment"] button');
  const maxN = Math.max(...T.map((t) => t.enrollment || 0));
  check('sort by enrolment, descending', (await text('#trial-body tr:first-child td:nth-child(5)')).includes(int(maxN)));
  eq('aria-sort set', await p.eval(`document.querySelector('#trial-table th[data-sort="enrollment"]').getAttribute('aria-sort')`), 'descending');
  await click('#trial-table th[data-sort="enrollment"] button');
  await click('#trial-table th[data-sort="year"] button');
  const minYear = T.map(yearOf).filter(Boolean).sort()[0];
  eq('sort by year, ascending', (await text('#trial-body tr:first-child td:nth-child(6)')).trim(), minYear);
  await click('#trial-table th[data-sort="year"] button'); await click('#trial-table th[data-sort="year"] button');
  eq('third click restores file order', await text('#trial-body tr:first-child .title-btn'), T[0].title);

  // paging
  await p.eval(`(() => { const b = [...document.querySelectorAll('#trial-pager button')].find(x => x.textContent === 'Next'); b.focus(); b.click(); })()`);
  eq('next page', await pager(), `26–50 of ${int(T.length)} trials`);
  eq('page 2 starts at row 26', await text('#trial-body tr:first-child .title-btn'), T[25].title);
  check('focus stays on Next', await p.eval(`document.activeElement.textContent === 'Next'`));
  await p.eval(`[...document.querySelectorAll('#trial-pager button')].find(x => x.textContent === 'Previous').click()`);

  // the dialog: a registered trial with placebo-controlled outcome arms
  const DIALOG_ID = 'NCT05583526';
  const truev = T.find((t) => t.id === DIALOG_ID);
  await setValue('#trial-search', DIALOG_ID.toLowerCase(), 'input');
  await click('#trial-body tr:first-child');
  await p.sleep(150);
  check('dialog opens as a modal', await p.eval(`document.querySelector('#trial-dialog').matches(':modal')`));
  eq('dialog title is the official title', await text('#trial-title'), truev.official_title || truev.title);
  eq('dialog links to the registry', await p.eval(`document.querySelector('#trial-link').href`), truev.url);
  eq('link reads as a registry record', await text('#trial-link-text'), 'Open registry record');
  const dialogArms = D.pipeline.curated_outcomes.filter((o) => (o.trial.match(/NCT\d{8}/g) || []).includes(DIALOG_ID));
  check('the dialog trial has active and placebo arms to show', dialogArms.some((o) => /placebo/i.test(o.agent)) && dialogArms.some((o) => !/placebo/i.test(o.agent)));
  eq('dialog lists the trial\'s outcome arms', await count('#trial-outcomes table:not(.table--stack) tbody tr'), dialogArms.length);
  eq('no undefined/NaN/null in the dialog', await p.eval(`/undefined|NaN|\\bnull\\b/.test(document.querySelector('#trial-dialog').innerText)`), false);
  await p.key('Escape', 'Escape', 27);
  check('Escape closes the dialog', await p.eval(`!document.querySelector('#trial-dialog').open`));

  // the dialog: a paper's results, read from the paper
  const TACRO = '15550128';
  const tacroResults = D.results.results.filter((r) => r.trials.includes(TACRO));
  await setValue('#trial-search', TACRO, 'input');
  await click('#trial-body tr:first-child');
  await p.sleep(150);
  eq('paper results in the dialog', await count('#trial-outcomes table.table--stack tbody tr'), tacroResults.length);
  check('… read as the paper prints them', (await text('#trial-outcomes table.table--stack tbody tr:first-child')).includes('19 of 22 (86.4%)'));
  eq('… with the population they were counted in', await text('#trial-outcomes table.table--stack tbody tr:first-child td:nth-child(5)'), 'As observed');
  eq('no undefined/NaN/null in the results dialog', await p.eval(`/undefined|NaN|\\bnull\\b/.test(document.querySelector('#trial-dialog').innerText)`), false);
  await p.key('Escape', 'Escape', 27);
  const busiest = [...RESULT_TRIALS].map((id) => [id, D.results.results.filter((r) => r.trials.includes(id)).length]).sort((a, b) => b[1] - a[1])[0];
  await p.eval(`(() => { const s = document.querySelector('#trial-search'); s.value = ${JSON.stringify(busiest[0])}; s.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await click('#trial-body tr:first-child');
  await p.sleep(200);
  check(`the longest list (${busiest[1]} results) scrolls inside the dialog`, await p.eval(`(() => { const d = document.querySelector('#trial-dialog'); return d.scrollHeight > d.clientHeight && getComputedStyle(d).overflowY !== 'visible'; })()`));
  eq('… and every result is listed', await count('#trial-outcomes table.table--stack tbody tr'), busiest[1]);
  await p.key('Escape', 'Escape', 27);

  // the dialog: a trial known only from its paper
  const paper = T.find((t) => isPub(t) && t.pmid && t.journal);
  await setValue('#trial-search', paper.pmid, 'input');
  await click('#trial-body tr:first-child');
  await p.sleep(150);
  check('paper dialog names the PMID', (await text('#trial-chips')).includes('PMID ' + paper.pmid));
  eq('paper dialog links to PubMed', await p.eval(`document.querySelector('#trial-link').href`), paper.url);
  eq('link reads as the paper', await text('#trial-link-text'), 'Open the paper');
  check('paper dialog shows the journal, not registry fields', (await text('#trial-facts')).includes(paper.journal) && !/Results on registry/.test(await text('#trial-facts')));
  await p.key('Escape', 'Escape', 27);
  await setValue('#trial-search', '', 'input');

  // ---------------------------------------------------------- outcomes
  console.log('published outcomes');
  await go('pipeline-outcomes');
  const O = D.pipeline.curated_outcomes;
  eq('outcome table rows', await count('#outcome-body tr'), O.length);
  check('placebo arms are in the table', O.some((o) => /placebo/i.test(o.agent)));
  eq('no arm line starts or ends with a separator', await p.eval(`[...document.querySelectorAll('#outcome-body .sub')].filter(s => /^\\s*·|·\\s*$/.test(s.textContent)).length`), 0);
  await p.eval(`document.querySelector('#outcome-body button').click()`);
  check('an outcome row opens its trial', await p.waitFor(`document.querySelector('#trial-dialog').open`, 5000));
  eq('… the right one', await text('#trial-chips .chip.mono'), (O[0].trial.match(/NCT\d{8}/) || [])[0]);
  await p.key('Escape', 'Escape', 27);

  const RS = D.results.results;
  await p.waitFor(`document.querySelectorAll('#results-body tr').length > 1`);
  const rpager = async () => (await text('#results-pager span')).trim();
  const expectResults = async (label, n) => eq(label, await rpager(), n ? `1–${Math.min(25, n)} of ${int(n)} ${n === 1 ? 'result' : 'results'}` : '0 results');
  await expectResults('every paper result is listed', RS.length);
  eq('results: first page', await count('#results-body tr'), 25);
  for (const [sel, v, pred] of [
    ['#results-type', 'responders', (r) => r.type === 'responders'],
    ['#results-type', 'comparison', (r) => r.type === 'comparison'],
    ['#results-population', 'per_lesion', (r) => r.population === 'per_lesion'],
    ['#results-population', 'not_reported', (r) => (r.population || 'not_reported') === 'not_reported'],
  ]) {
    await setValue(sel, v, 'change');
    await expectResults(`results ${sel} = ${v}`, RS.filter(pred).length);
    await setValue(sel, '', 'change');
  }
  await setValue('#results-search', TACRO, 'input');
  await expectResults('results: search by trial', RS.filter((r) => r.trials.includes(TACRO)).length);
  await setValue('#results-search', '', 'input');
  const firstTrial = RS[0].trials[0];
  await p.eval(`document.querySelector('#results-body .results-trial').click()`);
  check('a result opens its trial', await p.waitFor(`document.querySelector('#trial-dialog').open`, 5000));
  eq('… the right one', await text('#trial-title'), (T.find((t) => t.id === firstTrial) || {}).official_title || (T.find((t) => t.id === firstTrial) || {}).title);
  await p.key('Escape', 'Escape', 27);
  check('quotes appear only where the file carries one', await p.eval(`document.querySelectorAll('#results-body .quote').length`) === RS.slice(0, 25).filter((r) => r.quote).length);

  // ---------------------------------------------------------------- genes
  console.log('genes');
  const GN = D.genes.genes;
  const partnerCount = new Array(GN.length).fill(0);
  D.genes.pairs.forEach(([a, b]) => { partnerCount[a]++; partnerCount[b]++; });
  // A gene's direction: "mixed" when its cohorts found it moving opposite ways.
  const dirOf = (g) => { const d = new Set((g.expression || []).map((r) => r.direction)); return d.size > 1 ? 'mixed' : [...d][0]; };
  const strongestOf = (g) => (g.expression || []).filter((r) => r.log2fc != null).reduce((best, r) => (!best || Math.abs(r.log2fc) > Math.abs(best.log2fc) ? r : best), null);
  await go('genes', 500);
  await p.waitFor(`document.querySelectorAll('#gene-body tr.is-clickable').length > 0`);
  const gpager = async () => (await text('#gene-pager span')).trim();
  const expectGenes = async (label, n) => eq(label, await gpager(), n ? `1–${Math.min(25, n)} of ${int(n)} ${n === 1 ? 'gene' : 'genes'}` : '0 genes');
  await expectGenes('every gene is listed', GN.length);
  const byEffect = GN.filter(strongestOf).sort((a, b) => Math.abs(strongestOf(b).log2fc) - Math.abs(strongestOf(a).log2fc));
  eq('the strongest expression difference comes first', await text('#gene-body tr:first-child .title-btn'), byEffect[0].symbol);
  const firstCell = D.genes.cell_types[0].cell;
  for (const [sel, kind, v, pred] of [
    ['#gene-replicated', 'check', true, (g) => (g.agreeing || 0) >= 2],
    ['#gene-gwas', 'check', true, (g) => (g.gwas || []).length > 0],
    ['#gene-panel', 'check', true, (g) => Boolean(g.panel)],
    ['#gene-direction', 'select', 'higher', (g) => dirOf(g) === 'higher'],
    ['#gene-direction', 'select', 'mixed', (g) => dirOf(g) === 'mixed'],
    ['#gene-cell', 'select', firstCell, (g) => (g.cells || []).some((c) => c.cell === firstCell)],
  ]) {
    if (kind === 'check') await p.eval(`(() => { const c = document.querySelector('${sel}'); c.checked = true; c.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    else await setValue(sel, v, 'change');
    await expectGenes(`genes: ${sel} = ${v}`, GN.filter(pred).length);
    await click('#gene-pager .btn--link');
  }
  await expectGenes('clear filters restores every gene', GN.length);
  await setValue('#gene-search', 'CXCL', 'input');
  await expectGenes('genes: search by symbol', GN.filter((g) => g.symbol.toUpperCase().includes('CXCL')).length);
  // A gene with every kind of measurement, to open.
  const full = GN.find((g, i) => (g.expression || []).length && (g.cells || []).length && partnerCount[i] > 0);
  await setValue('#gene-search', full.symbol, 'input');
  await p.eval(`[...document.querySelectorAll('#gene-body tr')].find(tr => tr.querySelector('.title-btn').textContent === ${JSON.stringify(full.symbol)}).click()`);
  await p.sleep(150);
  check('the gene dialog opens', await p.eval(`document.querySelector('#gene-dialog').open`));
  eq('… for that gene', await text('#gene-title'), full.symbol);
  eq('… with each cohort result', await p.eval(`document.querySelector('#gene-detail table tbody').children.length`), full.expression.length);
  eq('… and each cell type', await p.eval(`document.querySelectorAll('#gene-detail table')[1].tBodies[0].children.length`), full.cells.length);
  if (full.entrez) check('… linked to NCBI Gene', (await p.eval(`document.querySelector('#gene-link').href`)).endsWith('/gene/' + full.entrez));
  eq('no undefined/NaN/null in the gene dialog', await p.eval(`/undefined|NaN|\\bnull\\b/.test(document.querySelector('#gene-dialog').innerText)`), false);
  // The partners shown are the gene's own, strongest first, computed here from the pairs.
  const fullAt = GN.indexOf(full);
  const mine = D.genes.pairs.filter(([a, b]) => a === fullAt || b === fullAt)
    .map(([a, b, r]) => [a === fullAt ? b : a, r]).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]));
  const partner = await p.eval(`document.querySelector('#gene-detail .chip--button').textContent.split(' · ')[0]`);
  eq('… its strongest co-expressed gene first', partner, GN[mine[0][0]].symbol);
  check('… and how many genes it moves with', (await text('#gene-detail')).includes(`${int(mine.length)} ${mine.length === 1 ? 'gene' : 'genes'} whose expression correlates`));
  await p.eval(`document.querySelector('#gene-detail .chip--button').click()`);
  await p.sleep(150);
  eq('a co-expressed gene opens its own entry', await text('#gene-title'), partner);
  await p.key('Escape', 'Escape', 27);
  // An anti-correlated pair shows r with its sign. A gene with at most 24 partners
  // shows them all, so the pair is on screen whatever the order of ties.
  const partnersOf = (i) => D.genes.pairs.filter(([x, y]) => x === i || y === i).map(([x, y, r]) => [x === i ? y : x, r]);
  const anti = D.genes.pairs.find(([x, , r]) => r < 0 && partnersOf(x).length <= 24);
  check('the genes include an anti-correlated pair to show', Boolean(anti));
  if (anti) {
    const [ga, gb, rv] = anti;
    await setValue('#gene-search', GN[ga].symbol, 'input');
    await p.eval(`[...document.querySelectorAll('#gene-body tr')].find(tr => tr.querySelector('.title-btn').textContent === ${JSON.stringify(GN[ga].symbol)}).click()`);
    await p.sleep(150);
    const chip = await p.eval(`[...document.querySelectorAll('#gene-detail .chip--button')].map(c => c.textContent).find(t => t.startsWith(${JSON.stringify(GN[gb].symbol + ' · ')}))`);
    eq('an anti-correlated partner shows its negative r', chip, `${GN[gb].symbol} · r \u2212${Math.abs(rv).toFixed(2)}`);
    await p.key('Escape', 'Escape', 27);
  }
  await setValue('#gene-search', '', 'input');
  await go('relapse', 500);
  await p.waitFor(`document.querySelectorAll('#trm-gene-body tr.is-clickable').length > 0`);
  eq('the relapse view lists every panel gene', await count('#trm-gene-body tr'), GN.filter((g) => g.panel).length);
  const torn = GN.find((g) => g.panel && dirOf(g) === 'mixed');
  if (torn) {
    const cell = await p.eval(`[...document.querySelectorAll('#trm-gene-body tr')].find(tr => tr.cells[0].textContent === ${JSON.stringify(torn.symbol)}).cells[2].textContent`);
    check(`a panel gene its cohorts disagree on (${torn.symbol}) is shown as mixed, not by its strongest result`, cell.startsWith('Mixed'), cell);
  }
  await p.eval(`document.querySelector('#trm-gene-body tr').click()`);
  check('a panel gene opens the gene dialog', await p.waitFor(`document.querySelector('#gene-dialog').open`, 3000));
  await p.key('Escape', 'Escape', 27);

  // ------------------------------------------------------------ economics
  console.log('economics');
  await go('economics', 500);
  await p.waitFor(`document.querySelectorAll('#econ-body tr').length > 0`);
  const C = D.cost, arms = C.profiles[Object.keys(C.profiles)[0]];
  const perRelapse = (regimen) => p.eval(`[...document.querySelectorAll('#econ-body tr')].find(tr => tr.textContent.includes(${JSON.stringify(regimen)})).lastElementChild.textContent.trim()`);
  eq('a strategy no trial has tested has no cost per relapse prevented', await perRelapse('Twice-Weekly Ruxolitinib'), 'No trial');
  eq('stopping, the comparator, has none either', await perRelapse('Complete Cessation'), '—');
  for (const name of ['Continuous Ruxolitinib', 'Twice-Weekly Tacrolimus']) {
    const arm = arms.find((a) => a.regimen.startsWith(name));
    const v = arm.relapse_prevention.map((r) => r.cost_per_relapse_prevented_usd);
    eq(`${name}: the range across the stop-loss scenarios`, await perRelapse(name), '$' + fixed(Math.min(...v), 0) + '–$' + fixed(Math.max(...v), 0));
  }
  const assumed = await text('#econ-assumptions');
  check('assumptions list every loss-after-stopping scenario', C.assumptions.stop_loss_scenarios.every((sc) => assumed.includes(Math.round(sc.value * 100) + '%')));
  check('assumptions give each strategy its own effect', C.assumptions.maintenance_hazard_ratios.every((m) => assumed.includes(m.hazard_ratio == null ? 'no estimate' : String(m.hazard_ratio))));
  check('nothing says every strategy works equally well', !/equally well|any maintenance strategy|same for every/i.test(assumed + (await text('[data-view="economics"] .lede'))));

  // ------------------------------------------------------- methods & data
  console.log('methods & data');
  await go('methods-data', 600);
  await p.waitFor(`document.querySelectorAll('#data-files > li').length > 1`);
  eq('data files listed', await count('#data-files > li'), 11);
  const jsonLinks = await p.eval(`[...document.querySelectorAll('#data-files a[download]')].map(a => a.getAttribute('href'))`);
  check('every JSON link points at a file that exists', jsonLinks.length === 11 && jsonLinks.every((h) => existsSync(join(dir, h))), jsonLinks.join(' '));
  const reg = await text('#data-registries');
  check('registries listed from the trials file', D.trials.registries.filter((r) => r.name !== PUB).every((r) => reg.includes(`${r.name} (${int(r.trials)})`)), reg.slice(0, 200));
  // Links to new code are commit permalinks, filled in once the code is committed.
  const pendingLinks = await p.eval(`[...document.querySelectorAll('a')].map(a => a.getAttribute('href') || '').filter(h => /PENDING/.test(h))`);
  check('no code link is left pending a commit', pendingLinks.length === 0, pendingLinks.join(' '));
  const codeLinks = await p.eval(`[...document.querySelectorAll('a[href*="github.com"][href*="/blob/"]')].map(a => a.href)`);
  check('every code link names master or a full commit', codeLinks.length > 0 && codeLinks.every((u) => /\/blob\/(master|[0-9a-f]{40})\//.test(u)), codeLinks.join(' '));

  // ------------------------------------------------------------- exports
  console.log('CSV exports');
  const grab = async (name, clickExpr, expectRows, verify) => {
    const before = new Set(readdirSync(dl));
    await p.eval(clickExpr);
    let file = null;
    for (let i = 0; i < 60 && !file; i++) { await p.sleep(100); file = readdirSync(dl).find((f) => !before.has(f) && f.endsWith('.csv')); }
    if (!file) return check(`${name}: file saved`, false, 'no download appeared');
    const raw = readFileSync(join(dl, file), 'utf8');
    check(`${name}: starts with a UTF-8 BOM`, raw.charCodeAt(0) === 0xfeff);
    const rows = parseCSV(raw.replace(/^﻿/, ''));
    eq(`${name}: data rows`, rows.length - 1, expectRows);
    check(`${name}: every row has the header's width`, rows.every((r) => r.length === rows[0].length));
    if (verify) verify(rows);
    rmSync(join(dl, file)); // a same-named download would otherwise hide the next one
  };
  const btn = (label) => `[...document.querySelectorAll('#data-files button')].find(b => b.textContent.trim() === ${JSON.stringify(label)}).click()`;
  const inItem = (file) => `[...document.querySelectorAll('#data-files > li')].find(li => li.textContent.includes(${JSON.stringify(file)})).querySelector('button').click()`;
  await grab('trials (data page)', inItem('trials.json'), T.length, (rows) => {
    const h = rows[0], col = (n) => h.indexOf(n);
    // A cell that a spreadsheet would run as a formula is written with a leading apostrophe.
    const asWritten = (v) => (/^[=+\-@\t\r]/.test(v) ? "'" + v : v);
    check('trials: every title round-trips', T.every((t, i) => rows[i + 1][col('Title')] === asWritten(t.title)));
    check('trials: a title starting with "-" is guarded', T.some((t) => t.title.startsWith('-')));
    check('trials: treatment groups joined', T.every((t, i) => rows[i + 1][col('Treatment groups')] === (t.groups || []).join('; ')));
    check('trials: papers carry no registry phase or results flag', T.every((t, i) => !isPub(t) || (rows[i + 1][col('Phase')] === '' && rows[i + 1][col('Results posted on registry')] === '')));
  });
  await grab('outcomes', btn('Outcomes CSV'), O.length);
  await grab('GWAS', btn('GWAS CSV'), D.pipeline.gwas.length, (rows) => {
    check('GWAS: the effect is headed OR or beta, never odds ratio alone', rows[0].includes('OR or beta') && !rows[0].includes('Odds ratio'));
    const ci = rows[0].indexOf('95% CI');
    check('GWAS: a beta keeps the interval text that marks it', rows.some((r) => /unit (increase|decrease)/.test(r[ci])));
  });
  await grab('NIH awards', btn('NIH awards CSV'), D.pipeline.nih.length, (rows) => {
    const h = rows[0];
    check('NIH: dates are the records\' own start and end, no timeline', h.includes('Project start') && h.includes('Project end') && !h.includes('Timeline'));
    check('NIH: every award row has its fiscal year', rows.slice(1).every((r) => /^\d{4}$/.test(r[h.indexOf('Fiscal year')])));
  });
  const expressionTotal = D.genes.genes.reduce((n, g) => n + (g.expression || []).length, 0);
  await grab('genes', btn('Genes CSV'), D.genes.genes.length);
  await grab('gene expression results', btn('Expression CSV'), expressionTotal);
  await grab('co-expression pairs', btn('Pairs CSV'), D.genes.pairs.length);
  await grab('paper results', `[...document.querySelectorAll('#data-files > li')].find(li => li.textContent.includes('trial_results.json')).querySelector('button').click()`, D.results.results.length, (rows) => {
    const h = rows[0], q = h.indexOf('Quote'), pop = h.indexOf('Counted in');
    check('results CSV: a quote only where the file has one', D.results.results.every((r, i) => (rows[i + 1][q] !== '') === Boolean(r.quote)));
    check('results CSV: every row says what it was counted in, or nothing', rows.slice(1).every((r) => ['As observed', 'Per lesion', 'LOCF', 'NRI', 'Not reported', ''].includes(r[pop])));
  });
  await go('pipeline-outcomes', 400);
  await setValue('#results-type', 'relapse', 'change');
  await grab('paper results (filtered view)', `document.querySelector('#results-csv').click()`, D.results.results.filter((r) => r.type === 'relapse').length);
  await setValue('#results-type', '', 'change');
  await go('pipeline-trials', 400);
  await setValue('#trial-registry', 'EU CTIS', 'change');
  await grab('trials (filtered view)', `document.querySelector('#trial-csv').click()`, T.filter((t) => t.registry === 'EU CTIS').length);
  await setValue('#trial-registry', '', 'change');

  // ---------------------------------------------- whole-page invariants
  console.log('invariants across every view');
  const ALL = ['overview', 'combinations-pairs', 'combinations-rerank', 'combinations-reverse', 'anatomical', 'relapse', 'genes', 'economics',
    'pipeline-trials', 'pipeline-outcomes', 'methods-dossiers', 'methods-data', 'methods-architecture'];
  for (const r of ALL) {
    await go(r, 300);
    const junk = await p.eval(`(() => { const t = document.querySelector('main > .view:not([hidden])').innerText; const m = t.match(/undefined|NaN|\\[object|\\bnull\\b|Infinity/); return m ? m[0] + ' … ' + t.slice(Math.max(0, m.index - 60), m.index + 40) : ''; })()`);
    eq(`${r}: no undefined/NaN/null in the text`, junk, '');
    eq(`${r}: every control has a name`, await p.eval(`[...document.querySelectorAll('main > .view:not([hidden]) button, main > .view:not([hidden]) a, .topbar a, .topbar button')].filter(e => e.offsetParent !== null && !(e.textContent.trim() || e.getAttribute('aria-label'))).length`), 0);
    eq(`${r}: every field has a label`, await p.eval(`[...document.querySelectorAll('main > .view:not([hidden]) input, main > .view:not([hidden]) select')].filter(e => e.offsetParent !== null && !(e.labels && e.labels.length) && !e.getAttribute('aria-label')).map(e => e.id).join(',')`), '');
    eq(`${r}: no error state`, await count('main > .view:not([hidden]) .state--error'), 0);
  }
  eq('ids are unique', await p.eval(`(() => { const ids = [...document.querySelectorAll('[id]')].map(e => e.id); return ids.length - new Set(ids).size; })()`), 0);
  eq('no inline event handlers', await p.eval(`[...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => a.name.startsWith('on'))).length`), 0);
  check('no console errors or exceptions (desktop run)', p.log.errors.length === 0, JSON.stringify(p.log.errors.slice(0, 5)));
  await p.close();

  // ------------------------------------------------------------ fallbacks
  console.log('fallbacks');
  for (const [label, opts] of [
    ['gzip twins unavailable', { block: ['*.json.gz'] }],
    ['no DecompressionStream in the browser', { before: 'delete window.DecompressionStream;' }],
  ]) {
    const f = await b.newPage({ width: 1280, height: 800, dark: false, before: opts.before || null });
    if (opts.block) await f.s('Network.setBlockedURLs', { urls: opts.block });
    await f.goto(`${base}/index.html#pipeline-trials`, { wait: 800 });
    // Uncompressed, the trials route fetches about 3.5 MB. On the live host the first
    // such load after a deploy took 51.6 s, later ones 3.9-7.5 s (2026-11-21).
    const ok = await f.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length === 25`, 60000);
    check(`${label}: the explorer still loads`, ok);
    check(`${label}: from the plain files`, ['/trials.json', '/data_pipeline.json', '/trial_results.json'].every((name) => f.log.requests.some((r) => r.url.split('?')[0].endsWith(name))));
    eq(`${label}: no error state`, await f.eval(`document.querySelectorAll('.state--error').length`), 0);
    // The genes load late, so whether their file was requested yet says nothing here;
    // their own view must load from the plain file.
    await f.eval(`location.hash = '#genes'`);
    check(`${label}: the gene explorer loads from its plain file`,
      (await f.waitFor(`document.querySelectorAll('#gene-body tr.is-clickable').length > 0`, 60000))
        && f.log.requests.some((r) => r.url.split('?')[0].endsWith('/genes.json')));
    await f.close();
  }

  // A secondary file that cannot be loaded at all must not take the trials list down with it.
  {
    const f = await b.newPage({ width: 1280, height: 800, dark: false });
    await f.s('Network.setBlockedURLs', { urls: ['*trial_results.json*'] });
    await f.goto(`${base}/index.html#pipeline-trials`, { wait: 800 });
    check('paper results unavailable: the trials list still loads', await f.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length === 25`, 15000));
    eq('paper results unavailable: no error in the trials list', await f.eval(`document.querySelectorAll('[data-subview="trials"] .state--error').length`), 0);
    check('paper results unavailable: the "Results in papers" filter is hidden', await f.eval(`document.querySelector('#trial-papers').closest('label').hidden`));
    await f.eval(`document.querySelector('#trial-body tr.is-clickable').click()`);
    check('paper results unavailable: a trial still opens', await f.waitFor(`document.querySelector('#trial-dialog').open`, 3000));
    await f.eval(`document.querySelector('#trial-dialog').close()`);
    await f.eval(`location.hash = '#pipeline-outcomes'`);
    await f.waitFor(`document.querySelectorAll('#outcome-body button').length > 0`, 15000);
    await f.eval(`document.querySelector('#outcome-body button').click()`);
    check('paper results unavailable: a published outcome opens its trial', await f.waitFor(`document.querySelector('#trial-dialog').open`, 5000));
    await f.close();
  }

  // --------------------------------------------------------------- phones
  console.log('phone layout (390px)');
  const ph = await b.newPage({ width: 390, height: 844, scale: 2, mobile: true, dark: false });
  await ph.goto(`${base}/index.html`, { wait: 1000 });
  for (const r of ALL) {
    await ph.eval(`location.hash = ${JSON.stringify(r)}`); await ph.sleep(350);
    if (r === 'pipeline-trials') await ph.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length > 0`);
    const o = await ph.eval(`({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })`);
    check(`${r}: no sideways page scroll`, o.sw <= o.cw, `scrollWidth ${o.sw} > ${o.cw}`);
    const tiny = await ph.eval(`(() => { const v = document.querySelector('main > .view:not([hidden])'); const w = document.createTreeWalker(v, NodeFilter.SHOW_TEXT); let n, min = 99, sample = ''; while ((n = w.nextNode())) { if (!n.nodeValue.trim()) continue; const el = n.parentElement; if (el.closest('sub, sup') || el.offsetParent === null) continue; const fs = parseFloat(getComputedStyle(el).fontSize); if (fs < min) { min = fs; sample = n.nodeValue.trim().slice(0, 30); } } return min + '|' + sample; })()`);
    check(`${r}: smallest text is at least 12px`, parseFloat(tiny) >= 12, tiny);
  }
  eq('phone: ten trials per page', await ph.eval(`(location.hash = 'pipeline-trials', new Promise(r => setTimeout(() => r(document.querySelectorAll('#trial-body tr.is-clickable').length), 400)))`), 10);
  check('no console errors or exceptions (phone run)', ph.log.errors.length === 0, JSON.stringify(ph.log.errors.slice(0, 5)));
  await ph.close();
} finally {
  await b.close();
}
console.log(`\n${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
