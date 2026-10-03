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
      if (panel.dataset.mediaPanel === 'video' && key === 'video') {
        for (const source of panel.querySelectorAll('video source[data-video-src]')) {
          if (!source.getAttribute('src')) {
            source.setAttribute('src', source.dataset.videoSrc || '');
            source.closest('video')?.load();
          }
        }
        for (const videoFrame of panel.querySelectorAll('iframe[data-video-src]')) {
          if (!videoFrame.getAttribute('src')) {
            videoFrame.setAttribute('src', videoFrame.dataset.videoSrc || '');
          }
        }
      }
    }
  };

  for (const tab of tabs) {
    tab.addEventListener('click', () => activate(tab.dataset.mediaTab || 'images'));
  }

  activate('images');
})();
