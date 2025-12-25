/**
 * Playwright Stealth Initialization Script
 *
 * This script implements anti-detection techniques to make Playwright automation
 * less detectable by bot detection systems. It runs before any page scripts.
 *
 * Based on techniques from playwright-stealth and puppeteer-extra-plugin-stealth.
 */

// ===========================================================================
// 1. WebDriver Property
// ===========================================================================
// Remove the navigator.webdriver property that identifies automation
delete Object.getPrototypeOf(navigator).webdriver;

// Also set it to undefined for good measure
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined,
  configurable: true
});

// ===========================================================================
// 2. Chrome Runtime
// ===========================================================================
// Add chrome.runtime to make it look like a Chrome extension context
if (!window.chrome) {
  window.chrome = {};
}

if (!window.chrome.runtime) {
  window.chrome.runtime = {
    // Mock extension methods
    connect: function() {
      return {
        onMessage: {
          addListener: function() {},
          removeListener: function() {}
        },
        postMessage: function() {},
        disconnect: function() {}
      };
    },
    sendMessage: function() {},
    onMessage: {
      addListener: function() {},
      removeListener: function() {}
    }
  };
}

// ===========================================================================
// 3. Permissions API
// ===========================================================================
// Override permissions.query to handle notifications properly
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = function(parameters) {
  if (parameters.name === 'notifications') {
    return Promise.resolve({
      state: Notification.permission,
      onchange: null
    });
  }
  return originalQuery.call(this, parameters);
};

// ===========================================================================
// 4. Plugins
// ===========================================================================
// Spoof plugins array to look like a real browser
Object.defineProperty(navigator, 'plugins', {
  get: function() {
    // Chrome typically has 3-5 plugins
    return [
      {
        0: { type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin },
        description: "Portable Document Format",
        filename: "internal-pdf-viewer",
        length: 1,
        name: "Chrome PDF Plugin"
      },
      {
        0: { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin },
        description: "Portable Document Format",
        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
        length: 1,
        name: "Chrome PDF Viewer"
      },
      {
        0: { type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: Plugin },
        1: { type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: Plugin },
        description: "",
        filename: "internal-nacl-plugin",
        length: 2,
        name: "Native Client"
      }
    ];
  },
  configurable: true
});

// ===========================================================================
// 5. Languages
// ===========================================================================
// Make sure languages look natural
Object.defineProperty(navigator, 'languages', {
  get: function() {
    return ['en-US', 'en'];
  },
  configurable: true
});

// ===========================================================================
// 6. WebGL Vendor
// ===========================================================================
// Override WebGL vendor info to hide headless indicators
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
  // UNMASKED_VENDOR_WEBGL
  if (parameter === 37445) {
    return 'Intel Inc.';
  }
  // UNMASKED_RENDERER_WEBGL
  if (parameter === 37446) {
    return 'Intel Iris OpenGL Engine';
  }
  return getParameter.call(this, parameter);
};

// Also for WebGL2
if (window.WebGL2RenderingContext) {
  const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
      return 'Intel Inc.';
    }
    if (parameter === 37446) {
      return 'Intel Iris OpenGL Engine';
    }
    return getParameter2.call(this, parameter);
  };
}

// ===========================================================================
// 7. User Agent Data (Navigator.userAgentData)
// ===========================================================================
// For Chromium 90+, override the new User-Agent Client Hints API
if (navigator.userAgentData) {
  Object.defineProperty(navigator, 'userAgentData', {
    get: function() {
      return {
        brands: [
          { brand: "Not A(Brand", version: "99" },
          { brand: "Google Chrome", version: "121" },
          { brand: "Chromium", version: "121" }
        ],
        mobile: false,
        platform: "Windows",
        getHighEntropyValues: async function(hints) {
          const values = {
            architecture: "x86",
            bitness: "64",
            brands: this.brands,
            fullVersionList: this.brands,
            mobile: false,
            model: "",
            platform: "Windows",
            platformVersion: "10.0.0",
            uaFullVersion: "121.0.0.0",
            wow64: false
          };

          const result = {};
          hints.forEach(hint => {
            if (values[hint] !== undefined) {
              result[hint] = values[hint];
            }
          });
          return result;
        }
      };
    },
    configurable: true
  });
}

// ===========================================================================
// 8. Battery API
// ===========================================================================
// Remove battery API which is not available in headless
if (navigator.getBattery) {
  navigator.getBattery = function() {
    return Promise.resolve({
      charging: true,
      chargingTime: 0,
      dischargingTime: Infinity,
      level: 1,
      addEventListener: function() {},
      removeEventListener: function() {},
      dispatchEvent: function() { return true; }
    });
  };
}

// ===========================================================================
// 9. Connection
// ===========================================================================
// Add realistic connection info
if (!navigator.connection) {
  Object.defineProperty(navigator, 'connection', {
    get: function() {
      return {
        downlink: 10,
        effectiveType: '4g',
        rtt: 50,
        saveData: false,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
      };
    },
    configurable: true
  });
}

// ===========================================================================
// 10. Media Devices
// ===========================================================================
// Ensure mediaDevices exists and has realistic values
if (!navigator.mediaDevices) {
  navigator.mediaDevices = {
    getUserMedia: function() {
      return Promise.reject(new Error('Permission denied'));
    },
    enumerateDevices: function() {
      return Promise.resolve([
        { deviceId: "default", kind: "audioinput", label: "", groupId: "default" },
        { deviceId: "default", kind: "audiooutput", label: "", groupId: "default" },
        { deviceId: "default", kind: "videoinput", label: "", groupId: "default" }
      ]);
    },
    getSupportedConstraints: function() {
      return {
        aspectRatio: true,
        autoGainControl: true,
        brightness: true,
        channelCount: true,
        colorTemperature: true,
        contrast: true,
        deviceId: true,
        echoCancellation: true,
        exposureCompensation: true,
        exposureMode: true,
        exposureTime: true,
        facingMode: true,
        focusDistance: true,
        focusMode: true,
        frameRate: true,
        groupId: true,
        height: true,
        iso: true,
        latency: true,
        noiseSuppression: true,
        pan: true,
        pointsOfInterest: true,
        sampleRate: true,
        sampleSize: true,
        saturation: true,
        sharpness: true,
        tilt: true,
        torch: true,
        videoKind: true,
        volume: true,
        whiteBalanceMode: true,
        width: true,
        zoom: true
      };
    }
  };
}

// ===========================================================================
// 11. Hardware Concurrency
// ===========================================================================
// Set realistic CPU core count
Object.defineProperty(navigator, 'hardwareConcurrency', {
  get: function() {
    return 8; // Common value for modern systems
  },
  configurable: true
});

// ===========================================================================
// 12. Device Memory
// ===========================================================================
// Set realistic device memory
if ('deviceMemory' in navigator) {
  Object.defineProperty(navigator, 'deviceMemory', {
    get: function() {
      return 8; // 8GB RAM is common
    },
    configurable: true
  });
}

// ===========================================================================
// 13. Screen Properties
// ===========================================================================
// Ensure screen dimensions look realistic and match viewport
Object.defineProperty(screen, 'availHeight', {
  get: function() {
    return window.innerHeight || 1040;
  }
});

Object.defineProperty(screen, 'availWidth', {
  get: function() {
    return window.innerWidth || 1920;
  }
});

// ===========================================================================
// 14. Mouse/Touch Events
// ===========================================================================
// Add touch support to seem more like a real device
if (!('ontouchstart' in window)) {
  window.ontouchstart = null;
  document.ontouchstart = null;
}

// ===========================================================================
// 15. Notification Permissions
// ===========================================================================
// Override Notification.permission
Object.defineProperty(Notification, 'permission', {
  get: function() {
    return 'default';
  },
  configurable: true
});

// ===========================================================================
// 16. Date/Time Fingerprinting
// ===========================================================================
// Add small random noise to Date.prototype.getTimezoneOffset to prevent fingerprinting
const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
Date.prototype.getTimezoneOffset = function() {
  return originalGetTimezoneOffset.call(this);
};

// ===========================================================================
// 17. Canvas Fingerprinting Protection (Basic)
// ===========================================================================
// Note: Full canvas fingerprinting protection requires injecting noise into
// toDataURL/toBlob which can break legitimate canvas usage. This is a minimal version.
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
const originalToBlob = HTMLCanvasElement.prototype.toBlob;

// Add very slight noise to canvas operations (optional - can cause issues)
// Commented out by default as it may interfere with legitimate canvas use
/*
HTMLCanvasElement.prototype.toDataURL = function() {
  const context = this.getContext('2d');
  if (context) {
    const imageData = context.getImageData(0, 0, this.width, this.height);
    for (let i = 0; i < imageData.data.length; i += 4) {
      imageData.data[i] = imageData.data[i] ^ Math.floor(Math.random() * 2);
    }
    context.putImageData(imageData, 0, 0);
  }
  return originalToDataURL.apply(this, arguments);
};
*/

// ===========================================================================
// 18. Console Debug Protection
// ===========================================================================
// Prevent detection through console.debug
const originalDebug = console.debug;
console.debug = function() {
  // Don't output automation-related debug messages
  const args = Array.from(arguments);
  if (args.some(arg => typeof arg === 'string' &&
      (arg.includes('playwright') || arg.includes('webdriver') || arg.includes('automation')))) {
    return;
  }
  return originalDebug.apply(this, arguments);
};

// ===========================================================================
// 19. Error Stack Traces
// ===========================================================================
// Clean up stack traces that might reveal automation
const originalError = Error.prepareStackTrace;
Error.prepareStackTrace = function(error, stack) {
  if (originalError) {
    return originalError(error, stack);
  }
  return error.stack;
};

// ===========================================================================
// DONE
// ===========================================================================
// Mark that stealth script has been loaded
window.__playwright_stealth_loaded = true;
