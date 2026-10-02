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
  const video = document.getElementById('capture-video');
  const frameNotice = document.getElementById('frame-notice');

  if (!targetsNode || !frame || !frameShell || !video) return;

  const targets = JSON.parse(targetsNode.textContent || '[]');
  const fullProfiles = [
    {key: 'phone', label: 'Phone', width: 390, height: 844},
    {key: 'tablet', label: 'Tablet', width: 820, height: 1180},
    {key: 'desktop', label: 'Desktop', width: 1440, height: 1000},
  ];

  let captureStream = null;
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

  function isFramed() {
    try {
      return window.top !== window.self;
    } catch (_) {
      return true;
    }
  }

  if (isFramed() && frameNotice) {
    frameNotice.hidden = false;
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

    const availableWidth = Math.max(220, window.innerWidth - 18);
    const availableHeight = Math.max(320, window.innerHeight - 18);
    const scale = Math.min(
      1,
      availableWidth / profile.width,
      availableHeight / profile.height,
    );
    frameShell.style.transform = `scale(${scale})`;
    if (stageLabel) stageLabel.textContent = profile.label;
  }

  async function loadTarget(target) {
    if (frame.src === new URL(target.url, window.location.href).href) {
      try {
        frame.contentWindow?.location.reload();
      } catch (_) {
        frame.src = target.url;
      }
    } else {
      frame.src = target.url;
    }

    await new Promise((resolve, reject) => {
      const timeout = window.setTimeout(
        () => reject(new Error(`Timed out loading ${target.label}`)),
        12000,
      );
      frame.onload = () => {
        window.clearTimeout(timeout);
        resolve();
      };
    });
    await sleep(650);
  }

  async function startScreenCapture() {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      throw new Error(
        'This browser does not support tab capture. Open this page in current Chrome or Edge on desktop.',
      );
    }

    const options = {
      video: true,
      audio: false,
      preferCurrentTab: true,
      selfBrowserSurface: 'include',
      surfaceSwitching: 'exclude',
      monitorTypeSurfaces: 'exclude',
    };

    const stream = await navigator.mediaDevices.getDisplayMedia(options);
    const track = stream.getVideoTracks()[0];
    const displaySurface = track?.getSettings?.().displaySurface;
    if (displaySurface && displaySurface !== 'browser') {
      for (const item of stream.getTracks()) item.stop();
      throw new Error('Choose “This Tab” in the browser sharing prompt, not Window or Entire Screen.');
    }

    captureStream = stream;
    video.srcObject = stream;
    await new Promise((resolve) => {
      if (video.readyState >= 1) resolve();
      else video.addEventListener('loadedmetadata', resolve, {once: true});
    });
    await video.play();

    track?.addEventListener('ended', () => {
      if (!cancelled) {
        cancelled = true;
        setMessage('Tab sharing stopped. Capture cancelled.');
      }
    });
  }

  function stopScreenCapture() {
    if (captureStream) {
      for (const track of captureStream.getTracks()) track.stop();
    }
    captureStream = null;
    video.srcObject = null;
  }

  async function captureFrame(profile) {
    document.body.classList.add('is-capturing');
    applyProfile(profile);
    await nextFrame();
    await nextFrame();
    await sleep(140);

    const rect = frameShell.getBoundingClientRect();
    if (!video.videoWidth || !video.videoHeight) {
      throw new Error('The shared tab did not provide a video frame.');
    }

    const scaleX = video.videoWidth / window.innerWidth;
    const scaleY = video.videoHeight / window.innerHeight;
    const sx = Math.max(0, rect.left * scaleX);
    const sy = Math.max(0, rect.top * scaleY);
    const sw = Math.min(video.videoWidth - sx, rect.width * scaleX);
    const sh = Math.min(video.videoHeight - sy, rect.height * scaleY);

    const canvas = document.createElement('canvas');
    canvas.width = profile.width;
    canvas.height = profile.height;
    const context = canvas.getContext('2d', {alpha: false});
    if (!context) throw new Error('Canvas rendering is not available.');

    context.drawImage(
      video,
      sx,
      sy,
      sw,
      sh,
      0,
      0,
      profile.width,
      profile.height,
    );

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (value) => value ? resolve(value) : reject(new Error('PNG capture failed.')),
        'image/png',
      );
    });
    document.body.classList.remove('is-capturing');
    return blob;
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
    if (isFramed()) {
      if (frameNotice) frameNotice.hidden = false;
      setMessage('Open this tool in a new tab before starting automatic capture.');
      return;
    }

    cancelled = false;
    resetTargetStates();
    captureAllButton.disabled = true;
    responsiveButton.disabled = true;
    cancelButton.hidden = false;
    setProgress(0, targets.length * profiles.length);
    const files = [];
    let completed = 0;

    try {
      setMessage('Choose “This Tab” in the browser sharing prompt…');
      await startScreenCapture();

      for (const target of targets) {
        if (cancelled) throw new Error('Capture cancelled.');
        setTargetState(target.key, 'active', 'Loading');
        setMessage(`Loading ${target.label}…`);
        await loadTarget(target);

        for (const profile of profiles) {
          if (cancelled) throw new Error('Capture cancelled.');
          applyProfile(profile);
          if (stageLabel) stageLabel.textContent = `${target.label} · ${profile.label}`;
          setTargetState(target.key, 'active', profile.label);
          setMessage(`Capturing ${target.label} · ${profile.label}…`);
          await sleep(360);
          const image = await captureFrame(profile);
          files.push({
            name: `screenshots/${String(completed + 1).padStart(2, '0')}-${slug(target.key)}-${slug(profile.key)}.png`,
            data: image,
          });
          completed += 1;
          setProgress(completed, targets.length * profiles.length);
        }

        setTargetState(target.key, 'done', 'Captured');
      }

      stopScreenCapture();
      document.body.classList.remove('is-capturing');

      const manifest = {
        format: 'getfit-ui-review-pack-v1',
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
        profiles: profiles.map(({key, label, width, height}) => ({key, label, width, height})),
        pages: targets.map(({key, label}) => ({key, label})),
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
          'Getfit UI Review Pack\n\nUpload this ZIP directly into ChatGPT for visual review against the approved Home Workout Assistant design board.\n\nThe pack contains rendered screenshots only plus non-sensitive capture metadata. It does not contain Home Assistant IDs, integration IDs, credentials or application database content.\n',
        ),
      });

      setMessage('Building ZIP…');
      const zip = await createZip(files);
      downloadZip(zip);
      setProgress(1, 1);
      setMessage(`Done — ${completed} screenshots downloaded in one ZIP. Upload that ZIP to ChatGPT.`);
    } catch (error) {
      stopScreenCapture();
      document.body.classList.remove('is-capturing');
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
    stopScreenCapture();
    document.body.classList.remove('is-capturing');
    setMessage('Capture cancelled.');
  });

  window.addEventListener('resize', () => {
    const label = stageLabel?.textContent || '';
    if (!document.body.classList.contains('is-capturing') && label.includes('current viewport')) {
      applyProfile(currentViewportProfile());
    }
  });

  applyProfile(currentViewportProfile());
})();
