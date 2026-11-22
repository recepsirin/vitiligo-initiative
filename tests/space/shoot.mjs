// Screenshots for review.
//   node shoot.mjs <base url> <out dir> [route ...]
// A route may end in "!dialog=<search text>" to open the first matching trial.
import { launch } from './cdp.mjs';
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';

const [, , base, out, ...routes] = process.argv;
mkdirSync(out, { recursive: true });
const b = await launch();
try {
  for (const [name, opts] of [
    ['desktop-light', { width: 1440, height: 900, dark: false }],
    ['desktop-dark', { width: 1440, height: 900, dark: true }],
    ['phone-light', { width: 390, height: 844, scale: 2, mobile: true, dark: false }],
  ]) {
    const p = await b.newPage(opts);
    await p.goto(`${base}/index.html`, { wait: 900 });
    for (const spec of routes) {
      const [route, action] = spec.split('!');
      await p.eval(`location.hash = ${JSON.stringify(route)}`);
      await p.sleep(500);
      if (route.startsWith('pipeline-trials')) await p.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length > 0`);
      if (route.startsWith('genes')) await p.waitFor(`document.querySelectorAll('#gene-body tr.is-clickable').length > 0`);
      const slug = spec.replace(/[^a-z0-9]+/gi, '-');
      if (action && action.startsWith('gene=')) {
        const sym = action.slice(5);
        await p.eval(`(() => { const s = document.querySelector('#gene-search'); s.value = ${JSON.stringify(sym)}; s.dispatchEvent(new Event('input', { bubbles: true })); [...document.querySelectorAll('#gene-body tr')].find(tr => tr.querySelector('.title-btn').textContent === ${JSON.stringify(sym)}).click(); })()`);
        await p.sleep(300);
        await p.shot(join(out, `${name}-${slug}.png`));
        await p.eval(`(() => { document.querySelector('#gene-dialog').close(); const s = document.querySelector('#gene-search'); s.value = ''; s.dispatchEvent(new Event('input', { bubbles: true })); })()`);
      } else if (action && action.startsWith('dialog=')) {
        const q = action.slice(7);
        await p.eval(`(() => { const s = document.querySelector('#trial-search'); s.value = ${JSON.stringify(q)}; s.dispatchEvent(new Event('input', { bubbles: true })); document.querySelector('#trial-body tr').click(); })()`);
        await p.sleep(300);
        await p.shot(join(out, `${name}-${slug}.png`));
        await p.eval(`(() => { document.querySelector('#trial-dialog').close(); const s = document.querySelector('#trial-search'); s.value = ''; s.dispatchEvent(new Event('input', { bubbles: true })); })()`);
      } else {
        await p.shot(join(out, `${name}-${slug}.png`), { full: true });
      }
    }
    if (p.log.errors.length) console.log(name, 'ERRORS:', JSON.stringify(p.log.errors.slice(0, 6)));
    await p.close();
  }
  console.log('done');
} finally {
  await b.close();
}
