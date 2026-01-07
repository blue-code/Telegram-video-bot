// PWA Install Prompt Handler
let deferredPrompt;
let installPromptShown = false;

// Check if already installed
function isInstalled() {
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.navigator.standalone === true;
}

// Check if install prompt was dismissed
function wasPromptDismissed() {
  const dismissed = localStorage.getItem('pwa-install-dismissed');
  if (!dismissed) return false;

  const dismissedDate = new Date(dismissed);
  const now = new Date();
  const daysSince = (now - dismissedDate) / (1000 * 60 * 60 * 24);

  // Show again after 7 days
  return daysSince < 7;
}

// Create install banner
function createInstallBanner() {
  if (document.getElementById('pwa-install-banner')) return;

  const banner = document.createElement('div');
  banner.id = 'pwa-install-banner';
  banner.innerHTML = `
    <style>
      #pwa-install-banner {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 16px;
        max-width: 90%;
        animation: slideUp 0.3s ease-out;
      }

      @keyframes slideUp {
        from {
          transform: translateX(-50%) translateY(100px);
          opacity: 0;
        }
        to {
          transform: translateX(-50%) translateY(0);
          opacity: 1;
        }
      }

      #pwa-install-banner .icon {
        font-size: 32px;
        flex-shrink: 0;
      }

      #pwa-install-banner .content {
        flex: 1;
      }

      #pwa-install-banner .title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 4px;
      }

      #pwa-install-banner .subtitle {
        font-size: 13px;
        opacity: 0.9;
      }

      #pwa-install-banner .actions {
        display: flex;
        gap: 8px;
      }

      #pwa-install-banner button {
        padding: 8px 16px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        white-space: nowrap;
      }

      #pwa-install-banner .install-btn {
        background: white;
        color: #667eea;
      }

      #pwa-install-banner .install-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
      }

      #pwa-install-banner .close-btn {
        background: rgba(255, 255, 255, 0.2);
        color: white;
      }

      #pwa-install-banner .close-btn:hover {
        background: rgba(255, 255, 255, 0.3);
      }

      @media (max-width: 768px) {
        #pwa-install-banner {
          bottom: 10px;
          left: 10px;
          right: 10px;
          transform: none;
          flex-direction: column;
          text-align: center;
          padding: 20px;
        }

        #pwa-install-banner .actions {
          width: 100%;
          flex-direction: column;
        }

        #pwa-install-banner button {
          width: 100%;
        }
      }
    </style>
    <div class="icon">📱</div>
    <div class="content">
      <div class="title">앱으로 설치하기</div>
      <div class="subtitle">홈 화면에 추가하여 빠르게 접근하세요</div>
    </div>
    <div class="actions">
      <button class="install-btn" onclick="installPWA()">설치</button>
      <button class="close-btn" onclick="dismissInstallPrompt()">나중에</button>
    </div>
  `;

  document.body.appendChild(banner);
  installPromptShown = true;
}

// Install PWA
window.installPWA = async function() {
  if (!deferredPrompt) {
    console.log('[PWA] No install prompt available');
    return;
  }

  // Show install prompt
  deferredPrompt.prompt();

  // Wait for user response
  const { outcome } = await deferredPrompt.userChoice;
  console.log(`[PWA] User response: ${outcome}`);

  if (outcome === 'accepted') {
    console.log('[PWA] Install accepted');
    // Track installation
    if (typeof gtag !== 'undefined') {
      gtag('event', 'pwa_install', {
        event_category: 'engagement',
        event_label: 'accepted'
      });
    }
  }

  // Clear deferred prompt
  deferredPrompt = null;

  // Remove banner
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.remove();
  }
};

// Dismiss install prompt
window.dismissInstallPrompt = function() {
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.remove();
  }

  // Remember dismissal
  localStorage.setItem('pwa-install-dismissed', new Date().toISOString());

  // Track dismissal
  if (typeof gtag !== 'undefined') {
    gtag('event', 'pwa_install_dismissed', {
      event_category: 'engagement'
    });
  }
};

// Listen for beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
  console.log('[PWA] beforeinstallprompt fired');

  // Prevent default browser install prompt
  e.preventDefault();

  // Store event for later use
  deferredPrompt = e;

  // Show custom install banner if conditions are met
  if (!isInstalled() && !wasPromptDismissed() && !installPromptShown) {
    // Wait 3 seconds before showing banner
    setTimeout(() => {
      createInstallBanner();
    }, 3000);
  }
});

// Listen for app installed event
window.addEventListener('appinstalled', () => {
  console.log('[PWA] App installed successfully');

  // Clear deferred prompt
  deferredPrompt = null;

  // Remove banner if still visible
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.remove();
  }

  // Track installation
  if (typeof gtag !== 'undefined') {
    gtag('event', 'pwa_installed', {
      event_category: 'engagement'
    });
  }

  // Show success message
  console.log('[PWA] Thank you for installing TVB!');
});

// Check if running as installed PWA
if (isInstalled()) {
  console.log('[PWA] Running as installed app');
  document.body.classList.add('pwa-installed');
}

// iOS Install Instructions
function showIOSInstallInstructions() {
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isInStandaloneMode = ('standalone' in window.navigator) && (window.navigator.standalone);

  if (isIOS && !isInStandaloneMode && !wasPromptDismissed()) {
    const banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.innerHTML = `
      <style>
        #pwa-install-banner {
          position: fixed;
          bottom: 20px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 16px 24px;
          border-radius: 16px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
          z-index: 9999;
          max-width: 90%;
          animation: slideUp 0.3s ease-out;
        }

        @keyframes slideUp {
          from {
            transform: translateX(-50%) translateY(100px);
            opacity: 0;
          }
          to {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
          }
        }

        #pwa-install-banner .content {
          margin-bottom: 12px;
        }

        #pwa-install-banner .title {
          font-weight: 600;
          font-size: 16px;
          margin-bottom: 8px;
        }

        #pwa-install-banner .steps {
          font-size: 13px;
          line-height: 1.6;
          opacity: 0.9;
        }

        #pwa-install-banner button {
          width: 100%;
          padding: 10px;
          border: none;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.2);
          color: white;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
        }
      </style>
      <div class="content">
        <div class="title">📱 홈 화면에 추가하기</div>
        <div class="steps">
          1. 공유 버튼(<span style="font-size: 18px;">⎙</span>)을 탭하세요<br>
          2. "홈 화면에 추가"를 선택하세요<br>
          3. "추가"를 탭하세요
        </div>
      </div>
      <button onclick="dismissInstallPrompt()">확인</button>
    `;

    document.body.appendChild(banner);

    // Auto-dismiss after 10 seconds
    setTimeout(() => {
      if (document.getElementById('pwa-install-banner')) {
        dismissInstallPrompt();
      }
    }, 10000);
  }
}

// Show iOS instructions after 3 seconds
setTimeout(showIOSInstallInstructions, 3000);
