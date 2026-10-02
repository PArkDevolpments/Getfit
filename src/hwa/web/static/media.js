(() => {
  for (const image of document.querySelectorAll('.exercise-card__media img, .exercise-phase img, .exercise-single-demo img')) {
    image.addEventListener('error', () => {
      const host = image.closest('.exercise-card__media, .exercise-phase, .exercise-single-demo');
      if (!host) return;
      const fallback = document.createElement('div');
      fallback.className = 'exercise-media-fallback';
      fallback.innerHTML = '<strong>Visual unavailable</strong><p>The approved technique cues remain available.</p>';
      image.replaceWith(fallback);
    });
  }

  const tabs = [...document.querySelectorAll('[data-media-tab]')];
  const panels = [...document.querySelectorAll('[data-media-panel]')];
  if (!tabs.length || !panels.length) return;

  const activate = (key) => {
    for (const tab of tabs) {
      const active = tab.dataset.mediaTab === key;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    }
    for (const panel of panels) {
      panel.hidden = panel.dataset.mediaPanel !== key;
    }
  };

  for (const tab of tabs) {
    tab.addEventListener('click', () => activate(tab.dataset.mediaTab || 'images'));
  }

  activate('images');
})();
