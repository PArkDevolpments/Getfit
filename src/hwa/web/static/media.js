(() => {
  for (const host of document.querySelectorAll('[data-local-demo]')) {
    const path = host.dataset.localDemo;
    if (!path) continue;
    const media = document.createElement('img');
    media.src = path;
    media.alt = 'Exercise technique demonstration';
    media.loading = 'lazy';
    media.addEventListener('error', () => {
      host.replaceChildren();
      const note = document.createElement('p');
      note.textContent = 'Technique media is unavailable. The exercise is still usable.';
      host.append(note);
    });
    host.replaceChildren(media);
  }
})();
