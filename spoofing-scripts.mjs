// spoofing-scripts.mjs
// Exports: getWebGLSpoofScript, getCanvasSpoofScript, getAudioContextSpoofScript,
// getHardwareInfoSpoofScript, getWebdriverSpoofScript, getPluginAndPermissionsSpoofScript

export function getWebGLSpoofScript(sessionSeed) {
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

export function getCanvasSpoofScript(sessionSeed) {
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

export function getAudioContextSpoofScript(sessionSeed) {
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

export function getHardwareInfoSpoofScript(sessionSeed) {
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

export function getWebdriverSpoofScript() {
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

export function getPluginAndPermissionsSpoofScript() {
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
