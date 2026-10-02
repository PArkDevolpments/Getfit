(() => {
  const targetsNode = document.getElementById('review-targets');
  const frame = document.getElementById('review-frame');
  const frameShell = document.getElementById('frame-shell');
  const stageLabel = document.getElementById('stage-label');
  const captureAllButton = document.getElementById('capture-all');
  const responsiveButton = document.getElementById('capture-responsive');
  const cancelButton = document.getElementById('cancel-capture');
  const progressBar = document.getElementById('progress-bar');
  const progressMessage = document.getElementById('progress-message');

  if (!targetsNode || !frame || !frameShell) return;

  const targets = JSON.parse(targetsNode.textContent || '[]');
  const fullProfiles = [
    {key: 'phone', label: 'Phone', width: 390, height: 844},
    {key: 'tablet', label: 'Tablet', width: 820, height: 1180},
    {key: 'desktop', label: 'Desktop', width: 1440, height: 1000},
  ];

  let cancelled = false;

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  const nextFrame = () => new Promise((resolve) => window.requestAnimationFrame(resolve));

  function setMessage(message) {
    if (progressMessage) progressMessage.textContent = message;
  }

  function setProgress(current, total) {
    if (!progressBar) return;
    const percent = total ? Math.round((current / total) * 100) : 0;
    progressBar.style.width = `${percent}%`;
  }

  function setTargetState(targetKey, state, text) {
    const row = document.querySelector(`[data-target="${targetKey}"]`);
    if (!row) return;
    row.classList.toggle('is-active', state === 'active');
    row.classList.toggle('is-done', state === 'done');
    row.classList.toggle('is-error', state === 'error');
    const value = row.querySelector('.review-page-list__state');
    if (value) value.textContent = text;
  }

  function resetTargetStates() {
    for (const target of targets) setTargetState(target.key, 'waiting', 'Waiting');
  }

  function currentViewportProfile() {
    return {
      key: `current-${window.innerWidth}x${window.innerHeight}`,
      label: `Current ${window.innerWidth}×${window.innerHeight}`,
      width: Math.max(320, window.innerWidth),
      height: Math.max(568, window.innerHeight),
    };
  }

  function applyProfile(profile) {
    frameShell.style.width = `${profile.width}px`;
    frameShell.style.height = `${profile.height}px`;

    const toolbar = document.getElementById('review-toolbar');
    const toolbarWidth = toolbar && window.innerWidth > 700 ? toolbar.offsetWidth + 42 : 18;
    const availableWidth = Math.max(220, window.innerWidth - toolbarWidth);
    const availableHeight = Math.max(320, window.innerHeight - 28);
    const scale = Math.min(
      1,
      availableWidth / profile.width,
      availableHeight / profile.height,
    );
    frameShell.style.transform = `scale(${scale})`;
    if (stageLabel) stageLabel.textContent = profile.label;
  }

  async function loadTarget(target, profile) {
    applyProfile(profile);
    const wanted = new URL(target.url, window.location.href).href;

    await new Promise((resolve, reject) => {
      const timeout = window.setTimeout(
        () => reject(new Error(`Timed out loading ${target.label}`)),
        15000,
      );
      frame.onload = () => {
        window.clearTimeout(timeout);
        resolve();
      };

      if (frame.src === wanted) {
        try {
          frame.contentWindow?.location.reload();
        } catch (_) {
          frame.src = target.url;
        }
      } else {
        frame.src = target.url;
      }
    });

    await nextFrame();
    await sleep(500);
  }

  function collectCss(documentRef) {
    const chunks = [];
    for (const sheet of Array.from(documentRef.styleSheets)) {
      try {
        for (const rule of Array.from(sheet.cssRules || [])) {
          chunks.push(rule.cssText);
        }
      } catch (_) {
        // A cross-origin stylesheet is intentionally ignored. Getfit production
        // assets are same-origin; this prevents an optional external resource
        // from breaking the review pack.
      }
    }
    return chunks.join('\n');
  }

  function syncFormState(originalRoot, clonedRoot) {
    const originals = originalRoot.querySelectorAll('input, textarea, select, details');
    const clones = clonedRoot.querySelectorAll('input, textarea, select, details');

    originals.forEach((original, index) => {
      const clone = clones[index];
      if (!clone) return;

      const tag = original.tagName;
      if (tag === 'INPUT' && clone.tagName === 'INPUT') {
        clone.value = original.value;
        clone.setAttribute('value', original.value);
        if (original.checked) clone.setAttribute('checked', '');
        else clone.removeAttribute('checked');
      } else if (tag === 'TEXTAREA' && clone.tagName === 'TEXTAREA') {
        clone.value = original.value;
        clone.textContent = original.value;
      } else if (tag === 'SELECT' && clone.tagName === 'SELECT') {
        Array.from(clone.options).forEach((option, optionIndex) => {
          if (optionIndex === original.selectedIndex) option.setAttribute('selected', '');
          else option.removeAttribute('selected');
        });
      } else if (tag === 'DETAILS' && clone.tagName === 'DETAILS') {
        if (original.open) clone.setAttribute('open', '');
        else clone.removeAttribute('open');
      }
    });
  }

  function syncCanvasState(originalRoot, clonedRoot) {
    const originals = Array.from(originalRoot.querySelectorAll('canvas'));
    const clones = Array.from(clonedRoot.querySelectorAll('canvas'));

    originals.forEach((original, index) => {
      const clone = clones[index];
      if (!clone || clone.tagName !== 'CANVAS') return;
      try {
        const image = original.ownerDocument.createElement('img');
        image.src = original.toDataURL('image/png');
        image.width = original.width;
        image.height = original.height;
        image.setAttribute('style', original.getAttribute('style') || '');
        clone.replaceWith(image);
      } catch (_) {
        // A tainted optional canvas remains blank rather than failing the pack.
      }
    });
  }

  async function blobToDataUrl(blob) {
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(reader.error || new Error('Unable to read image asset.'));
      reader.readAsDataURL(blob);
    });
  }

  async function inlineImages(originalRoot, clonedRoot) {
    const originals = Array.from(originalRoot.querySelectorAll('img'));
    const clones = Array.from(clonedRoot.querySelectorAll('img'));

    await Promise.all(originals.map(async (original, index) => {
      const clone = clones[index];
      if (!clone || clone.tagName !== 'IMG') return;
      const source = original.currentSrc || original.src;
      if (!source || source.startsWith('data:')) return;

      try {
        const url = new URL(source, original.ownerDocument.baseURI);
        if (url.origin !== window.location.origin) return;
        const response = await fetch(url.href, {credentials: 'same-origin'});
        if (!response.ok) return;
        clone.src = await blobToDataUrl(await response.blob());
        clone.removeAttribute('srcset');
      } catch (_) {
        // A missing optional media asset must not block the rest of the pack.
      }
    }));
  }

  function removeNonVisualNodes(root) {
    root.querySelectorAll('script, iframe, video, audio').forEach((node) => node.remove());
  }

  function copyDocumentAttributes(documentRef, clonedBody) {
    for (const attribute of Array.from(documentRef.body.attributes)) {
      clonedBody.setAttribute(attribute.name, attribute.value);
    }
  }

  async function renderDocumentToPng(profile) {
    const documentRef = frame.contentDocument;
    if (!documentRef?.documentElement || !documentRef.body) {
      throw new Error('The Getfit page could not be read for capture.');
    }

    const clonedBody = documentRef.body.cloneNode(true);
    if (!clonedBody || clonedBody.nodeType !== Node.ELEMENT_NODE) {
      throw new Error('The Getfit page could not be cloned for capture.');
    }

    copyDocumentAttributes(documentRef, clonedBody);
    syncFormState(documentRef.body, clonedBody);
    syncCanvasState(documentRef.body, clonedBody);
    removeNonVisualNodes(clonedBody);
    await inlineImages(documentRef.body, clonedBody);

    const css = collectCss(documentRef);
    const fullHeight = Math.max(
      profile.height,
      documentRef.documentElement.scrollHeight,
      documentRef.body.scrollHeight,
    );
    const fullWidth = profile.width;

    const xhtmlDocument = document.implementation.createHTMLDocument('Getfit capture');
    const wrapper = xhtmlDocument.createElement('div');
    wrapper.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    wrapper.style.width = `${fullWidth}px`;
    wrapper.style.minHeight = `${fullHeight}px`;

    const style = xhtmlDocument.createElement('style');
    style.textContent = [
      ':root{color-scheme:normal;}',
      'html,body{margin:0!important;width:100%!important;min-height:100%!important;}',
      css,
    ].join('\n');
    wrapper.appendChild(style);
    wrapper.appendChild(xhtmlDocument.importNode(clonedBody, true));

    const serialized = new XMLSerializer().serializeToString(wrapper);
    const svg = [
      `<svg xmlns="http://www.w3.org/2000/svg" width="${fullWidth}" height="${fullHeight}" viewBox="0 0 ${fullWidth} ${fullHeight}">`,
      `<foreignObject x="0" y="0" width="${fullWidth}" height="${fullHeight}">`,
      serialized,
      '</foreignObject>',
      '</svg>',
    ].join('');

    const svgUrl = URL.createObjectURL(
      new Blob([svg], {type: 'image/svg+xml;charset=utf-8'}),
    );

    try {
      const image = new Image();
      await new Promise((resolve, reject) => {
        const timeout = window.setTimeout(
          () => reject(new Error('Timed out rendering the page snapshot.')),
          15000,
        );
        image.onload = () => {
          window.clearTimeout(timeout);
          resolve();
        };
        image.onerror = () => {
          window.clearTimeout(timeout);
          reject(new Error('Browser could not rasterise the page snapshot.'));
        };
        image.src = svgUrl;
      });

      const canvas = document.createElement('canvas');
      canvas.width = fullWidth;
      canvas.height = fullHeight;
      const context = canvas.getContext('2d', {alpha: false});
      if (!context) throw new Error('Canvas rendering is not available.');

      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, fullWidth, fullHeight);
      context.drawImage(image, 0, 0, fullWidth, fullHeight);

      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
          (value) => value ? resolve(value) : reject(new Error('PNG capture failed.')),
          'image/png',
        );
      });

      return {blob, width: fullWidth, height: fullHeight};
    } finally {
      URL.revokeObjectURL(svgUrl);
    }
  }

  function uint16(value) {
    const bytes = new Uint8Array(2);
    new DataView(bytes.buffer).setUint16(0, value, true);
    return bytes;
  }

  function uint32(value) {
    const bytes = new Uint8Array(4);
    new DataView(bytes.buffer).setUint32(0, value >>> 0, true);
    return bytes;
  }

  function concatBytes(parts) {
    const length = parts.reduce((total, part) => total + part.length, 0);
    const output = new Uint8Array(length);
    let offset = 0;
    for (const part of parts) {
      output.set(part, offset);
      offset += part.length;
    }
    return output;
  }

  const crcTable = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let value = n;
      for (let bit = 0; bit < 8; bit += 1) {
        value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
      }
      table[n] = value >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
      crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function dosTimestamp(date) {
    const year = Math.max(1980, date.getFullYear());
    const time = (date.getHours() << 11)
      | (date.getMinutes() << 5)
      | Math.floor(date.getSeconds() / 2);
    const day = ((year - 1980) << 9)
      | ((date.getMonth() + 1) << 5)
      | date.getDate();
    return {time, day};
  }

  async function bytesFromBlob(blob) {
    return new Uint8Array(await blob.arrayBuffer());
  }

  async function createZip(files) {
    const encoder = new TextEncoder();
    const localParts = [];
    const centralParts = [];
    let offset = 0;
    const timestamp = dosTimestamp(new Date());

    for (const file of files) {
      const name = encoder.encode(file.name);
      const data = file.data instanceof Uint8Array ? file.data : await bytesFromBlob(file.data);
      const crc = crc32(data);

      const localHeader = concatBytes([
        uint32(0x04034b50),
        uint16(20),
        uint16(0),
        uint16(0),
        uint16(timestamp.time),
        uint16(timestamp.day),
        uint32(crc),
        uint32(data.length),
        uint32(data.length),
        uint16(name.length),
        uint16(0),
        name,
        data,
      ]);
      localParts.push(localHeader);

      centralParts.push(concatBytes([
        uint32(0x02014b50),
        uint16(20),
        uint16(20),
        uint16(0),
        uint16(0),
        uint16(timestamp.time),
        uint16(timestamp.day),
        uint32(crc),
        uint32(data.length),
        uint32(data.length),
        uint16(name.length),
        uint16(0),
        uint16(0),
        uint16(0),
        uint16(0),
        uint32(0),
        uint32(offset),
        name,
      ]));
      offset += localHeader.length;
    }

    const local = concatBytes(localParts);
    const central = concatBytes(centralParts);
    const end = concatBytes([
      uint32(0x06054b50),
      uint16(0),
      uint16(0),
      uint16(files.length),
      uint16(files.length),
      uint32(central.length),
      uint32(local.length),
      uint16(0),
    ]);

    return new Blob([local, central, end], {type: 'application/zip'});
  }

  function slug(value) {
    return value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function downloadZip(blob) {
    const now = new Date();
    const stamp = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
      '-',
      String(now.getHours()).padStart(2, '0'),
      String(now.getMinutes()).padStart(2, '0'),
    ].join('');
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `getfit-ui-review-${stamp}.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async function runCapture(profiles) {
    cancelled = false;
    resetTargetStates();
    captureAllButton.disabled = true;
    responsiveButton.disabled = true;
    cancelButton.hidden = false;
    setProgress(0, targets.length * profiles.length);
    const files = [];
    const captures = [];
    let completed = 0;

    try {
      for (const target of targets) {
        if (cancelled) throw new Error('Capture cancelled.');

        for (const profile of profiles) {
          if (cancelled) throw new Error('Capture cancelled.');
          setTargetState(target.key, 'active', profile.label);
          setMessage(`Loading ${target.label} · ${profile.label}…`);
          await loadTarget(target, profile);

          setMessage(`Capturing ${target.label} · ${profile.label}…`);
          const shot = await renderDocumentToPng(profile);
          const fileName = `screenshots/${String(completed + 1).padStart(2, '0')}-${slug(target.key)}-${slug(profile.key)}.png`;
          files.push({name: fileName, data: shot.blob});
          captures.push({
            page: target.key,
            page_label: target.label,
            profile: profile.key,
            profile_label: profile.label,
            width: shot.width,
            height: shot.height,
            file: fileName,
          });
          completed += 1;
          setProgress(completed, targets.length * profiles.length);
        }

        setTargetState(target.key, 'done', 'Captured');
      }

      const manifest = {
        format: 'getfit-ui-review-pack-v2',
        capture_method: 'same-origin-dom-raster',
        app_version: document.body.dataset.appVersion,
        display_name: document.body.dataset.displayName,
        presentation_profile: document.body.dataset.presentationProfile,
        captured_at: new Date().toISOString(),
        browser: navigator.userAgent,
        host_viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
          device_pixel_ratio: window.devicePixelRatio,
        },
        captures,
        screenshot_count: files.length,
      };

      const encoder = new TextEncoder();
      files.push({
        name: 'review-manifest.json',
        data: encoder.encode(JSON.stringify(manifest, null, 2)),
      });
      files.push({
        name: 'README.txt',
        data: encoder.encode(
          'Getfit UI Review Pack\n\nUpload this ZIP directly into ChatGPT for visual review against the approved Home Workout Assistant design board.\n\nScreenshots are generated from the same-origin rendered Getfit DOM. No screen-sharing permission is required. The pack contains rendered screenshots plus non-sensitive capture metadata. It does not contain Home Assistant IDs, integration IDs, credentials or application database content.\n',
        ),
      });

      setMessage('Building ZIP…');
      const zip = await createZip(files);
      downloadZip(zip);
      setProgress(1, 1);
      setMessage(`Done — ${completed} screenshots downloaded in one ZIP. Upload that ZIP to ChatGPT.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Capture failed.';
      setMessage(message);
      for (const target of targets) {
        const row = document.querySelector(`[data-target="${target.key}"]`);
        if (row?.classList.contains('is-active')) setTargetState(target.key, 'error', 'Failed');
      }
    } finally {
      captureAllButton.disabled = false;
      responsiveButton.disabled = false;
      cancelButton.hidden = true;
    }
  }

  captureAllButton?.addEventListener('click', () => {
    void runCapture([currentViewportProfile()]);
  });

  responsiveButton?.addEventListener('click', () => {
    void runCapture(fullProfiles);
  });

  cancelButton?.addEventListener('click', () => {
    cancelled = true;
    setMessage('Capture will stop after the current page.');
  });

  applyProfile(currentViewportProfile());
})();
