(() => {
  if (window.parent === window) return;

  const root = document.documentElement;
  const narrow = window.matchMedia('(max-width: 820px)').matches;
  const RETRY_MS = 250;
  const MAX_ATTEMPTS = 24;
  let ready = false;
  let attempts = 0;
  let retryTimer = null;

  function cssLength(value, fallback = '0px') {
    const text = String(value || '').trim();
    return /^-?\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%)$/.test(text) ? text : fallback;
  }

  function clearRetry() {
    if (retryTimer) window.clearTimeout(retryTimer);
    retryTimer = null;
  }

  function requestProperties() {
    if (window.parent === window || ready) return;
    attempts += 1;
    root.dataset.haShellRequested = 'true';
    root.dataset.haShellAttempts = String(attempts);
    window.parent.postMessage(
      {
        type: 'home-assistant/subscribe-properties',
        handleSafeArea: true,
        kioskMode: narrow,
      },
      '*',
    );

    clearRetry();
    if (!ready && attempts < MAX_ATTEMPTS) {
      retryTimer = window.setTimeout(requestProperties, RETRY_MS);
    } else if (!ready) {
      root.dataset.haShellTimedOut = 'true';
    }
  }

  function applyProperties(data) {
    if (!data || data.type !== 'home-assistant/properties') return;
    const insets = data.safeAreaInsets || {};
    root.style.setProperty('--ha-safe-top', cssLength(insets.top));
    root.style.setProperty('--ha-safe-right', cssLength(insets.right));
    root.style.setProperty('--ha-safe-bottom', cssLength(insets.bottom));
    root.style.setProperty('--ha-safe-left', cssLength(insets.left));
    root.dataset.haShellReady = 'true';
    root.dataset.haShellTimedOut = 'false';
    root.dataset.haNarrow = data.narrow ? 'true' : 'false';
    root.dataset.haPanelHost = String(data.host || 'home-assistant-app-panel');
    ready = true;
    clearRetry();
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    applyProperties(event.data);
  });

  // Home Assistant's native app panel supports this subscription protocol.
  // Retry briefly because the iframe can execute before the panel's message
  // listener/ref has fully settled during mobile navigation.
  requestProperties();

  window.addEventListener('pageshow', () => {
    if (!ready) requestProperties();
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !ready) requestProperties();
  });

  window.addEventListener('resize', () => {
    if (!ready) requestProperties();
  });

  window.addEventListener('pagehide', () => {
    clearRetry();
    window.parent.postMessage(
      {type: 'home-assistant/unsubscribe-properties'},
      '*',
    );
  }, {once: true});
})();
