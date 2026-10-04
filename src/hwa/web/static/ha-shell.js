(() => {
  if (window.parent === window) return;

  const root = document.documentElement;
  const narrow = window.matchMedia('(max-width: 820px)').matches;

  function cssLength(value, fallback = '0px') {
    const text = String(value || '').trim();
    return /^-?\d+(?:\.\d+)?(?:px|rem|em|vh|vw|%)$/.test(text) ? text : fallback;
  }

  function applyProperties(data) {
    if (!data || data.type !== 'home-assistant/properties') return;
    const insets = data.safeAreaInsets || {};
    root.style.setProperty('--ha-safe-top', cssLength(insets.top));
    root.style.setProperty('--ha-safe-right', cssLength(insets.right));
    root.style.setProperty('--ha-safe-bottom', cssLength(insets.bottom));
    root.style.setProperty('--ha-safe-left', cssLength(insets.left));
    root.dataset.haShellReady = 'true';
    root.dataset.haNarrow = data.narrow ? 'true' : 'false';
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    applyProperties(event.data);
  });

  window.parent.postMessage(
    {
      type: 'home-assistant/subscribe-properties',
      handleSafeArea: true,
      kioskMode: narrow,
    },
    '*',
  );

  window.addEventListener('pagehide', () => {
    window.parent.postMessage(
      {type: 'home-assistant/unsubscribe-properties'},
      '*',
    );
  }, {once: true});
})();
