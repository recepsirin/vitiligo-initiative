import { launch } from './cdp.mjs';
const b = await launch();
try {
  const p = await b.newPage({ width: 1440, height: 900 });
  await p.goto('https://re-cep-vitiligo-curative-discovery.static.hf.space/index.html#pipeline-trials', { wait: 1500 });
  const ok = await p.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length === 25`, 20000);
  const reqs = p.log.requests.filter((r) => /trials\.json/.test(r.url)).map((r) => `${r.status} ${(r.bytes ?? '?')}B ${r.url.split('?')[0].replace(/^https:\/\/[^/]+\//, '')}`);
  console.log('explorer rendered:', ok, '| pager:', await p.eval(`document.querySelector('#trial-pager span')?.textContent`));
  console.log('trial requests:\n  ' + reqs.join('\n  '));
  console.log('console errors:', JSON.stringify(p.log.errors.slice(0, 3)));
} finally { await b.close(); }
