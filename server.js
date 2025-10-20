const express = require('express');
const puppeteer = require('puppeteer');
const { TorController } = require('tor-ip-changer');
const { randomUUID } = require('crypto');
const app = express();
app.use(express.json());

let torController = null;
let browser = null;

// 1. ADIM: Fingerprint seed oluştur
function generateFingerprintSeed() {
  return randomUUID().slice(0, 8);
}

// 2. ADIM: Gerçekçi User-Agent
const userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// 3. ADIM: WebGL Spoofing
function getWebGLSpoofScript(sessionSeed) {
  const gpuPairs = [
    { vendor: 'Intel Inc.', renderers: [
        'Intel Iris Xe Graphics',
        'Intel UHD Graphics 770', 
        'Intel Iris Plus Graphics 655'
      ]},
    { vendor: 'NVIDIA Corporation', renderers: [
        'NVIDIA GeForce RTX 4050/PCIe/SSE2',
        'NVIDIA GeForce RTX 4090/PCIe/SSE2',
        'NVIDIA GeForce RTX 4080/PCIe/SSE2'
      ]},
    { vendor: 'AMD', renderers: [
        'AMD Radeon RX 7900 XT',
        'AMD Radeon RX 6800 XT',
        'AMD Radeon RX Vega 11'
      ]}
  ];

  return `
    (() => {
      const gpuPairs = ${JSON.stringify(gpuPairs)};
      function hashStr(s) {
        let h = 0;
        for (let i = 0; i < s.length; i++) {
          h = ((h << 5) - h) + s.charCodeAt(i);
          h |= 0;
        }
        return Math.abs(h);
      }
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

// 4. ADIM: Canvas Spoofing
function getCanvasSpoofScript(sessionSeed) {
  return `
    (() => {
      const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
      const domain = location.hostname;
      const sessionSeed = '${sessionSeed}';

      function hashStr(s) {
        let h = 0;
        for (let i = 0; i < s.length; i++) {
          h = ((h << 5) - h) + s.charCodeAt(i);
          h |= 0;
        }
        return h;
      }

      const baseHash = hashStr(domain + sessionSeed);
      const r = Math.abs((baseHash >> 16) & 255);
      const g = Math.abs((baseHash >> 8) & 255);
      const b = Math.abs(baseHash & 255);

      HTMLCanvasElement.prototype.toDataURL = function(type) {
        const canvas = document.createElement('canvas');
        canvas.width = this.width;
        canvas.height = this.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(this, 0, 0);
        ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ', 0.03)';
        ctx.fillRect(0, 0, 1, 1);
        return originalToDataURL.call(canvas, type);
      };
    })();
  `;
}

// 5. ADIM: AudioContext Spoofing
function getAudioContextSpoofScript(sessionSeed) {
  return `
    (() => {
      const domain = location.hostname;
      const sessionSeed = '${sessionSeed}';

      function hashStr(s) {
        let h = 0;
        for (let i = 0; i < s.length; i++) {
          h = ((h << 5) - h) + s.charCodeAt(i);
          h |= 0;
        }
        return Math.abs(h);
      }

      const baseHash = hashStr(domain + sessionSeed);
      function noise(i) {
        return ((baseHash >> (i % 24)) & 15) * 1e-5;
      }

      const originalGetChannelData = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = function() {
        const data = originalGetChannelData.apply(this, arguments);
        for (let i = 0; i < data.length; i += 100) {
          data[i] = data[i] + noise(i);
        }
        return data;
      };
    })();
  `;
}

// 6. ADIM: Hardware Spoofing
function getHardwareInfoSpoofScript(sessionSeed) {
  const platforms = ['Win32', 'Linux x86_64', 'MacIntel', 'Win64'];
  const concurrencies = [4, 8, 16];
  const memories = [8, 16, 32];

  return `
    (() => {
      const platforms = ${JSON.stringify(platforms)};
      const concurrencies = ${JSON.stringify(concurrencies)};
      const memories = ${JSON.stringify(memories)};

      function hashStr(s) {
        let h = 0;
        for (let i = 0; i < s.length; i++) {
          h = ((h << 5) - h) + s.charCodeAt(i);
          h |= 0;
        }
        return Math.abs(h);
      }

      const baseHash = hashStr('${sessionSeed}');

      Object.defineProperty(navigator, 'platform', {
        get: () => platforms[baseHash % platforms.length],
        configurable: true
      });

      Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => concurrencies[baseHash % concurrencies.length],
        configurable: true
      });

      Object.defineProperty(navigator, 'deviceMemory', {
        get: () => memories[baseHash % memories.length],
        configurable: true
      });
    })();
  `;
}

// 7. ADIM: Webdriver Spoofing
function getWebdriverSpoofScript() {
  return `
    (() => {
      delete Object.getPrototypeOf(navigator).webdriver;
    })();
  `;
}

// 8. ADIM: Plugin Spoofing
function getPluginSpoofScript() {
  return `
    (() => {
      const fakePlugins = [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' }
      ];
      
      Object.defineProperty(navigator, 'plugins', {
        get: () => fakePlugins,
        configurable: true
      });
    })();
  `;
}

// 9. ADIM: Tüm spoofing scriptlerini sayfaya ekle
async function applyFingerprintSpoofing(page, sessionSeed) {
  await page.evaluateOnNewDocument(getWebGLSpoofScript(sessionSeed));
  await page.evaluateOnNewDocument(getHardwareInfoSpoofScript(sessionSeed));
  await page.evaluateOnNewDocument(getWebdriverSpoofScript());
  await page.evaluateOnNewDocument(getCanvasSpoofScript(sessionSeed));
  await page.evaluateOnNewDocument(getAudioContextSpoofScript(sessionSeed));
  await page.evaluateOnNewDocument(getPluginSpoofScript());
  
  // User-Agent ayarla
  await page.setUserAgent(userAgent);
  
  // Diğer header'lar
  await page.setExtraHTTPHeaders({
    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
  });
}

// Sistem başlatma
async function initSystem() {
  try {
    console.log('🚀 Sistem başlatılıyor...');
    
    // Tor IP Changer
    torController = new TorController({
      torHost: '127.0.0.1',
      torPort: 9050,
      controlPort: 9051,
      password: 'hepsiburada123'
    });

    await torController.startTor();
    console.log('✅ Tor IP Changer hazır!');

    // Browser'ı başlat
    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-web-security',
        '--proxy-server=socks5://127.0.0.1:9050'
      ]
    });
    
    console.log('✅ Browser başlatıldı');
    console.log('🎉 SİSTEM HAZIR! Fingerprint spoofing aktif');

  } catch (error) {
    console.error('❌ Sistem hatası:', error);
  }
}

// Ana API
app.post('/api/hepsiburada', async (req, res) => {
  const { email } = req.body;
  
  if (!email) {
    return res.status(400).json({ error: 'Email gerekli' });
  }

  let page = null;
  try {
    console.log(`📨 İstek alındı: ${email}`);
    
    // 🔁 YENİ TOR IP
    await torController.renewTorSession();
    const newIp = await torController.getCurrentIp();
    console.log(`🆕 Yeni Tor IP: ${newIp}`);

    // 🎭 YENİ FINGERPRINT SEED
    const fingerprintSeed = generateFingerprintSeed();
    console.log(`🎭 Yeni Fingerprint: ${fingerprintSeed}`);

    // Yeni sekme aç
    page = await browser.newPage();
    
    // ✅ TÜM SPOOFING SCRIPTLERİNİ EKLE (HER SEKMEDE!)
    await applyFingerprintSpoofing(page, fingerprintSeed);

    // Hepsiburada işlemleri
    await page.goto('https://giris.hepsiburada.com/', { 
      waitUntil: 'networkidle2',
      timeout: 30000 
    });

    await page.type('input[type="email"]', email);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(5000);
    
    await page.close();
    
    res.json({
      success: true,
      message: `${email} - İşlem tamam!`,
      tor_ip: newIp,
      fingerprint: fingerprintSeed,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('❌ Hata:', error);
    if (page) await page.close();
    res.status(500).json({ error: error.message });
  }
});

// Sistem durumu
app.get('/api/status', async (req, res) => {
  try {
    const currentIp = torController ? await torController.getCurrentIp() : 'N/A';
    res.json({
      status: '🟢 Çalışıyor',
      tor_ip: currentIp,
      browser_ready: !!browser,
      fingerprint_spoofing: true,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.json({ status: '🔴 Hata', error: error.message });
  }
});

// Ana sayfa
app.get('/', (req, res) => {
  res.json({
    message: '🚀 Hepsiburada Auto System - Advanced Fingerprint Spoofing',
    version: '3.0.0',
    features: [
      'Tor IP Rotation',
      'WebGL Spoofing', 
      'Canvas Fingerprint Spoofing',
      'AudioContext Spoofing',
      'Hardware Info Spoofing',
      'Webdriver Removal',
      'Plugin Spoofing'
    ]
  });
});

// Sunucuyu başlat
const PORT = process.env.PORT || 3000;
app.listen(PORT, async () => {
  console.log(`🚀 Server http://localhost:${PORT} portunda çalışıyor`);
  await initSystem();
});
