// No sideways page scroll, and the filter row's behaviour, at in-between widths.
import { launch } from './cdp.mjs';
const [, , base] = process.argv;
const b = await launch(); let bad = 0;
try {
  for (const [w, h] of [[768, 1024], [1100, 800], [1280, 800], [1440, 900], [1920, 1080]]) {
    const p = await b.newPage({ width: w, height: h, dark: false });
    await p.goto(`${base}/index.html#pipeline-trials`, { wait: 900 });
    await p.waitFor(`document.querySelectorAll('#trial-body tr.is-clickable').length > 0`);
    const r = await p.eval(`(() => {
      const tops = [...document.querySelectorAll('.filters > *')].filter(e => e.offsetParent).map(e => Math.round(e.getBoundingClientRect().top));
      const ph = document.querySelector('#trial-search');
      return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
               rows: new Set(tops).size, placeholderFits: ph.scrollWidth <= ph.clientWidth + 1 };
    })()`);
    const ok = r.sw <= r.cw;
    bad += !ok;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${w}px: page ${r.sw}/${r.cw} · filter rows ${r.rows} · search box fits its text: ${r.placeholderFits}`);
    await p.close();
  }
} finally { await b.close(); }
process.exit(bad ? 1 : 0);
