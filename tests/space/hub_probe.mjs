// Does a Hub link with a fragment open that view? Reads the iframe's src as the Hub set it.
import { launch } from './cdp.mjs';
const b = await launch();
try {
  for (const frag of ['pipeline-trials', 'pipeline-outcomes', 'methods-data']) {
    const p = await b.newPage({ width: 1440, height: 900 });
    await p.goto(`https://huggingface.co/spaces/re-cep/vitiligo-curative-discovery#${frag}`, { wait: 2500 });
    await p.waitFor(`!!document.querySelector('iframe[src*="static.hf.space"]')`, 20000);
    const src = await p.eval(`(document.querySelector('iframe[src*="static.hf.space"]') || {}).src || ''`);
    console.log(`${src.endsWith('#' + frag) ? 'ok  ' : 'FAIL'} #${frag} -> iframe ${src.replace(/^https:\/\//, '').slice(0, 120)}`);
    await p.close();
  }
} finally { await b.close(); }
