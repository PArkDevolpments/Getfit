(() => {
  const root = document.documentElement;
  let rafId = 0;

  function numberFromCss(name) {
    const value = Number.parseFloat(getComputedStyle(root).getPropertyValue(name));
    return Number.isFinite(value) ? value : 0;
  }

  function classify(width, height) {
    if (width > 820) return 'wide';
    if (height <= 720) return 'compact';
    if (height <= 860) return 'standard';
    return 'tall';
  }

  function measure() {
    rafId = 0;
    const viewport = window.visualViewport;
    const width = Math.round(viewport?.width || window.innerWidth);
    const height = Math.round(viewport?.height || window.innerHeight);
    const safeTop = numberFromCss('--ha-safe-top');
    const safeBottom = numberFromCss('--ha-safe-bottom');
    const mobile = width <= 820;
    const nav = mobile ? document.querySelector('.primary-nav') : null;
    const navHeight = nav ? Math.round(nav.getBoundingClientRect().height) : 0;
    const usableHeight = Math.max(0, height - safeTop - safeBottom - navHeight);
    const band = classify(width, height);

    root.style.setProperty('--getfit-viewport-w', `${width}px`);
    root.style.setProperty('--getfit-viewport-h', `${height}px`);
    root.style.setProperty('--getfit-nav-h', `${navHeight}px`);
    root.style.setProperty('--getfit-usable-h', `${usableHeight}px`);
    root.dataset.viewportBand = band;
    root.dataset.viewportWidth = String(width);
    root.dataset.viewportHeight = String(height);
    root.dataset.viewportReady = 'true';

    window.dispatchEvent(new CustomEvent('getfit:viewport', {
      detail: {width, height, navHeight, usableHeight, band},
    }));
  }

  function schedule() {
    if (rafId) window.cancelAnimationFrame(rafId);
    rafId = window.requestAnimationFrame(measure);
  }

  schedule();
  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  window.addEventListener('pageshow', schedule);
  window.addEventListener('getfit:host-properties', schedule);

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', schedule);
    window.visualViewport.addEventListener('scroll', schedule);
  }

  if ('ResizeObserver' in window) {
    const nav = document.querySelector('.primary-nav');
    if (nav) new ResizeObserver(schedule).observe(nav);
  }
})();
