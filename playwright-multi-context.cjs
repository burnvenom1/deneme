// playwright-multi-context.cjs
const fs = require('fs');
const path = require('path');
const { chromium, request: playwrightRequest } = require('playwright-core');
const { randomUUID } = require('crypto');
const {
  getWebGLSpoofScript,
  getCanvasSpoofScript,
  getAudioContextSpoofScript,
  getHardwareInfoSpoofScript,
  getWebdriverSpoofScript,
  getPluginAndPermissionsSpoofScript
} = require('./spoofing-scripts.cjs');

const LOGS_DIR = 'logs';
const SCREENSHOTS_DIR = 'screenshots';
if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });
if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

const logFile = path.join(LOGS_DIR, 'run.log');
function log() {
  const args = Array.from(arguments);
  const line = `[${new Date().toISOString()}] ${args.map(a => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')}`;
  console.log(line);
  try { fs.appendFileSync(logFile, line + '\n'); } catch (e) {}
}

const CONTEXTS = process.env.CONTEXTS ? Math.max(1, parseInt(process.env.CONTEXTS, 10)) : 3;
const TOR_BASE_PORT = process.env.TOR_BASE_PORT ? parseInt(process.env.TOR_BASE_PORT, 10) : 9050;
const HEADLESS = (typeof process.env.HEADLESS === 'undefined') ? true : (String(process.env.HEADLESS).toLowerCase() !== 'false');
const CHROME_PATH = process.env.CHROME_PATH || '/usr/bin/chromium-browser';
const API_BASE = process.env.API_BASE_URL || null;
const API_TOKEN = process.env.API_TOKEN || null;

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
function getBackoff(attempt, base = 500, max = 15000) {
  const cap = Math.min(max, base * Math.pow(2, attempt));
  return Math.floor(Math.random() * cap);
}
async function retry(fn, attempts = 4) {
  for (let i = 0; i < attempts; i++) {
    try { return await fn(); }
    catch (err) {
      const wait = getBackoff(i);
      log(`Retry ${i+1}/${attempts} after error: ${err && err.message ? err.message : err}. waiting ${wait}ms`);
      await sleep(wait);
    }
  }
  throw new Error('Max retries reached');
}

function buildProxyList() {
  const arr = [];
  for (let i = 0; i < CONTEXTS; i++) arr.push(`socks5://127.0.0.1:${TOR_BASE_PORT + i}`);
  return arr;
}

async function fetchTasksFromApi() {
  if (!API_BASE || !API_TOKEN) return null;
  const req = await playwrightRequest.newContext({ baseURL: API_BASE, extraHTTPHeaders: { Authorization: `Bearer ${API_TOKEN}`, Accept: 'application/json' }, timeout: 30000 });
  try {
    const res = await req.get('/tasks');
    if (!res.ok()) throw new Error(`API tasks fetch failed: ${res.status()}`);
    return await res.json();
  } finally { await req.dispose(); }
}
async function postResultToApi(taskId, result) {
  if (!API_BASE || !API_TOKEN) return null;
  const req = await playwrightRequest.newContext({ baseURL: API_BASE, extraHTTPHeaders: { Authorization: `Bearer ${API_TOKEN}`, 'Content-Type': 'application/json', Accept: 'application/json' }, timeout: 30000 });
  try {
    const res = await req.post(`/tasks/${taskId}/result`, { data: result });
    if (!res.ok()) throw new Error(`API post failed: ${res.status()}`);
    return await res.json();
  } finally { await req.dispose(); }
}

function findChromium() {
  const candidates = [CHROME_PATH, '/usr/bin/chromium-browser', '/usr/bin/chromium', '/snap/bin/chromium'];
  for (const p of candidates) {
    if (!p) continue;
    try { if (fs.existsSync(p)) return p; } catch(e) {}
  }
  return undefined;
}

(async () => {
  log('START playwright-multi-context (CJS)');
  log('CONFIG', { CONTEXTS, TOR_BASE_PORT, CHROME_PATH, HEADLESS, API_BASE: !!API_BASE });

  const proxies = buildProxyList();
  log('Proxies:', proxies);

  const browserExec = findChromium();
  if (!browserExec) {
    log('Warning: Could not locate chromium executable on runner. Playwright may still use an installed browser; if launch fails consider adjusting CHROME_PATH.');
  } else {
    log('Chromium executable path:', browserExec);
  }

  let browser;
  try {
    browser = await chromium.launch({
      headless: HEADLESS,
      executablePath: browserExec,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--lang=tr-TR',
        '--timezone=Europe/Istanbul',
        '--disable-web-security',
        '--disable-extensions',
        '--disable-popup-blocking',
        '--disable-default-apps',
        '--disable-infobars',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage'
      ],
      timeout: 45000
    });
  } catch (e) {
    log('Browser launch failed:', e && e.message ? e.message : e);
    process.exit(2);
  }

  try {
    const tasksFromApi = await (API_BASE && API_TOKEN ? retry(fetchTasksFromApi, 3).catch(err => { log('fetchTasksFromApi failed', err && err.message); return null; }) : null);
    const workItems = Array.isArray(tasksFromApi) && tasksFromApi.length ? tasksFromApi : [
      { id: 'demo-1', url: 'https://giris.hepsiburada.com', fields: [], clicks: [], successSelector: null }
    ];

    const toProcess = workItems.slice(0, CONTEXTS);
    log('Work items', toProcess.map(w => w.id));

    const workers = toProcess.map((task, idx) => (async () => {
      const proxy = proxies[idx] || null;
      const seed = randomUUID().slice(0,8) + '-' + idx;
      log(`Worker[${idx}] start task=${task.id} proxy=${proxy} seed=${seed}`);

      const ctxOptions = {
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport: { width: 1280, height: 720 },
        locale: 'tr-TR',
        timezoneId: 'Europe/Istanbul',
        geolocation: { latitude: 41.0082, longitude: 28.9784, accuracy: 10 },
        permissions: []
      };
      if (proxy) ctxOptions.proxy = { server: proxy };

      const context = await browser.newContext(ctxOptions);

      await context.addInitScript(getWebGLSpoofScript(seed));
      await context.addInitScript(getHardwareInfoSpoofScript(seed));
      await context.addInitScript(getWebdriverSpoofScript());
      await context.addInitScript(getCanvasSpoofScript(seed));
      await context.addInitScript(getAudioContextSpoofScript(seed));
      await context.addInitScript(getPluginAndPermissionsSpoofScript());

      const page = await context.newPage();
      await page.route('**/*', route => {
        const t = route.request().resourceType();
        if (['image','stylesheet','font','media'].includes(t)) route.abort();
        else route.continue();
      });

      try {
        await retry(() => page.goto(task.url, { waitUntil: 'domcontentloaded', timeout: 30000 }), 4);
        log(`Worker[${idx}] navigated to ${task.url}`);

        // visible IP via api.ipify
        try {
          const ipInfo = await page.evaluate(async () => {
            try { const r = await fetch('https://api.ipify.org?format=json', { cache: 'no-store' }); return await r.json(); }
            catch (e) { return { error: String(e) }; }
          });
          const visibleIP = ipInfo && ipInfo.ip ? ipInfo.ip : `error:${ipInfo && ipInfo.error ? ipInfo.error : 'unknown'}`;
          log(`Worker[${idx}] visible IP: ${visibleIP}`);
          fs.appendFileSync(path.join(LOGS_DIR, 'ips.csv'), `${task.id},${idx},${visibleIP},${new Date().toISOString()}\n`);
        } catch (e) {
          log(`Worker[${idx}] ip fetch failed: ${e && e.message}`);
        }

        if (Array.isArray(task.fields)) {
          for (const f of task.fields) {
            try {
              await page.waitForSelector(f.selector, { timeout: 4000 });
              await page.fill(f.selector, f.value);
              log(`Worker[${idx}] filled ${f.selector}`);
            } catch (e) {
              log(`Worker[${idx}] field ${f.selector} error: ${e && e.message}`);
            }
          }
        }

        if (Array.isArray(task.clicks)) {
          for (const sel of task.clicks) {
            try {
              await page.waitForSelector(sel, { timeout: 4000 });
              await Promise.all([ page.click(sel), page.waitForTimeout(400) ]);
              log(`Worker[${idx}] clicked ${sel}`);
            } catch (e) {
              log(`Worker[${idx}] click ${sel} error: ${e && e.message}`);
            }
          }
        }

        const fname = `${SCREENSHOTS_DIR}/screenshot-${task.id || 't'+idx}-${Date.now()}.png`;
        await page.screenshot({ path: fname }).catch(e => log('screenshot fail', e && e.message));
        log(`Worker[${idx}] screenshot saved: ${fname}`);

        const result = { status: 'done', screenshot: fname, timestamp: new Date().toISOString() };
        if (API_BASE && API_TOKEN) {
          try { await retry(() => postResultToApi(task.id || ('t'+idx), result), 3); log(`Worker[${idx}] result posted`); }
          catch (e) { log(`Worker[${idx}] postResult failed: ${e && e.message}`); }
        }

      } catch (err) {
        log(`Worker[${idx}] fatal: ${err && err.message ? err.message : String(err)}`);
        const result = { status: 'error', error: err && err.message ? err.message : String(err), timestamp: new Date().toISOString() };
        if (API_BASE && API_TOKEN) await postResultToApi(task.id || ('t'+idx), result).catch(e => log('post error', e && e.message));
      } finally {
        try { await context.close(); } catch (e) { log('context close error', e && e.message); }
      }
    })());

    await Promise.all(workers);
    log('All workers finished');
    await browser.close();
    log('Browser closed');
    process.exit(0);

  } catch (e) {
    log('Main fatal error', e && e.message ? e.message : e);
    try { await browser.close(); } catch(_) {}
    process.exit(1);
  }
})();
