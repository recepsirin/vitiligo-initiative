// Minimal Chrome DevTools Protocol driver (no dependencies; Node >= 22).
// Launches headless Chrome, opens pages, evaluates JS, takes screenshots,
// and records console errors / uncaught exceptions / failed requests.
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function launch() {
  const profile = mkdtempSync(join(tmpdir(), 'cdp-profile-'));
  const proc = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--hide-scrollbars', '--force-color-profile=srgb', '--disable-gpu',
    '--disable-component-update', '--disable-background-networking', '--disable-sync', 'about:blank',
  ], { stdio: 'ignore' });

  const portFile = join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 200 && !existsSync(portFile); i++) await sleep(50);
  if (!existsSync(portFile)) throw new Error('Chrome did not start');
  const [port, path] = readFileSync(portFile, 'utf8').trim().split('\n');
  const ws = new WebSocket(`ws://127.0.0.1:${port}${path}`);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let nextId = 1;
  const pending = new Map();
  const listeners = new Set();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(`${msg.error.message} ${msg.error.data || ''}`));
      else resolve(msg.result);
    } else if (msg.method) {
      for (const l of listeners) l(msg);
    }
  };
  // A call Chrome never answers would otherwise hang the run without a word.
  const SEND_TIMEOUT = 60000;
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = nextId++;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`DevTools ${method} got no reply in ${SEND_TIMEOUT / 1000} s: ${JSON.stringify(params).slice(0, 200)}`));
    }, SEND_TIMEOUT);
    pending.set(id, {
      resolve: (v) => { clearTimeout(timer); resolve(v); },
      reject: (e) => { clearTimeout(timer); reject(e); },
    });
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });

  async function newPage({ width = 1440, height = 900, scale = 1, mobile = false, dark = null, before = null } = {}) {
    const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
    const s = (m, p) => send(m, p, sessionId);
    const log = { errors: [], console: [], failed: [], requests: [] };
    listeners.add((msg) => {
      if (msg.sessionId !== sessionId) return;
      const p = msg.params;
      if (msg.method === 'Runtime.exceptionThrown') {
        const d = p.exceptionDetails;
        log.errors.push(`${d.text} ${d.exception?.description || ''} @${d.url || ''}:${d.lineNumber}`);
      } else if (msg.method === 'Runtime.consoleAPICalled') {
        const text = p.args.map((a) => a.value ?? a.description ?? '').join(' ');
        log.console.push(`[${p.type}] ${text}`);
        if (p.type === 'error') log.errors.push(`console.error: ${text}`);
      } else if (msg.method === 'Log.entryAdded') {
        if (p.entry.level === 'error') log.errors.push(`log: ${p.entry.text} ${p.entry.url || ''}`);
      } else if (msg.method === 'Network.loadingFailed') {
        log.failed.push(`${p.errorText} (${p.requestId})`);
      } else if (msg.method === 'Network.responseReceived') {
        const r = p.response;
        log.requests.push({ url: r.url, status: r.status, type: p.type, mime: r.mimeType,
          enc: r.headers['content-encoding'] || r.headers['Content-Encoding'] || '', id: p.requestId });
      } else if (msg.method === 'Network.loadingFinished') {
        const r = log.requests.find((x) => x.id === p.requestId);
        if (r) r.bytes = p.encodedDataLength;
      }
    });
    await s('Page.enable'); await s('Runtime.enable'); await s('Log.enable'); await s('Network.enable');
    await s('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: scale, mobile });
    if (dark !== null) {
      await s('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }] });
    }
    if (before) await s('Page.addScriptToEvaluateOnNewDocument', { source: before });

    const page = {
      log, s,
      async goto(url, { wait = 800 } = {}) {
        const loaded = new Promise((res) => {
          const l = (msg) => { if (msg.sessionId === sessionId && msg.method === 'Page.loadEventFired') { listeners.delete(l); res(); } };
          listeners.add(l);
        });
        await s('Page.navigate', { url });
        await Promise.race([loaded, sleep(20000)]);
        await sleep(wait);
      },
      async eval(expr) {
        const r = await s('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true, userGesture: true });
        if (r.exceptionDetails) throw new Error(`eval failed: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}\n  expr: ${expr.slice(0, 200)}`);
        return r.result.value;
      },
      async waitFor(expr, timeout = 15000) {
        const t0 = Date.now();
        while (Date.now() - t0 < timeout) {
          if (await this.eval(expr)) return true;
          await sleep(100);
        }
        return false;
      },
      async shot(file, { full = false } = {}) {
        let params = { format: 'png' };
        if (full) {
          const { cssContentSize } = await s('Page.getLayoutMetrics');
          params = { ...params, captureBeyondViewport: true,
            clip: { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 12000), scale: 1 } };
        }
        const { data } = await s('Page.captureScreenshot', params);
        writeFileSync(file, Buffer.from(data, 'base64'));
        return file;
      },
      async key(key, code = key, keyCode = 0) {
        // Enter only activates a control when the key event carries its text.
        const text = key === 'Enter' ? '\r' : undefined;
        await s('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode, ...(text ? { text } : {}) });
        await s('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
        await sleep(60);
      },
      sleep,
      async close() { await send('Target.closeTarget', { targetId }); },
    };
    return page;
  }

  return {
    newPage,
    send,
    async close() {
      try { await send('Browser.close'); } catch {}
      proc.kill();
      await sleep(200);
      try { rmSync(profile, { recursive: true, force: true }); } catch {}
    },
  };
}
