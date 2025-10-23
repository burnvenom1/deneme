// playwright-multi-context.js
// Node 18+/20+
// Install: npm i --no-audit --no-fund playwright-core
// Usage in GH Action: env provided by workflow. Locally: CONTEXTS=3 TOR_BASE_PORT=9050 node playwright-multi-context.js

const { chromium, request: playwrightRequest } = require('playwright-core');
const { randomUUID } = require('crypto');

const CONTEXTS = process.env.CONTEXTS ? Math.max(1, parseInt(process.env.CONTEXTS, 10)) : 3;
const PROXY_LIST = process.env.PROXY_LIST ? process.env.PROXY_LIST.split(',').map(s => s.trim()).filter(Boolean) : null;
const TOR_BASE_PORT = process.env.TOR_BASE_PORT ? parseInt(process.env.TOR_BASE_PORT, 10) : 9050;
const CHROME_PATH = process.env.CHROME_PATH || '/usr/bin/chromium-browser';
const HEADLESS = (typeof process.env.HEADLESS === 'undefined') ? true : (String(process.env.HEADLESS).toLowerCase() !== 'false');
const API_BASE = process.env.API_BASE_URL || null;
const API_TOKEN = process.env.API_TOKEN || null;

const sleep = ms => new Promise(r => setTimeout(r, ms));
function getBackoff(attempt, base = 500, max = 15000) {
  const cap = Math.min(max, base * Math.pow(2, attempt));
  return Math.floor(Math.random() * cap);
}
async function retry(fn, attempts = 4) {
  for (let i = 0; i < attempts; i++) {
    try { return await fn(); }
    catch (err) {
      const wait = getBackoff(i);
      console.log(`Retry ${i+1}/${attempts} after error: ${err && err.message ? err.message : err}. waiting ${wait}ms`);
      await sleep(wait);
    }
  }
  throw new Error('Max retries reached');
}

/** ---------- Spoofing script builders (string returns) ---------- **/
function getWebGLSpoofScript(sessionSeed) {
  const gpuPairs = [
    { vendor: 'Intel Inc.', renderers: ['Intel Iris Xe Graphics','Intel UHD Graphics 770','Intel Iris Plus Graphics 655']},
    { vendor: 'NVIDIA Corporation', renderers: ['NVIDIA GeForce RTX 4050/PCIe/SSE2','NVIDIA GeForce RTX 4090/PCIe/SSE2','NVIDIA GeForce RTX 4080/PCIe/SSE2','NVIDIA GeForce RTX 4070 Ti/PCIe/SSE2']},
    { vendor: 'AMD', renderers: ['AMD Radeon RX 7900 XT','AMD Radeon RX 6800 XT','AMD Radeon RX Vega 11']},
    { vendor: 'Google Inc.', renderers: ['ANGLE (Google Inc., Vulkan 1.3, Vulkan)']}
  ];
  return `
    (() => {
      const gpuPairs = ${JSON.stringify(gpuPairs)};
      function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; } return Math.abs(h); }
      const baseHash = hashStr('${sessionSeed}');
      const vendorIndex = baseHash % gpuPairs.length;
      const vendor = gpuPairs[vendorIndex].vendor;
      const renderers = gpuPairs[vendorIndex].renderers;
      const renderer = renderers[(baseHash >> 3) % renderers.length];
      const getParam = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return vendor;
        if (param === 37446) return renderer;
        return getParam.call(this, param);
      };
    })();
  `;
}

function getCanvasSpoofScript(sessionSeed) {
  return `
    (() => {
      const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
      const domain = location.hostname;
      const sessionSeed = '${sessionSeed}';
      function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; } return h; }
      const baseHash = hashStr(domain + sessionSeed);
      const r = Math.abs((baseHash >> 16) & 255);
      const g = Math.abs((baseHash >> 8) & 255);
      const b = Math.abs(baseHash & 255);
      HTMLCanvasElement.prototype.toDataURL = function(type) {
        const canvas = document.createElement('canvas');
        canvas.width = this.width || 300;
        canvas.height = this.height || 150;
        const ctx = canvas.getContext('2d');
        try { ctx.drawImage(this, 0, 0); } catch(e) {}
        ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ', 0.03)';
        ctx.fillRect(0, 0, 1, 1);
        return originalToDataURL.call(canvas, type);
      };
    })();
  `;
}

function getAudioContextSpoofScript(sessionSeed) {
  return `
    (() => {
      const domain = location.hostname;
      const sessionSeed = '${sessionSeed}';
      function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; } return Math.abs(h); }
      const baseHash = hashStr(domain + sessionSeed);
      function noise(i) { return ((baseHash >> (i % 24)) & 15) * 1e-5; }
      const originalGetChannelData = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = function() {
        const data = originalGetChannelData.apply(this, arguments);
        for (let i = 0; i < data.length; i += 100) { data[i] = data[i] + noise(i); }
        return data;
      };
      const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
      AudioContext.prototype.createAnalyser = function() {
        const analyser = originalCreateAnalyser.apply(this, arguments);
        const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
        analyser.getFloatFrequencyData = function(array) {
          originalGetFloatFrequencyData.call(this, array);
          for (let i = 0; i < array.length; i++) { array[i] = array[i] + noise(i); }
        };
        const originalGetByteFrequencyData = analyser.getByteFrequencyData;
        analyser.getByteFrequencyData = function(array) {
          originalGetByteFrequencyData.call(this, array);
          for (let i = 0; i < array.length; i++) { array[i] = array[i] + noise(i); }
        };
        return analyser;
      };
      const originalOscillatorStart = OscillatorNode.prototype.start;
      OscillatorNode.prototype.start = function() {
        try { const originalFrequency = this.frequency.value; this.frequency.value = originalFrequency + noise(0) * 1e5; } catch (e) {}
        originalOscillatorStart.apply(this, arguments);
      };
    })();
  `;
}

function getHardwareInfoSpoofScript(sessionSeed) {
  const platforms = ['Win32','Linux x86_64','MacIntel','Win64','Linux aarch64'];
  const concurrencies = [2,4,8];
  const memories = [4,8,16];
  return `
    (() => {
      const platforms = ${JSON.stringify(platforms)};
      const concurrencies = ${JSON.stringify(concurrencies)};
      const memories = ${JSON.stringify(memories)};
      const domain = location.hostname;
      function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; } return Math.abs(h); }
      const baseHashDomain = hashStr(domain + '${sessionSeed}');
      const baseHashSession = hashStr('${sessionSeed}');
      Object.defineProperty(navigator, 'platform', { get: () => platforms[baseHashDomain % platforms.length], configurable: true });
      Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => concurrencies[baseHashDomain % concurrencies.length], configurable: true });
      Object.defineProperty(navigator, 'deviceMemory', { get: () => memories[baseHashSession % memories.length], configurable: true });
      Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }), configurable: true });
    })();
  `;
}

function getWebdriverSpoofScript() {
  return `
    (() => {
      try {
        if (Navigator.prototype && Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver')) {
          Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false, configurable: true });
        } else {
          Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true });
        }
      } catch(e) {}
    })();
  `;
}

function getPluginAndPermissionsSpoofScript() {
  return `
    (() => {
      try {
        const fakePlugins = [
          { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'PDF Görüntüleyici', version: '1.0.0' },
          { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', version: '' },
          { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', version: '' }
        ];
        fakePlugins.__proto__ = PluginArray.prototype;
        fakePlugins.item = function(i){ return this[i] || null; };
        fakePlugins.namedItem = function(n){ return this.find(p=>p.name===n)||null; };
        fakePlugins.refresh = function(){};
        Object.defineProperty(navigator, 'plugins', { get: () => fakePlugins, configurable: true });
        Object.defineProperty(navigator, 'permissions', { get: () => ({ query: () => Promise.resolve({ state: 'granted', onchange: null }), __proto__: Permissions.prototype }), configurable: true });
        const fakeMimeTypes = [{ type: 'application/pdf', suffixes: 'pdf', description: '', enabledPlugin: fakePlugins[0] }];
        fakeMimeTypes.__proto__ = MimeTypeArray.prototype;
        fakeMimeTypes.item = function(i){ return this[i] || null; };
        fakeMimeTypes.namedItem = function(n){ return this.find(m=>m.type===n)||null; };
        Object.defineProperty(navigator, 'mimeTypes', { get: () => fakeMimeTypes, configurable: true });
      } catch(e){}
    })();
  `;
}

/** ---------- helper: prepare proxy list ---------- **/
function buildProxyList() {
  if (PROXY_LIST && PROXY_LIST.length > 0) {
    return PROXY_LIST;
  }
  const arr = [];
  for (let i = 0; i < CONTEXTS; i++) {
    arr.push(`socks5://127.0.0.1:${TOR_BASE_PORT + i}`);
  }
  return arr;
}

/** ---------- optional API helpers (tasks/results) ---------- **/
async function fetchTasksFromApi() {
  if (!API_BASE || !API_TOKEN) return null;
  const req = await playwrightRequest.newContext({
    baseURL: API_BASE,
    extraHTTPHeaders: { 'Authorization': `Bearer ${API_TOKEN}`, 'Accept': 'application/json' },
    timeout: 30000
  });
  try {
    const res = await req.get('/tasks');
    if (!res.ok()) throw new Error(`API tasks fetch failed: ${res.status()}`);
    return await res.json();
  } finally {
    await req.dispose();
  }
}
async function postResultToApi(taskId, result) {
  if (!API_BASE || !API_TOKEN) return null;
  const req = await playwrightRequest.newContext({
    baseURL: API_BASE,
    extraHTTPHeaders: { 'Authorization': `Bearer ${API_TOKEN}`, 'Content-Type': 'application/json', 'Accept': 'application/json' },
    timeout: 30000
  });
  try {
    const res = await req.post(`/tasks/${taskId}/result`, { data: result });
    if (!res.ok()) throw new Error(`API post failed: ${res.status()}`);
    return await res.json();
  } finally {
    await req.dispose();
  }
}

/** ---------- main logic ---------- **/
(async () => {
  console.log('CONFIG:', { CONTEXTS, proxiesFromEnv: !!PROXY_LIST, TOR_BASE_PORT, CHROME_PATH, HEADLESS });

  const proxies = buildProxyList();
  console.log('Using proxies (first N):', proxies.slice(0, CONTEXTS));

  const browser = await chromium.launch({
    headless: HEADLESS,
    executablePath: CHROME_PATH,
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
    timeout: 30000
  });

  try {
    const tasks = await (API_BASE && API_TOKEN ? retry(fetchTasksFromApi, 3).catch(()=>null) : null);
    const workItems = Array.isArray(tasks) && tasks.length ? tasks : [
      { id: 'demo-1', url: 'https://giris.hepsiburada.com/?ReturnUrl=https%3A%2F%2Foauth.hepsiburada.com%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3DSPA%26redirect_uri%3Dhttps%253A%252F%252Fwww.hepsiburada.com%252Fuyelik%252Fcallback%26response_type%3Dcode%26scope%3Dopenid%2520profile%26state%3D7cb8bd4eeed54ce590c3ade08f4ae1ca%26code_challenge%3DyoQ0DpRXUGYGRQyvQL7U42EelI35-Od97R3LFWFkUUk%26code_challenge_method%3DS256%26response_mode%3Dquery%26ActivePage%3DSIGN_UP%26oidcReturnUrl%3Dhttps%253A%252F%252Fwww.hepsiburada.com%252F', fields: [], clicks: [], successSelector: null }
    ];

    const toProcess = workItems.slice(0, CONTEXTS);

    const workers = toProcess.map((task, idx) => (async () => {
      const proxy = proxies[idx] || null;
      const seed = randomUUID().slice(0,8) + '-' + idx;
      console.log(`Worker[${idx}] task:${task.id} proxy:${proxy} seed:${seed}`);

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

        if (Array.isArray(task.fields)) {
          for (const f of task.fields) {
            try {
              await page.waitForSelector(f.selector, { timeout: 4000 });
              await page.fill(f.selector, f.value);
            } catch (e) {
              console.log(`Worker[${idx}] field ${f.selector} not found: ${e.message}`);
            }
          }
        }

        if (Array.isArray(task.clicks)) {
          for (const sel of task.clicks) {
            try {
              await page.waitForSelector(sel, { timeout: 4000 });
              await Promise.all([ page.click(sel), page.waitForTimeout(400) ]);
            } catch (e) {
              console.log(`Worker[${idx}] click ${sel} failed: ${e.message}`);
            }
          }
        }

        let successText = null;
        if (task.successSelector) {
          try {
            await page.waitForSelector(task.successSelector, { timeout: 8000 });
            successText = await page.$eval(task.successSelector, el => el.textContent.trim());
          } catch (e) {
            console.log(`Worker[${idx}] successSelector not found`);
          }
        }

        const fname = `screenshot-${task.id || 't'+idx}-${Date.now()}.png`;
        await page.screenshot({ path: fname }).catch(()=>{});
        console.log(`Worker[${idx}] screenshot saved: ${fname}`);

        const result = { status: successText ? 'ok' : 'maybe', successText, screenshot: fname, timestamp: new Date().toISOString() };
        if (API_BASE && API_TOKEN) {
          await retry(() => postResultToApi(task.id || ('t'+idx), result), 3).catch(e => console.log('post result failed', e.message));
        } else {
          console.log('Result (no API):', result);
        }

      } catch (err) {
        console.error(`Worker[${idx}] fatal:`, err && err.message ? err.message : err);
        const result = { status: 'error', error: err && err.message ? err.message : String(err), timestamp: new Date().toISOString() };
        if (API_BASE && API_TOKEN) await postResultToApi(task.id || ('t'+idx), result).catch(()=>{});
      } finally {
        try { await context.close(); } catch(_) {}
      }
    })());

    await Promise.all(workers);

    console.log('All workers finished.');
    await browser.close();
  } catch (e) {
    console.error('Main fatal error:', e && e.message ? e.message : e);
    try { await browser.close(); } catch(_) {}
    process.exit(1);
  }
})();
