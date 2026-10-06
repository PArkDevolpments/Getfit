(() => {
  const targetsNode = document.getElementById('review-targets');
  const frame = document.getElementById('review-frame');
  const frameShell = document.getElementById('frame-shell');
  const stageLabel = document.getElementById('stage-label');
  const deviceAuditButton = document.getElementById('run-device-audit');
  const automatedAuditButton = document.getElementById('run-automated-audit');
  const responsiveButton = document.getElementById('capture-responsive');
  const cancelButton = document.getElementById('cancel-capture');
  const downloadReviewLink = document.getElementById('download-review');
  const progressBar = document.getElementById('progress-bar');
  const progressMessage = document.getElementById('progress-message');
  const acceptanceSpecNode = document.getElementById('acceptance-specification');
  const acceptanceStorageKeyNode = document.getElementById('acceptance-storage-key');

  if (!targetsNode || !frame || !frameShell) return;

  const targets = JSON.parse(targetsNode.textContent || '[]');
  const acceptanceSpecification = acceptanceSpecNode
    ? JSON.parse(acceptanceSpecNode.textContent || '{}')
    : {};
  const fullProfiles = [
    {key: 'ha-phone', label: 'Home Assistant target · 440×820', width: 440, height: 820},
    {key: 'phone', label: 'iPhone 16 Pro Max', width: 430, height: 932},
    {key: 'tablet', label: 'Tablet', width: 820, height: 1180},
    {key: 'desktop', label: 'Desktop', width: 1440, height: 1000},
  ];

  let cancelled = false;
  let latestDownloadUrl = null;
  let captureRunning = false;
  let navigationSequence = 0;

  const sandboxStateTargets = new Set([
    'strength-active',
    'strength-feedback',
    'strength-pain',
    'strength-rest',
    'bike-finisher',
    'treadmill',
    'interval-hard',
    'interval-recovery',
  ]);

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  const nextFrame = () => new Promise((resolve) => window.requestAnimationFrame(resolve));

  function getAcceptanceResults() {
    const fallback = {
      format: 'getfit-acceptance-results-v1',
      app_version: document.body.dataset.appVersion,
      spec_version: null,
      updated_at: null,
      criteria: {},
    };
    if (!acceptanceStorageKeyNode) return fallback;
    try {
      const storageKey = JSON.parse(acceptanceStorageKeyNode.textContent || 'null');
      if (!storageKey) return fallback;
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) {
      return fallback;
    }
  }

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
    const visualWidth = Math.round(window.visualViewport?.width || window.innerWidth);
    const visualHeight = Math.round(window.visualViewport?.height || window.innerHeight);
    const width = Math.max(320, visualWidth);
    const height = Math.max(568, visualHeight);
    return {
      key: `device-${width}x${height}`,
      label: `This device · ${width}×${height}`,
      width,
      height,
    };
  }

  function hostShellSnapshot() {
    const root = document.documentElement;
    const styles = getComputedStyle(root);
    return {
      ready: root.dataset.haShellReady === 'true',
      host: root.dataset.haPanelHost || null,
      requested: root.dataset.haShellRequested === 'true',
      attempts: Number(root.dataset.haShellAttempts || 0),
      timed_out: root.dataset.haShellTimedOut === 'true',
      safe_area: {
        top: styles.getPropertyValue('--ha-safe-top').trim() || '0px',
        right: styles.getPropertyValue('--ha-safe-right').trim() || '0px',
        bottom: styles.getPropertyValue('--ha-safe-bottom').trim() || '0px',
        left: styles.getPropertyValue('--ha-safe-left').trim() || '0px',
      },
    };
  }

  async function waitForHostShellReady(timeoutMs = 6500) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const snapshot = hostShellSnapshot();
      if (snapshot.ready) {
        await nextFrame();
        await sleep(350);
        return hostShellSnapshot();
      }
      await sleep(100);
    }
    return hostShellSnapshot();
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

  function captureIdentity(target) {
    const documentRef = frame.contentDocument;
    const player = documentRef?.getElementById('workout-player');
    const activeMedia = documentRef?.querySelector('.exercise-media-tab.is-active');
    let path = '';
    try {
      path = frame.contentWindow?.location.pathname || '';
    } catch (_) {
      path = '';
    }
    return {
      expected_path: new URL(target.url, window.location.href).pathname,
      path,
      review_state: player?.dataset.reviewState || null,
      media_tab: activeMedia?.dataset.mediaTab || null,
      ready_state: documentRef?.readyState || 'unknown',
    };
  }

  function captureIdentityMatches(target, identity, {requireMedia = true} = {}) {
    if (!identity || identity.path !== identity.expected_path) return false;
    if (
      sandboxStateTargets.has(target.key)
      && identity.review_state !== target.key
    ) {
      return false;
    }
    if (requireMedia && target.media_tab && identity.media_tab !== target.media_tab) {
      return false;
    }
    return true;
  }

  async function waitForTargetIdentity(target, {requireMedia = true, timeoutMs = 6500} = {}) {
    const started = Date.now();
    let identity = captureIdentity(target);
    while (Date.now() - started < timeoutMs) {
      identity = captureIdentity(target);
      if (
        identity.ready_state === 'complete'
        && captureIdentityMatches(target, identity, {requireMedia})
      ) {
        return identity;
      }
      await sleep(75);
    }
    throw new Error(
      `Capture identity mismatch for ${target.label}: expected ${identity.expected_path}`
      + ` / ${target.key}, received ${identity.path} / ${identity.review_state || 'none'}.`,
    );
  }

  async function settleLoadedTarget(target) {
    await nextFrame();
    await nextFrame();
    const fonts = frame.contentDocument?.fonts;
    if (fonts?.ready) {
      try {
        await fonts.ready;
      } catch (_) {
        // A font readiness failure must not bypass the identity gate below.
      }
    }
    await sleep(150);
    return await waitForTargetIdentity(target);
  }

  async function loadTarget(target, profile) {
    applyProfile(profile);
    const wanted = new URL(target.url, window.location.href);
    wanted.searchParams.set(
      '__getfit_review_capture',
      `${Date.now()}-${++navigationSequence}-${target.key}-${profile.key}`,
    );
    const expectedPath = wanted.pathname;

    await new Promise((resolve, reject) => {
      const cleanup = () => {
        window.clearTimeout(timeout);
        frame.removeEventListener('load', onLoad);
      };
      const timeout = window.setTimeout(() => {
        cleanup();
        reject(new Error(`Timed out loading ${target.label}`));
      }, 15000);
      const onLoad = () => {
        let activePath = '';
        try {
          activePath = frame.contentWindow?.location.pathname || '';
        } catch (_) {
          activePath = '';
        }
        if (activePath !== expectedPath) return;
        cleanup();
        resolve();
      };

      frame.addEventListener('load', onLoad);
      frame.src = wanted.href;
    });

    await waitForTargetIdentity(target, {requireMedia: false});
    await nextFrame();
    await sleep(180);

    if (target.media_tab) {
      const documentRef = frame.contentDocument;
      const tab = documentRef?.querySelector(
        `[data-media-tab="${target.media_tab}"]`,
      );
      if (!tab) {
        throw new Error(
          `Review target ${target.label} could not activate media tab ${target.media_tab}.`,
        );
      }
      tab.click();
      await nextFrame();
      await sleep(180);
    }

    return await settleLoadedTarget(target);
  }

  function detectPageState(target) {
    const documentRef = frame.contentDocument;
    if (!documentRef?.body) return 'unknown';
    if (!sandboxStateTargets.has(target.key)) return 'ready';
    const text = documentRef.body.textContent || '';
    return text.includes('No workout is currently in progress') ? 'empty' : 'active';
  }

  function criterionTargetKeys(criterionId) {
    if (criterionId.startsWith('TODAY-')) return ['today'];

    if (criterionId === 'STRENGTH-06') return ['strength-feedback'];
    if (criterionId === 'STRENGTH-07' || criterionId === 'STRENGTH-08') {
      return ['strength-rest'];
    }
    if (criterionId.startsWith('STRENGTH-')) return ['strength-active'];

    if (criterionId === 'TECH-04') {
      return [
        'exercise-video-floor-press',
        'exercise-video-supported-reverse-lunge',
        'exercise-video-lateral-raise',
      ];
    }
    if (criterionId.startsWith('TECH-')) return ['exercise-detail'];

    if (criterionId === 'CARDIO-02') return ['treadmill'];
    if (criterionId === 'CARDIO-04') return ['interval-hard'];
    if (criterionId === 'CARDIO-05') return ['interval-recovery'];
    if (criterionId.startsWith('CARDIO-')) return ['bike-finisher'];

    if (criterionId === 'PROGRESS-01') return ['progress-review'];
    if (criterionId.startsWith('PROGRESS-')) return ['progress'];

    if (criterionId === 'LIBRARY-01') return ['library'];
    if (criterionId === 'LIBRARY-02') return ['exercise-detail'];
    if (criterionId.startsWith('SETTINGS-')) return ['more'];

    if (criterionId === 'REGRESSION-01' || criterionId === 'REGRESSION-04') {
      return ['today'];
    }
    if (criterionId === 'REGRESSION-05') {
      return [
        'today',
        'plan',
        'strength-active',
        'strength-feedback',
        'strength-pain',
        'strength-rest',
        'bike-finisher',
        'treadmill',
        'interval-hard',
        'interval-recovery',
        'library',
        'exercise-detail',
        'exercise-video-floor-press',
        'exercise-video-supported-reverse-lunge',
        'exercise-video-lateral-raise',
        'more',
      ];
    }
    if (criterionId === 'REGRESSION-02') return ['strength-active'];
    if (criterionId === 'REGRESSION-03') return ['progress'];
    if (criterionId === 'REGRESSION-06') return ['more'];
    return [];
  }

  function pageText(documentRef, profile = null) {
    if (!documentRef?.body) return '';
    const nodeFilter = documentRef.defaultView?.NodeFilter;
    if (!nodeFilter) {
      return (documentRef?.body?.innerText || '').replace(/\s+/g, ' ').trim();
    }
    const walker = documentRef.createTreeWalker(
      documentRef.body,
      nodeFilter.SHOW_TEXT,
    );
    const parts = [];
    let textNode = walker.nextNode();
    while (textNode) {
      const value = (textNode.nodeValue || '').replace(/\s+/g, ' ').trim();
      const parent = textNode.parentElement;
      if (
        value
        && parent
        && elementReviewState(parent, documentRef, profile).visible
      ) {
        parts.push(value);
      }
      textNode = walker.nextNode();
    }
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  }

  function composedParentElement(node) {
    if (!node) return null;
    if (node.assignedSlot) return node.assignedSlot;
    if (node.parentElement) return node.parentElement;
    const root = node.getRootNode?.();
    return root?.host?.nodeType === 1 ? root.host : null;
  }

  function composedAncestors(node) {
    const ancestors = [];
    const seen = new Set();
    let current = node;
    while (current && !seen.has(current)) {
      ancestors.push(current);
      seen.add(current);
      current = composedParentElement(current);
    }
    return ancestors;
  }

  function intersectsOverflowClip(value) {
    return ['auto', 'clip', 'hidden', 'scroll'].includes(value);
  }

  function intersectRect(rect, clip, {clipX = true, clipY = true} = {}) {
    const left = clipX ? Math.max(rect.left, clip.left) : rect.left;
    const right = clipX ? Math.min(rect.right, clip.right) : rect.right;
    const top = clipY ? Math.max(rect.top, clip.top) : rect.top;
    const bottom = clipY ? Math.min(rect.bottom, clip.bottom) : rect.bottom;
    return {
      left,
      top,
      right,
      bottom,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top),
    };
  }

  function clippedViewportRect(node, documentRef, rect, viewportWidth, viewportHeight) {
    let clipped = intersectRect(
      rect,
      {left: 0, top: 0, right: viewportWidth, bottom: viewportHeight},
    );
    let clippedByAncestor = false;
    let current = composedParentElement(node);
    while (
      current
      && clipped.width > 0
      && clipped.height > 0
      && documentRef?.defaultView
    ) {
      const currentStyle = documentRef.defaultView.getComputedStyle(current);
      const clipX = intersectsOverflowClip(currentStyle.overflowX);
      const clipY = intersectsOverflowClip(currentStyle.overflowY);
      if (clipX || clipY) {
        const ancestorRect = current.getBoundingClientRect?.();
        if (ancestorRect) {
          const left = ancestorRect.left + Number(current.clientLeft || 0);
          const top = ancestorRect.top + Number(current.clientTop || 0);
          const width = Number(current.clientWidth || 0);
          const height = Number(current.clientHeight || 0);
          const next = intersectRect(
            clipped,
            {
              left,
              top,
              right: left + width,
              bottom: top + height,
            },
            {clipX, clipY},
          );
          if (
            Math.abs(next.left - clipped.left) > 0.5
            || Math.abs(next.top - clipped.top) > 0.5
            || Math.abs(next.right - clipped.right) > 0.5
            || Math.abs(next.bottom - clipped.bottom) > 0.5
          ) {
            clippedByAncestor = true;
          }
          clipped = next;
        }
      }
      current = composedParentElement(current);
    }
    return {rect: clipped, clippedByAncestor};
  }

  function isScreenReaderOnly(node, style) {
    if (!node || !style) return false;
    if (
      composedAncestors(node).some(
        (current) => current.matches?.('.sr-only, .visually-hidden, .screen-reader-only'),
      )
    ) {
      return true;
    }

    const width = Number.parseFloat(style.width || '0');
    const height = Number.parseFloat(style.height || '0');
    const clipped = style.clip
      && style.clip !== 'auto'
      && style.clip !== 'rect(auto, auto, auto, auto)';
    const clipPathed = style.clipPath && style.clipPath !== 'none';
    return style.position === 'absolute'
      && width <= 1
      && height <= 1
      && style.overflow === 'hidden'
      && Boolean(clipped || clipPathed);
  }

  function pointerReachable(node, documentRef, clippedRect) {
    if (
      !node
      || !documentRef?.elementFromPoint
      || clippedRect.width <= 0
      || clippedRect.height <= 0
    ) {
      return false;
    }

    const insetX = Math.min(2, clippedRect.width / 4);
    const insetY = Math.min(2, clippedRect.height / 4);
    const points = [
      [(clippedRect.left + clippedRect.right) / 2, (clippedRect.top + clippedRect.bottom) / 2],
      [clippedRect.left + insetX, clippedRect.top + insetY],
      [clippedRect.right - insetX, clippedRect.top + insetY],
      [clippedRect.left + insetX, clippedRect.bottom - insetY],
      [clippedRect.right - insetX, clippedRect.bottom - insetY],
    ];

    return points.some(([x, y]) => {
      const hit = documentRef.elementFromPoint(x, y);
      return Boolean(
        hit
        && (
          hit === node
          || node.contains?.(hit)
        )
      );
    });
  }

  function elementReviewState(node, documentRef, profile = null) {
    const viewportWidth = documentRef?.documentElement?.clientWidth
      || documentRef?.defaultView?.innerWidth
      || profile?.width
      || 0;
    const viewportHeight = documentRef?.documentElement?.clientHeight
      || documentRef?.defaultView?.innerHeight
      || profile?.height
      || 0;
    const style = node && documentRef?.defaultView
      ? documentRef.defaultView.getComputedStyle(node)
      : null;
    const rect = node?.getBoundingClientRect?.() || {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0,
      width: 0,
      height: 0,
    };
    const ancestors = composedAncestors(node);
    const hiddenByAttribute = ancestors.some(
      (current) => Boolean(current.hidden || current.hasAttribute?.('hidden')),
    );
    const ariaHidden = ancestors.some(
      (current) => current.getAttribute?.('aria-hidden') === 'true',
    );
    const inert = ancestors.some(
      (current) => current.hasAttribute?.('inert'),
    );
    const disabled = Boolean(node?.disabled)
      || node?.getAttribute?.('aria-disabled') === 'true';
    const pointerBlocked = Boolean(style && style.pointerEvents === 'none');
    let ancestorRendered = Boolean(style);
    for (const current of ancestors) {
      if (!ancestorRendered || !documentRef?.defaultView) break;
      const currentStyle = documentRef.defaultView.getComputedStyle(current);
      const currentOpacity = Number.parseFloat(currentStyle.opacity || '1');
      if (
        currentStyle.display === 'none'
        || currentStyle.contentVisibility === 'hidden'
        || currentOpacity <= 0
      ) {
        ancestorRendered = false;
      }
    }
    if (
      style
      && (style.visibility === 'hidden' || style.visibility === 'collapse')
    ) {
      ancestorRendered = false;
    }
    const screenReaderOnly = isScreenReaderOnly(node, style);
    const clientRectCount = node?.getClientRects?.().length || 0;
    const rendered = Boolean(
      ancestorRendered
      && rect.width > 0
      && rect.height > 0
      && clientRectCount > 0
    );
    const visible = rendered
      && !hiddenByAttribute
      && !screenReaderOnly;
    const clipping = visible
      ? clippedViewportRect(
        node,
        documentRef,
        rect,
        viewportWidth,
        viewportHeight,
      )
      : {
        rect: {left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0},
        clippedByAncestor: false,
      };
    const clippedRect = clipping.rect;
    const inViewport = visible
      && clippedRect.width > 0
      && clippedRect.height > 0;
    const fullyInViewport = inViewport
      && rect.top >= 0
      && rect.left >= 0
      && rect.bottom <= viewportHeight
      && rect.right <= viewportWidth
      && Math.abs(clippedRect.width - rect.width) <= 1
      && Math.abs(clippedRect.height - rect.height) <= 1;
    const pointerIsReachable = inViewport
      && !pointerBlocked
      && pointerReachable(node, documentRef, clippedRect);
    const reachable = visible
      && !disabled
      && !inert
      && !pointerBlocked;

    return {
      visible,
      reachable,
      rendered,
      disabled,
      inert,
      pointer_events_blocked: pointerBlocked,
      pointer_reachable: pointerIsReachable,
      hidden_attribute: hiddenByAttribute,
      aria_hidden: ariaHidden,
      screen_reader_only: screenReaderOnly,
      in_viewport: inViewport,
      fully_in_viewport: fullyInViewport,
      clipped_by_ancestor: clipping.clippedByAncestor,
      geometry: {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
      visible_geometry: {
        left: Math.round(clippedRect.left),
        top: Math.round(clippedRect.top),
        right: Math.round(clippedRect.right),
        bottom: Math.round(clippedRect.bottom),
        width: Math.round(clippedRect.width),
        height: Math.round(clippedRect.height),
      },
    };
  }

  function visuallyPresent(documentRef, selector, profile) {
    return Array.from(documentRef?.querySelectorAll(selector) || []).some(
      (node) => elementReviewState(node, documentRef, profile).visible,
    );
  }

  function reachableControl(documentRef, selector, profile) {
    return Array.from(documentRef?.querySelectorAll(selector) || []).find(
      (node) => elementReviewState(node, documentRef, profile).reachable,
    ) || null;
  }

  function controlReviewRecord(node, documentRef, profile) {
    const state = elementReviewState(node, documentRef, profile);
    const visualLabel = (
      node.textContent
      || node.getAttribute('placeholder')
      || ''
    ).replace(/\s+/g, ' ').trim();
    const accessibleName = (
      node.getAttribute('aria-label')
      || visualLabel
      || ''
    ).replace(/\s+/g, ' ').trim();
    const value = 'value' in node && state.visible
      ? String(node.value || '').trim()
      : '';
    return {
      kind: node.tagName.toLowerCase(),
      visual_label: visualLabel || null,
      accessible_name: accessibleName || null,
      value: value || null,
      disabled: state.disabled,
      visibility: state,
    };
  }

  function collectReviewContent(target, documentRef, profile, identity, pageState) {
    const visibleText = pageText(documentRef, profile);

    const visualHeadingRecords = [];
    const nonVisualHeadingRecords = [];
    for (const node of documentRef?.querySelectorAll('h1, h2, h3') || []) {
      const label = (node.textContent || '').replace(/\s+/g, ' ').trim();
      if (!label) continue;
      const visibility = elementReviewState(node, documentRef, profile);
      const record = {label, visibility};
      if (visibility.visible) visualHeadingRecords.push(record);
      else nonVisualHeadingRecords.push(record);
    }

    const visualControls = [];
    const nonVisualControls = [];
    const controlAccessibility = [];
    for (
      const node of documentRef?.querySelectorAll(
        'button, a, input, select, textarea, summary',
      ) || []
    ) {
      const record = controlReviewRecord(node, documentRef, profile);
      controlAccessibility.push({
        kind: record.kind,
        visual_label: record.visual_label,
        accessible_name: record.accessible_name,
        disabled: record.disabled,
        visibility: record.visibility,
      });
      if (record.visibility.visible) {
        visualControls.push({
          kind: record.kind,
          visual_label: record.visual_label,
          value: record.value,
          disabled: record.disabled,
          visibility: record.visibility,
        });
      } else {
        nonVisualControls.push({
          kind: record.kind,
          accessible_name: record.accessible_name,
          disabled: record.disabled,
          visibility: record.visibility,
        });
      }
    }

    const visualHeadings = visualHeadingRecords.map((item) => item.label);

    return {
      page: target.key,
      page_label: target.label,
      profile: profile.key,
      profile_label: profile.label,
      viewport: {width: profile.width, height: profile.height},
      page_state: pageState,
      source_path: identity.path,
      source_review_state: identity.review_state,
      source_media_tab: identity.media_tab,
      title: documentRef?.title || null,
      headings: visualHeadings,
      controls: visualControls,
      visible_text: visibleText,
      visual_evidence: {
        visual_headings: visualHeadingRecords,
        visual_controls: visualControls,
        visible_text: visibleText,
      },
      accessibility_metadata: {
        controls: controlAccessibility,
        non_visual_headings: nonVisualHeadingRecords,
        non_visual_controls: nonVisualControls,
      },
    };
  }

  function automatedResult(status, evidence, profile) {
    return {
      status,
      evidence,
      profile: profile.key,
      viewport: {width: profile.width, height: profile.height},
    };
  }

  function fullyVisible(node, documentRef, profile) {
    if (!node) return false;
    const state = elementReviewState(node, documentRef, profile);
    if (!state.fully_in_viewport) return false;
    const viewportHeight = documentRef.documentElement.clientHeight
      || documentRef.defaultView?.innerHeight
      || profile.height;
    const nav = profile.width <= 820
      ? documentRef.querySelector('.primary-nav')
      : null;
    const navRect = nav?.getBoundingClientRect();
    const mobileReserve = navRect
      ? Math.max(0, viewportHeight - navRect.top)
      : 0;
    return state.geometry.top >= 0
      && state.geometry.bottom <= viewportHeight - mobileReserve
      && state.geometry.width > 0
      && state.geometry.height > 0;
  }

  function liveCardioTargetsFit(node, documentRef, profile) {
    if (profile.width > 700) return true;
    return fullyVisible(
      node?.querySelector('.cardio-prescription-grid'),
      documentRef,
      profile,
    );
  }

  function auditTouchTargets(documentRef) {
    const selectors = [
      '[data-primary-action]',
      '.complete-set-button',
      '[data-set-feedback]',
      '.workout-command-bar button',
      '.cardio-completion-toggle',
      '.primary-action',
      '.secondary-action',
      '.ghost-action',
      '.primary-nav__item',
      '.bottom-nav__item',
      '.exercise-media-tab',
      '.exercise-card__open',
      '.coach-dashboard-card__settings',
    ];
    const seen = new Set();
    const failures = [];
    let checked = 0;

    for (const node of documentRef.querySelectorAll(selectors.join(','))) {
      if (seen.has(node)) continue;
      seen.add(node);
      const state = elementReviewState(node, documentRef);
      if (!state.reachable) continue;
      checked += 1;
      const rect = state.geometry;
      if (rect.height < 44 || rect.width < 44) {
        failures.push({
          label: (
            node.textContent
            || node.getAttribute('aria-label')
            || node.tagName
          ).trim(),
          width: rect.width,
          height: rect.height,
        });
      }
    }

    return {checked, failures};
  }

  function evaluateCriterion(criterionId, target, documentRef, pageState, profile) {
    if (!documentRef?.body) {
      return automatedResult('FAIL', 'Rendered document was unavailable to the audit runner.', profile);
    }

    const text = pageText(documentRef, profile);
    const domText = (documentRef.body.textContent || '').replace(/\s+/g, ' ').trim();
    const has = (selector) => visuallyPresent(documentRef, selector, profile);
    const all = (...selectors) => selectors.every((selector) => has(selector));
    const includes = (...values) => values.every((value) => text.includes(value));
    const noInternalIdentity = !/(hwa_person_id|pep_person_id|menu_person_id|health_profile_id|person_id)/i.test(domText);

    if (criterionId === 'TODAY-01') {
      return automatedResult(
        all('.coach-dashboard-card', '.workout-selection')
          ? 'PASS'
          : 'FAIL',
        'Checked for the approved dark coaching dashboard plus adjacent Week 1 workout-selection surface.',
        profile,
      );
    }
    if (criterionId === 'TODAY-02') {
      const displayName = document.body.dataset.displayName || window.document.body.dataset.displayName || '';
      const visiblePerson = displayName ? text.includes(displayName) : text.includes('Kris');
      const noSelector = !documentRef.querySelector(
        'select[name*="person"], input[name*="person_id"], [data-person-selector]',
      );
      return automatedResult(
        visiblePerson && noSelector && noInternalIdentity ? 'PASS' : 'FAIL',
        'Checked visible trusted identity, absence of a browser person selector and absence of internal identity terms.',
        profile,
      );
    }
    if (criterionId === 'TODAY-03') {
      const card = documentRef.querySelector('.next-workout-card');
      return automatedResult(
        card && includes('Week 1', 'Day 1', 'Upper Body + Bike') ? 'PASS' : 'REVIEW_REQUIRED',
        card
          ? 'Next Workout card is present; current rendered programme position was checked against the approved Week 1 Day 1 baseline.'
          : 'Next Workout card was not found.',
        profile,
      );
    }
    if (criterionId === 'TODAY-04') {
      const action = reachableControl(
        documentRef,
        '[data-primary-action="start"], [data-primary-action="resume"]',
        profile,
      );
      return automatedResult(
        action ? 'PASS' : 'FAIL',
        action
          ? `Primary action is visible and reachable as ${action.dataset.primaryAction}; mutation/resume persistence remains covered by automated integration tests.`
          : 'No visible, active and reachable Start or Resume primary action was rendered.',
        profile,
      );
    }
    if (criterionId === 'TODAY-05') {
      const krisTargets = includes('Floor press', '6 kg each', 'Row', '10 kg', 'Shoulder press', '5 kg each');
      return automatedResult(
        krisTargets ? 'PASS' : 'REVIEW_REQUIRED',
        krisTargets
          ? 'Rendered Kris snapshot contains the approved Floor press, Row and Shoulder press loads.'
          : 'The exact approved Kris target trio was not all visible in this rendered state.',
        profile,
      );
    }
    if (criterionId === 'TODAY-06') {
      return automatedResult(
        all('.week-status-dots', '.weekly-cardio') && includes('Last workout')
          ? 'PASS'
          : 'FAIL',
        'Checked weekly status indicators, Last workout and Weekly cardio evidence surfaces.',
        profile,
      );
    }
    if (criterionId === 'TODAY-07') {
      return automatedResult(
        has('.weekly-goal') && includes('150 minutes of moderate activity', '2–4 strength sessions')
          ? 'PASS'
          : 'FAIL',
        'Checked the approved weekly activity and strength-session goal copy.',
        profile,
      );
    }
    if (criterionId === 'TODAY-08') {
      const root = documentRef.documentElement;
      const horizontalOverflow = root.scrollWidth > root.clientWidth + 4;
      return automatedResult(
        horizontalOverflow ? 'FAIL' : 'REVIEW_REQUIRED',
        horizontalOverflow
          ? `Horizontal overflow detected: scrollWidth ${root.scrollWidth}px vs clientWidth ${root.clientWidth}px.`
          : 'No horizontal overflow detected. Overall visual hierarchy and polish require visual review of the captured snapshots.',
        profile,
      );
    }

    if (criterionId.startsWith('STRENGTH-')) {
      if (pageState === 'empty') {
        return automatedResult('BLOCKED', 'No active workout draft was rendered.', profile);
      }
      if (criterionId === 'STRENGTH-01') {
        return automatedResult(
          has('#workout-player[data-workout-state="active"]') ? 'PASS' : 'FAIL',
          'Checked that the active workout player is rendered.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-02') {
        const floorPress = Array.from(documentRef.querySelectorAll('.strength-item')).some(
          (node) => (node.dataset.exerciseId || '').includes('dumbbell_floor_press')
            && elementReviewState(node, documentRef, profile).visible,
        );
        return automatedResult(
          floorPress && has('.workout-progress') ? 'REVIEW_REQUIRED' : 'FAIL',
          floorPress
            ? 'Floor Press and workout progress exist; dominance and coaching hierarchy require visual review.'
            : 'Floor Press or workout progress was not found.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-03') {
        const floorPress = Array.from(documentRef.querySelectorAll('.strength-item')).find(
          (node) => (node.dataset.exerciseId || '').includes('dumbbell_floor_press')
            && elementReviewState(node, documentRef, profile).visible,
        );
        const floorText = floorPress?.textContent || '';
        const metrics = /10\s*reps/i.test(floorText)
          && /6(?:\.0+)?\s*kg/i.test(floorText)
          && /2[–-]0[–-]1/.test(floorText);
        return automatedResult(
          metrics ? 'PASS' : 'FAIL',
          metrics
            ? 'Floor Press contains the approved reps, load and tempo targets.'
            : 'One or more approved Floor Press targets were missing from the rendered player.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-04') {
        const completeSet = Array.from(documentRef.querySelectorAll('button, label, span')).find(
          (node) => /complete set/i.test((node.textContent || '').trim())
            && elementReviewState(node, documentRef, profile).reachable,
        );
        return automatedResult(
          completeSet ? 'REVIEW_REQUIRED' : 'FAIL',
          completeSet
            ? 'Complete Set control is visible and reachable; visual primacy requires screenshot review.'
            : 'No visible and reachable “Complete Set” primary action was found.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-05') {
        return automatedResult(
          all('input[name*="-reps"]', 'input[name*="-rpe"]', 'input[name*="-rir"]')
            ? 'PASS'
            : 'FAIL',
          'Checked actual reps plus RPE/RIR recording controls.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-06') {
        const feedbackPanel = documentRef.querySelector('[data-set-feedback-panel]');
        const feedbackButtons = Array.from(
          feedbackPanel?.querySelectorAll('[data-set-feedback]') || [],
        );
        const feedback = ['Too easy', 'About right', 'Too hard', 'Pain'].every(
          (value) => text.includes(value),
        );
        const feedbackVisible = profile.width > 700
          || fullyVisible(feedbackPanel, documentRef, profile);
        const touchSized = feedbackButtons.every((button) => {
          const state = elementReviewState(button, documentRef, profile);
          return state.reachable
            && state.geometry.width >= 44
            && state.geometry.height >= 44;
        });
        return automatedResult(
          feedback && feedbackVisible && feedbackButtons.length === 4 && touchSized
            ? 'PASS'
            : 'FAIL',
          feedback && feedbackVisible && feedbackButtons.length === 4 && touchSized
            ? 'Dedicated set-complete feedback is fully visible with four touch-safe coaching choices.'
            : 'Set-complete feedback is missing, clipped below the active viewport, or has undersized choices.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-07') {
        const mainRest = documentRef.querySelector('[data-main-rest-panel]');
        const restText = mainRest?.textContent || '';
        const restVisible = profile.width > 700
          || fullyVisible(mainRest, documentRef, profile);
        return automatedResult(
          mainRest && restVisible && /01:30/.test(restText) ? 'PASS' : 'FAIL',
          mainRest && restVisible && /01:30/.test(restText)
            ? 'Dedicated 01:30 rest state is fully visible and uses the prescribed 75–90 second recovery range.'
            : 'Dedicated 01:30 rest state is missing or clipped below the active viewport.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-08') {
        return automatedResult(
          has('.main-rest-next') && includes('Next:')
            ? 'PASS'
            : 'FAIL',
          'Checked the dedicated rest-state next-set preview.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-09') {
        const controlSelectors = [
          '#previous-stage',
          '#pause-workout',
          '#skip-stage',
          '#next-stage',
          '#stop-workout',
        ];
        const allReachable = controlSelectors.every((selector) => reachableControl(
          documentRef,
          selector,
          profile,
        ));
        return automatedResult(
          allReachable ? 'PASS' : 'FAIL',
          allReachable
            ? 'Previous, Pause, Skip, Next and Stop are visible, active and reachable.'
            : 'One or more workout command controls are hidden, inactive or unreachable.',
          profile,
        );
      }
      if (criterionId === 'STRENGTH-10') {
        const playerNode = documentRef.querySelector('#workout-player');
        const review = playerNode?.dataset.reviewMode === 'true';
        return automatedResult(
          playerNode ? 'REVIEW_REQUIRED' : 'FAIL',
          review
            ? 'Review sandbox intentionally disables writes; live draft persistence remains covered by integration/restart tests.'
            : 'Live workout player is present; draft persistence remains covered by integration/restart tests.',
          profile,
        );
      }
    }

    if (criterionId.startsWith('TECH-')) {
      const mediaUnavailable = includes('Media unavailable')
        || includes('Visual guide not yet approved');
      if (criterionId === 'TECH-01') {
        const movementMedia = has('.exercise-phase img, .exercise-single-demo img');
        return automatedResult(
          movementMedia && !mediaUnavailable ? 'REVIEW_REQUIRED' : 'FAIL',
          movementMedia && !mediaUnavailable
            ? 'Movement-specific local media is rendered; coaching quality requires visual review.'
            : 'Movement-specific local technique media was not rendered.',
          profile,
        );
      }
      if (criterionId === 'TECH-02') {
        const threeStage = ['Start', 'Lower', 'Drive Up'].every((value) => text.includes(value));
        return automatedResult(
          threeStage ? 'REVIEW_REQUIRED' : 'FAIL',
          threeStage
            ? 'Three movement phases are present; visual quality requires review.'
            : 'Start → Lower → Drive Up sequence was not found.',
          profile,
        );
      }
      if (criterionId === 'TECH-03') {
        return automatedResult(
          has('.cue-list li') ? 'REVIEW_REQUIRED' : 'FAIL',
          has('.cue-list li')
            ? 'Movement technique cues are present; coaching quality requires review.'
            : 'No approved technique cue list was rendered.',
          profile,
        );
      }
      if (criterionId === 'TECH-04') {
        const modes = ['Images', 'Technique', 'Video'].every((value) => text.includes(value));
        const localVideo = documentRef.querySelector('.exercise-local-video source');
        const localSource = localVideo?.getAttribute('src') || localVideo?.dataset.videoSrc || '';
        const localConfigured = localSource.includes('/exercise-videos/');
        return automatedResult(
          modes && localConfigured ? 'REVIEW_REQUIRED' : 'FAIL',
          modes && localConfigured
            ? 'Images / Technique / Video modes are present with a configured local MP4 exercise video. Visual playback still requires screenshot/device review.'
            : 'The local exercise video route was not found.',
          profile,
        );
      }
      if (criterionId === 'TECH-05') {
        const genericFallback = has('.exercise-demo-fallback');
        return automatedResult(
          genericFallback || mediaUnavailable ? 'FAIL' : 'PASS',
          genericFallback || mediaUnavailable
            ? 'A generic/unapproved media fallback is still active.'
            : 'No generic fallback is active for the reviewed exercise; local approved media is available.',
          profile,
        );
      }
    }

    if (criterionId.startsWith('CARDIO-')) {
      if (pageState === 'empty') {
        return automatedResult('BLOCKED', 'No active workout draft was rendered.', profile);
      }
      const bike = Array.from(documentRef.querySelectorAll('.cardio-item')).find(
        (node) => node.dataset.equipment === 'SPIN_BIKE'
          && elementReviewState(node, documentRef, profile).visible,
      );
      const treadmill = Array.from(documentRef.querySelectorAll('.cardio-item')).find(
        (node) => node.dataset.equipment === 'TREADMILL'
          && elementReviewState(node, documentRef, profile).visible,
      );
      const activeCardio = documentRef.querySelector('.cardio-item:not([hidden])');
      if (criterionId === 'CARDIO-01') {
        if (!bike) return automatedResult('BLOCKED', 'No spin-bike stage exists in the active workout.', profile);
        const visibleBike = activeCardio?.dataset.equipment === 'SPIN_BIKE'
          ? activeCardio
          : bike;
        const bikeText = visibleBike?.textContent || '';
        const bikeModelCorrect = /Cadence/.test(bikeText)
          && /Resistance/.test(bikeText)
          && !/Speed km\/h/.test(bikeText)
          && !/Incline %/.test(bikeText);
        const liveTargetsVisible = liveCardioTargetsFit(
          visibleBike,
          documentRef,
          profile,
        );
        return automatedResult(
          bikeModelCorrect && liveTargetsVisible ? 'PASS' : 'FAIL',
          bikeModelCorrect && liveTargetsVisible
            ? 'Checked spin-bike cadence/resistance model and confirmed live targets fit above navigation.'
            : bikeModelCorrect
              ? 'Spin-bike model is correct, but live targets are clipped below the active viewport.'
              : 'Spin-bike cadence/resistance model is invalid or contains treadmill-only fields.',
          profile,
        );
      }
      if (criterionId === 'CARDIO-02') {
        if (!treadmill) return automatedResult('BLOCKED', 'No treadmill stage exists in the active workout.', profile);
        const visibleTreadmill = activeCardio?.dataset.equipment === 'TREADMILL'
          ? activeCardio
          : treadmill;
        const treadmillText = visibleTreadmill?.textContent || '';
        const incline = visibleTreadmill?.querySelector('input[name*="-incline"]');
        const treadmillModelCorrect = /Speed km\/h/.test(treadmillText)
          && /Incline %/.test(treadmillText)
          && incline?.getAttribute('max') === '20'
          && !/Cadence min rpm/.test(treadmillText);
        const liveTargetsVisible = liveCardioTargetsFit(
          visibleTreadmill,
          documentRef,
          profile,
        );
        return automatedResult(
          treadmillModelCorrect && liveTargetsVisible ? 'PASS' : 'FAIL',
          treadmillModelCorrect && liveTargetsVisible
            ? 'Checked treadmill speed/incline model and confirmed live targets fit above navigation.'
            : treadmillModelCorrect
              ? 'Treadmill model is correct, but live targets are clipped below the active viewport.'
              : 'Treadmill speed/incline model is invalid, exceeds the 20% equipment cap, or exposes bike-only cadence.',
          profile,
        );
      }
      if (criterionId === 'CARDIO-03') {
        const finisher = Array.from(documentRef.querySelectorAll('.cardio-item')).find(
          (node) => node.dataset.equipment === 'SPIN_BIKE'
            && node.dataset.segmentType === 'CONDITIONING'
            && elementReviewState(node, documentRef, profile).visible,
        );
        if (!finisher) {
          return automatedResult(
            'BLOCKED',
            'No Day 1 spin-bike conditioning stage exists in the review workout.',
            profile,
          );
        }
        const bikeText = finisher.textContent || '';
        const goodTargets = /15:00/.test(bikeText)
          && /80–90\s*rpm/.test(bikeText)
          && /moderate/i.test(bikeText)
          && /RPE\s*5(?:\.0+)?/.test(bikeText);
        const liveTargetsVisible = liveCardioTargetsFit(
          activeCardio?.dataset.segmentType === 'CONDITIONING' ? activeCardio : finisher,
          documentRef,
          profile,
        );
        return automatedResult(
          goodTargets && liveTargetsVisible ? 'REVIEW_REQUIRED' : 'FAIL',
          goodTargets && liveTargetsVisible
            ? 'Dedicated bike-finisher state contains 15:00, 80–90 rpm, moderate resistance and RPE 5, with live targets above navigation.'
            : goodTargets
              ? 'Approved Day 1 bike-finisher targets are correct, but the live target grid is clipped below the active viewport.'
              : 'Approved Day 1 bike-finisher state/targets were not all detected.',
          profile,
        );
      }
      if (criterionId === 'CARDIO-04') {
        const hard = Array.from(documentRef.querySelectorAll('.cardio-item--hard')).find(
          (node) => elementReviewState(node, documentRef, profile).visible,
        );
        const hardText = hard?.textContent || '';
        const targets = /00:30/.test(hardText)
          && /85–100\s*rpm/.test(hardText)
          && /RPE\s*7(?:\.0+)?–8(?:\.0+)?/.test(hardText);
        const liveTargetsVisible = liveCardioTargetsFit(
          activeCardio?.classList.contains('cardio-item--hard') ? activeCardio : hard,
          documentRef,
          profile,
        );
        return automatedResult(
          hard && targets && liveTargetsVisible ? 'REVIEW_REQUIRED' : 'FAIL',
          hard && targets && liveTargetsVisible
            ? 'Dedicated HARD interval state contains 00:30, 85–100 rpm and RPE 7–8, with live targets above navigation.'
            : hard && targets
              ? 'Required HARD interval targets are correct, but the live target grid is clipped below the active viewport.'
              : 'Required HARD interval state/targets were not found.',
          profile,
        );
      }
      if (criterionId === 'CARDIO-05') {
        const recovery = Array.from(documentRef.querySelectorAll('.cardio-item--recovery')).find(
          (node) => elementReviewState(node, documentRef, profile).visible,
        );
        const recoveryText = recovery?.textContent || '';
        const targets = /01:30/.test(recoveryText)
          && /60–75\s*rpm/.test(recoveryText)
          && /Light/i.test(recoveryText)
          && /RPE\s*2(?:\.0+)?–3(?:\.0+)?/.test(recoveryText);
        const liveTargetsVisible = liveCardioTargetsFit(
          activeCardio?.classList.contains('cardio-item--recovery') ? activeCardio : recovery,
          documentRef,
          profile,
        );
        return automatedResult(
          recovery && targets && liveTargetsVisible ? 'REVIEW_REQUIRED' : 'FAIL',
          recovery && targets && liveTargetsVisible
            ? 'Dedicated recovery state contains 01:30, 60–75 rpm, light resistance and RPE 2–3, with live targets above navigation.'
            : recovery && targets
              ? 'Required recovery interval targets are correct, but the live target grid is clipped below the active viewport.'
              : 'Required recovery interval state/targets were not found.',
          profile,
        );
      }
      if (criterionId === 'CARDIO-06') {
        return automatedResult(
          bike && reachableControl(documentRef, '.cardio-item:not([hidden]) input[name*="-rpe"]', profile)
            ? 'PASS'
            : 'REVIEW_REQUIRED',
          'Checked separation of prescribed cardio content and actual RPE input where available.',
          profile,
        );
      }
    }

    if (criterionId === 'PROGRESS-01') {
      const chart = Array.from(documentRef.querySelectorAll('svg[data-progress-chart]')).find(
        (node) => elementReviewState(node, documentRef, profile).visible,
      );
      const points = Number(chart?.dataset.pointCount || 0);
      return automatedResult(
        chart && points >= 2 ? 'REVIEW_REQUIRED' : 'FAIL',
        chart && points >= 2
          ? `Evidence chart component renders ${points} review points; visual clarity requires review and live mode remains evidence-only.`
          : 'A populated evidence progression chart was not rendered.',
        profile,
      );
    }
    if (criterionId === 'PROGRESS-02') {
      return automatedResult(
        has('.history-timeline') ? 'REVIEW_REQUIRED' : 'FAIL',
        'Recent history exists; product-level usefulness and progression framing require review.',
        profile,
      );
    }
    if (criterionId === 'PROGRESS-03') {
      return automatedResult(
        all('.progress-kpi-grid', '.history-timeline') ? 'PASS' : 'FAIL',
        'Checked programme-completion and completed-session evidence surfaces.',
        profile,
      );
    }
    if (criterionId === 'PROGRESS-04') {
      return automatedResult(
        noInternalIdentity && !documentRef.querySelector('[data-person-selector]')
          ? 'PASS'
          : 'FAIL',
        'Checked person-scoped presentation and absence of a browser identity selector/internal IDs.',
        profile,
      );
    }

    if (criterionId === 'LIBRARY-01') {
      const cards = Array.from(documentRef.querySelectorAll('.exercise-card')).filter(
        (node) => elementReviewState(node, documentRef, profile).visible,
      );
      const sources = cards
        .map((card) => card.querySelector('.exercise-card__media img')?.getAttribute('src'))
        .filter(Boolean);
      const uniqueSources = new Set(sources);
      const movementSpecific = cards.length > 1 && sources.length === cards.length
        && uniqueSources.size === cards.length;
      return automatedResult(
        movementSpecific ? 'REVIEW_REQUIRED' : 'FAIL',
        movementSpecific
          ? 'Each programme exercise card uses a distinct local movement visual; overall art quality requires visual review.'
          : 'Exercise cards are missing distinct movement-specific local visuals.',
        profile,
      );
    }
    if (criterionId === 'LIBRARY-02') {
      return automatedResult(
        noInternalIdentity && has('.exercise-history-list') ? 'PASS' : 'FAIL',
        'Checked person-scoped recent exercise history and absence of internal identity terms.',
        profile,
      );
    }

    if (criterionId === 'SETTINGS-01') {
      if (includes('Equipment configuration unavailable')) {
        return automatedResult('BLOCKED', 'Live equipment configuration is unavailable.', profile);
      }
      const capabilities = includes('Treadmill', 'Incline up to 20%', 'Spin bike', 'No incline', 'Adjustable dumbbells');
      return automatedResult(
        capabilities ? 'PASS' : 'REVIEW_REQUIRED',
        capabilities
          ? 'Configured treadmill, bike and dumbbell capabilities match the accepted equipment model.'
          : 'Not all expected equipment-capability copy was detected.',
        profile,
      );
    }
    if (criterionId === 'SETTINGS-02') {
      return automatedResult(
        has('#calibration-settings') ? 'REVIEW_REQUIRED' : 'FAIL',
        'Calibration surface exists; consumer wording and progression behaviour require review.',
        profile,
      );
    }
    if (criterionId === 'SETTINGS-03') {
      const unsafe = /(https?:\/\/|token|secret|pep_person_id|menu_person_id|hwa_person_id)/i.test(domText);
      return automatedResult(
        has('#integration-settings') && !unsafe ? 'PASS' : 'FAIL',
        unsafe
          ? 'Integration surface exposed endpoint/credential/internal-ID-like content.'
          : 'Integration status is present without detected endpoints, tokens or cross-system IDs.',
        profile,
      );
    }

    if (criterionId === 'REGRESSION-01') {
      const navLinks = Array.from(documentRef.querySelectorAll('.primary-nav a'));
      const assets = Array.from(documentRef.querySelectorAll('link[rel="stylesheet"], script[src]'));
      const ingressPath = window.location.pathname.includes('/api/hassio_ingress/');
      const prefixOkay = !ingressPath || [...navLinks, ...assets].every((node) => {
        const value = node.href || node.src || '';
        return !value || value.includes('/api/hassio_ingress/');
      });
      return automatedResult(
        prefixOkay ? 'PASS' : 'FAIL',
        ingressPath
          ? 'Checked that rendered navigation/assets preserve the Home Assistant Ingress prefix.'
          : 'Direct-mode rendering detected; no escaped root-absolute asset/navigation URL was found.',
        profile,
      );
    }
    if (criterionId === 'REGRESSION-02') {
      return automatedResult(
        pageState === 'active' ? 'REVIEW_REQUIRED' : 'BLOCKED',
        pageState === 'active'
          ? 'Active draft exists; restart/resume persistence is covered by integration tests and remains review-required on LIVE.'
          : 'No active draft exists to review restart/resume behaviour.',
        profile,
      );
    }
    if (criterionId === 'REGRESSION-03') {
      return automatedResult(
        has('.history-timeline') ? 'REVIEW_REQUIRED' : 'BLOCKED',
        has('.history-timeline')
          ? 'History surface is present; canonical Pep export remains verified by automated contract tests.'
          : 'No completed history is available for live review.',
        profile,
      );
    }
    if (criterionId === 'REGRESSION-04') {
      const laterWeek = /Week\s+(?:[2-9]|[1-9]\d)/.test(text);
      return automatedResult(
        !laterWeek && noInternalIdentity ? 'PASS' : 'FAIL',
        !laterWeek
          ? 'No future Week 2+ programme content or browser identity selector was detected on Today.'
          : 'Future/unapproved programme week content was detected.',
        profile,
      );
    }
    if (criterionId === 'REGRESSION-05') {
      const root = documentRef.documentElement;
      const horizontalOverflow = root.scrollWidth > root.clientWidth + 4;
      const fitCriticalVerticalOverflow = sandboxStateTargets.has(target.key)
        && profile.width <= 700
        && root.scrollHeight > root.clientHeight + 4;
      const touchAudit = auditTouchTargets(documentRef);
      const failures = touchAudit.failures
        .map((item) => `${item.label || 'control'} ${item.width}×${item.height}px`)
        .join(', ');
      return automatedResult(
        horizontalOverflow || fitCriticalVerticalOverflow || touchAudit.failures.length
          ? 'FAIL'
          : 'PASS',
        horizontalOverflow
          ? `Horizontal overflow detected: ${root.scrollWidth}px > ${root.clientWidth}px.`
          : fitCriticalVerticalOverflow
            ? `Fit-critical workout state needs vertical scrolling: ${root.scrollHeight}px > ${root.clientHeight}px (+4px tolerance).`
            : touchAudit.failures.length
              ? `Touch targets below 44px detected: ${failures}.`
              : `No unintended overflow and ${touchAudit.checked} visible core controls meet the 44px touch-target floor.`,
        profile,
      );
    }
    if (criterionId === 'REGRESSION-06') {
      return automatedResult(
        'REVIEW_REQUIRED',
        'Browser audit cannot independently verify GitHub exact-main CI and public image pulls; release workflow evidence must be attached by the build pipeline.',
        profile,
      );
    }

    return automatedResult('REVIEW_REQUIRED', 'No safe deterministic browser check is defined for this criterion.', profile);
  }

  function aggregateAutomatedResults(samples) {
    const results = {};
    const specification = acceptanceSpecification || {};
    for (const gate of specification.gates || []) {
      for (const criterion of gate.criteria || []) {
        const entries = samples.filter((sample) => sample.criterion_id === criterion.criterion_id);
        let status = 'REVIEW_REQUIRED';
        if (entries.some((entry) => entry.status === 'FAIL')) status = 'FAIL';
        else if (entries.length && entries.every((entry) => entry.status === 'PASS')) status = 'PASS';
        else if (entries.length && entries.every((entry) => entry.status === 'BLOCKED')) status = 'BLOCKED';
        else if (entries.some((entry) => entry.status === 'BLOCKED')
          && !entries.some((entry) => entry.status === 'PASS')) status = 'BLOCKED';

        results[criterion.criterion_id] = {
          criterion_id: criterion.criterion_id,
          gate_id: gate.gate_id,
          title: criterion.title,
          status,
          mandatory: criterion.mandatory,
          evidence: entries.map((entry) => ({
            profile: entry.profile,
            viewport: entry.viewport,
            status: entry.status,
            evidence: entry.evidence,
          })),
        };
      }
    }
    return results;
  }

  function buildAutomatedReport(results, captures) {
    const rows = Object.values(results).map((result) => [
      '<tr>',
      `<td><strong>${result.criterion_id}</strong><br><small>${result.gate_id}</small></td>`,
      `<td>${result.title}</td>`,
      `<td><span class="status status-${result.status.toLowerCase().replace('_', '-')}">${result.status.replace('_', ' ')}</span></td>`,
      `<td>${result.evidence.map((item) => `${item.profile}: ${item.evidence}`).join('<br>')}</td>`,
      '</tr>',
    ].join('')).join('');
    const counts = Object.values(results).reduce((acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    }, {});
    return [
      '<!doctype html><html lang="en-GB"><head><meta charset="utf-8">',
      '<meta name="viewport" content="width=device-width,initial-scale=1">',
      '<title>Getfit Automated Specification Audit</title><style>',
      'body{margin:0;padding:24px;background:#071725;color:#eaf7ff;font-family:system-ui,sans-serif}',
      'main{max-width:1280px;margin:auto}.summary{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}',
      '.summary span,.status{padding:6px 9px;border-radius:999px;background:#173149;font-size:12px;font-weight:800}',
      '.status-pass{background:#103b29;color:#b9f6d2}.status-fail{background:#4b1c28;color:#ffd1da}',
      '.status-blocked{background:#473715;color:#ffe5a0}.status-review-required{background:#20364b;color:#c9dfef}',
      'table{width:100%;border-collapse:collapse;background:#0b2134;border-radius:14px;overflow:hidden}',
      'th,td{padding:10px;border-bottom:1px solid #1d3a50;text-align:left;vertical-align:top;font-size:12px}',
      'th{color:#9ec7df;background:#0e2a41}small{color:#7fa0b5}',
      '</style></head><body><main><h1>Getfit Automated Specification Audit</h1>',
      `<p>App v${document.body.dataset.appVersion} · specification ${acceptanceSpecification.spec_version || 'unknown'} · ${captures.length} visual snapshots</p>`,
      '<div class="summary">',
      `<span>PASS ${counts.PASS || 0}</span><span>FAIL ${counts.FAIL || 0}</span>`,
      `<span>BLOCKED ${counts.BLOCKED || 0}</span><span>REVIEW REQUIRED ${counts.REVIEW_REQUIRED || 0}</span>`,
      '</div><table><thead><tr><th>Criterion</th><th>Requirement</th><th>Result</th><th>Automated evidence</th></tr></thead><tbody>',
      rows,
      '</tbody></table></main></body></html>',
    ].join('');
  }

  function collectDeviceDiagnostics(target, documentRef, profile, hostShell) {
    const root = documentRef.documentElement;
    const touchAudit = auditTouchTargets(documentRef);
    const issues = [];
    const horizontalOverflow = root.scrollWidth > root.clientWidth + 4;
    if (horizontalOverflow) {
      issues.push({
        code: 'HORIZONTAL_OVERFLOW',
        detail: `scrollWidth ${root.scrollWidth}px exceeds clientWidth ${root.clientWidth}px`,
      });
    }

    const fitCriticalWorkoutStates = new Set([
      'strength-active',
      'strength-feedback',
      'strength-pain',
      'strength-rest',
      'bike-finisher',
      'treadmill',
      'interval-hard',
      'interval-recovery',
    ]);
    const verticalOverflow = fitCriticalWorkoutStates.has(target.key)
      && root.scrollHeight > root.clientHeight + 4;
    if (verticalOverflow) {
      issues.push({
        code: 'FIT_CRITICAL_VERTICAL_OVERFLOW',
        detail: {
          scroll_height: root.scrollHeight,
          client_height: root.clientHeight,
          overflow_px: root.scrollHeight - root.clientHeight,
          tolerance_px: 4,
        },
      });
    }
    if (touchAudit.failures.length) {
      issues.push({
        code: 'TOUCH_TARGETS',
        detail: touchAudit.failures,
      });
    }

    const haShellReady = Boolean(hostShell?.ready);
    const haPanelHost = hostShell?.host || null;
    const acceptedHosts = new Set([
      'home-assistant-app-panel',
      'getfit-full-canvas-panel',
    ]);
    if (profile.width <= 820 && !haShellReady) {
      issues.push({
        code: 'HOME_ASSISTANT_FULL_CANVAS_HANDSHAKE_MISSING',
        detail: {
          requested: Boolean(hostShell?.requested),
          attempts: Number(hostShell?.attempts || 0),
          timed_out: Boolean(hostShell?.timed_out),
        },
      });
    } else if (
      profile.width <= 820
      && haPanelHost
      && !acceptedHosts.has(haPanelHost)
    ) {
      issues.push({
        code: 'HOME_ASSISTANT_FULL_CANVAS_HOST_UNSUPPORTED',
        detail: {
          active_host: haPanelHost,
          accepted_hosts: Array.from(acceptedHosts),
        },
      });
    }

    const bottomNav = documentRef.querySelector('.primary-nav');
    const bottomNavRect = bottomNav?.getBoundingClientRect();
    if (profile.width <= 820 && bottomNavRect) {
      const navFitsViewport = Math.abs(bottomNavRect.left) <= 1
        && Math.abs(bottomNavRect.right - root.clientWidth) <= 1
        && Math.abs(bottomNavRect.bottom - root.clientHeight) <= 1;
      if (!navFitsViewport) {
        issues.push({
          code: 'BOTTOM_NAV_NOT_VIEWPORT_FIT',
          detail: {
            left: Math.round(bottomNavRect.left),
            right: Math.round(bottomNavRect.right),
            bottom: Math.round(bottomNavRect.bottom),
            viewport_width: root.clientWidth,
            viewport_height: root.clientHeight,
          },
        });
      }
    }

    const mustBeVisible = {
      'strength-active': '.complete-set-button',
      'strength-feedback': '[data-set-feedback-panel]',
      'strength-pain': '[data-pain-stop-panel]',
      'strength-rest': '[data-main-rest-panel]',
      'bike-finisher': '.cardio-item:not([hidden]) .cardio-prescription-grid',
      'treadmill': '.cardio-item:not([hidden]) .cardio-prescription-grid',
      'interval-hard': '.cardio-item:not([hidden]) .cardio-prescription-grid',
      'interval-recovery': '.cardio-item:not([hidden]) .cardio-prescription-grid',
    };
    const selector = mustBeVisible[target.key];
    if (selector) {
      const node = documentRef.querySelector(selector);
      if (!fullyVisible(node, documentRef, profile)) {
        issues.push({
          code: 'PRIMARY_STATE_BELOW_VIEWPORT',
          detail: `${selector} is not fully visible in the active device viewport`,
        });
      }
    }

    return {
      page: target.key,
      page_label: target.label,
      viewport: {width: profile.width, height: profile.height},
      scroll_width: root.scrollWidth,
      scroll_height: root.scrollHeight,
      client_width: root.clientWidth,
      client_height: root.clientHeight,
      viewport_band: root.dataset.viewportBand || null,
      viewport_engine: {
        ready: root.dataset.viewportReady === 'true',
        measured_width: Number(root.dataset.viewportWidth || 0),
        measured_height: Number(root.dataset.viewportHeight || 0),
        usable_height: Number.parseFloat(
          documentRef.defaultView?.getComputedStyle(root).getPropertyValue('--getfit-usable-h') || '0',
        ) || 0,
        nav_height: Number.parseFloat(
          documentRef.defaultView?.getComputedStyle(root).getPropertyValue('--getfit-nav-h') || '0',
        ) || 0,
      },
      touch_targets_checked: touchAudit.checked,
      ha_shell_ready: haShellReady,
      ha_panel_host: haPanelHost,
      ha_shell_requested: Boolean(hostShell?.requested),
      ha_shell_attempts: Number(hostShell?.attempts || 0),
      ha_shell_timed_out: Boolean(hostShell?.timed_out),
      ha_safe_area: hostShell?.safe_area || null,
      bottom_nav: bottomNavRect
        ? {
          left: Math.round(bottomNavRect.left),
          right: Math.round(bottomNavRect.right),
          top: Math.round(bottomNavRect.top),
          bottom: Math.round(bottomNavRect.bottom),
          width: Math.round(bottomNavRect.width),
          height: Math.round(bottomNavRect.height),
        }
        : null,
      issues,
    };
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

  function replaceCanvasState(originalRoot, clonedRoot) {
    const originals = Array.from(originalRoot.querySelectorAll('canvas'));
    const clones = Array.from(clonedRoot.querySelectorAll('canvas'));

    originals.forEach((original, index) => {
      const clone = clones[index];
      if (!clone || clone.tagName !== 'CANVAS') return;
      const placeholder = original.ownerDocument.createElement('div');
      placeholder.textContent = 'Canvas visual unavailable in review snapshot';
      placeholder.setAttribute(
        'style',
        [
          original.getAttribute('style') || '',
          `width:${original.clientWidth || original.width || 320}px`,
          `height:${original.clientHeight || original.height || 180}px`,
          'display:grid',
          'place-items:center',
          'border:1px dashed #8aa6b8',
          'border-radius:10px',
          'color:#60778c',
          'background:#eef5fa',
          'font:600 12px system-ui,sans-serif',
        ].join(';'),
      );
      clone.replaceWith(placeholder);
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

  function replaceExternalFrameState(root) {
    for (const localVideo of root.querySelectorAll('.exercise-video-embed video')) {
      const placeholder = root.ownerDocument.createElement('div');
      placeholder.className = 'review-external-frame-placeholder';
      placeholder.innerHTML = [
        '<span aria-hidden="true">▶</span>',
        '<strong>Local exercise video</strong>',
        '<small>Playback is supplied by the MP4 stored in Home Assistant media.</small>',
      ].join('');
      localVideo.replaceWith(placeholder);
    }
  }

  function removeNonVisualNodes(root) {
    root.querySelectorAll('script, iframe, video, audio').forEach((node) => node.remove());
  }

  function copyDocumentAttributes(documentRef, clonedBody) {
    for (const attribute of Array.from(documentRef.body.attributes)) {
      clonedBody.setAttribute(attribute.name, attribute.value);
    }
  }

  async function renderDocumentToSvg(profile, {viewportOnly = false} = {}) {
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
    replaceCanvasState(documentRef.body, clonedBody);
    replaceExternalFrameState(clonedBody);
    removeNonVisualNodes(clonedBody);
    await inlineImages(documentRef.body, clonedBody);

    const css = collectCss(documentRef);
    const fullHeight = viewportOnly
      ? profile.height
      : Math.max(
        profile.height,
        documentRef.documentElement.scrollHeight,
        documentRef.body.scrollHeight,
      );
    const fullWidth = profile.width;

    const xhtmlDocument = document.implementation.createHTMLDocument('Getfit capture');
    const wrapper = xhtmlDocument.createElement('div');
    wrapper.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    wrapper.setAttribute(
      'style',
      `width:${fullWidth}px;min-height:${fullHeight}px;overflow:hidden;`,
    );

    const style = xhtmlDocument.createElement('style');
    style.textContent = [
      ':root{color-scheme:normal;}',
      'html,body{margin:0!important;width:100%!important;min-height:100%!important;}',
      '*{animation:none!important;transition:none!important;caret-color:transparent!important;}',
      '.review-external-frame-placeholder{width:100%;height:100%;min-height:160px;display:grid;place-items:center;align-content:center;gap:8px;padding:20px;box-sizing:border-box;background:#07111a;color:#eaf6ff;text-align:center;}',
      '.review-external-frame-placeholder span{width:52px;height:52px;display:grid;place-items:center;border-radius:50%;background:#1fcf72;color:#04170f;font-weight:900;font-size:20px;}',
      '.review-external-frame-placeholder strong{font-size:16px;}',
      '.review-external-frame-placeholder small{max-width:320px;color:#9eb8ca;font-size:12px;line-height:1.4;}',
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

    return {
      blob: new Blob([svg], {type: 'image/svg+xml;charset=utf-8'}),
      width: fullWidth,
      height: fullHeight,
    };
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

  function prepareZipDownload(blob, prefix = 'getfit-ui-review', {autoDownload = true} = {}) {
    const now = new Date();
    const stamp = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
      '-',
      String(now.getHours()).padStart(2, '0'),
      String(now.getMinutes()).padStart(2, '0'),
    ].join('');
    const fileName = `${prefix}-${stamp}.zip`;

    if (latestDownloadUrl) URL.revokeObjectURL(latestDownloadUrl);
    latestDownloadUrl = URL.createObjectURL(blob);

    if (downloadReviewLink) {
      downloadReviewLink.href = latestDownloadUrl;
      downloadReviewLink.download = fileName;
      downloadReviewLink.textContent = `Download ${fileName}`;
      downloadReviewLink.hidden = false;
    }

    if (autoDownload) {
      const link = document.createElement('a');
      link.href = latestDownloadUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
  }


  function buildReviewGallery(captures) {
    const cards = captures.map((capture) => [
      '<article class="capture-card">',
      `<h2>${capture.page_label} · ${capture.profile_label}</h2>`,
      `<p>${capture.width} × ${capture.height}</p>`,
      `<img src="${capture.file}" alt="${capture.page_label} ${capture.profile_label} review snapshot">`,
      '</article>',
    ].join('')).join('');

    return [
      '<!doctype html><html lang="en-GB"><head><meta charset="utf-8">',
      '<meta name="viewport" content="width=device-width,initial-scale=1">',
      '<title>Getfit UI Review Gallery</title>',
      '<style>',
      'body{margin:0;padding:24px;background:#061321;color:#eaf6ff;font-family:system-ui,sans-serif}',
      'header{max-width:1200px;margin:0 auto 24px}h1{margin:0 0 8px}p{color:#9eb8ca}',
      '.grid{max-width:1200px;margin:auto;display:grid;gap:20px}',
      '.capture-card{padding:14px;border:1px solid #21415a;border-radius:16px;background:#0a2033}',
      '.capture-card h2{margin:0;font-size:16px}.capture-card p{margin:4px 0 12px;font-size:12px}',
      '.capture-card img{display:block;width:100%;height:auto;border-radius:10px;background:white}',
      '</style></head><body><header><h1>Getfit UI Review Gallery</h1>',
      '<p>Open this file after extracting the ZIP to browse every captured surface.</p>',
      '</header><main class="grid">', cards, '</main></body></html>',
    ].join('');
  }

  async function runCapture(profiles, {automated = false, deviceMode = false, hostShell = null} = {}) {
    if (captureRunning) {
      setMessage('A review capture is already running. Wait for it to finish before starting another.');
      return;
    }
    captureRunning = true;
    cancelled = false;
    resetTargetStates();
    if (deviceAuditButton) deviceAuditButton.disabled = true;
    if (automatedAuditButton) automatedAuditButton.disabled = true;
    responsiveButton.disabled = true;
    cancelButton.hidden = false;
    setProgress(0, targets.length * profiles.length);
    const files = [];
    const captures = [];
    const reviewContent = [];
    const auditSamples = [];
    const deviceDiagnostics = [];
    let completed = 0;

    try {
      for (const target of targets) {
        if (cancelled) throw new Error('Capture cancelled.');

        for (const profile of profiles) {
          if (cancelled) throw new Error('Capture cancelled.');
          setTargetState(target.key, 'active', profile.label);
          setMessage(`Loading ${target.label} · ${profile.label}…`);
          const identity = await loadTarget(target, profile);
          const documentRef = frame.contentDocument;
          if (!documentRef?.body || !captureIdentityMatches(target, identity)) {
            throw new Error(`Capture integrity check failed for ${target.label} · ${profile.label}.`);
          }

          const pageState = detectPageState(target);
          reviewContent.push(
            collectReviewContent(target, documentRef, profile, identity, pageState),
          );
          if (deviceMode) {
            deviceDiagnostics.push(
              collectDeviceDiagnostics(target, documentRef, profile, hostShell),
            );
          }
          if (automated) {
            for (const gate of acceptanceSpecification.gates || []) {
              for (const criterion of gate.criteria || []) {
                if (!criterionTargetKeys(criterion.criterion_id).includes(target.key)) continue;
                const result = evaluateCriterion(
                  criterion.criterion_id,
                  target,
                  documentRef,
                  pageState,
                  profile,
                );
                auditSamples.push({
                  criterion_id: criterion.criterion_id,
                  gate_id: gate.gate_id,
                  ...result,
                });
              }
            }
          }
          setMessage(`Capturing ${target.label} · ${profile.label}…`);
          const index = String(completed + 1).padStart(2, '0');

          if (deviceMode) {
            const viewportShot = await renderDocumentToSvg(profile, {viewportOnly: true});
            const viewportFile = `screenshots/${index}-${slug(target.key)}-viewport.svg`;
            files.push({name: viewportFile, data: viewportShot.blob});
            captures.push({
              page: target.key,
              page_label: target.label,
              profile: profile.key,
              profile_label: profile.label,
              capture_kind: 'viewport',
              width: viewportShot.width,
              height: viewportShot.height,
              page_state: pageState,
              source_path: identity.path,
              source_review_state: identity.review_state,
              source_media_tab: identity.media_tab,
              file: viewportFile,
            });

            const fullShot = await renderDocumentToSvg(profile);
            const fullFile = `full-pages/${index}-${slug(target.key)}-full.svg`;
            files.push({name: fullFile, data: fullShot.blob});
            captures.push({
              page: target.key,
              page_label: target.label,
              profile: profile.key,
              profile_label: profile.label,
              capture_kind: 'full-page',
              width: fullShot.width,
              height: fullShot.height,
              page_state: pageState,
              source_path: identity.path,
              source_review_state: identity.review_state,
              source_media_tab: identity.media_tab,
              file: fullFile,
            });
          } else {
            const shot = await renderDocumentToSvg(profile);
            const fileName = `screenshots/${index}-${slug(target.key)}-${slug(profile.key)}.svg`;
            files.push({name: fileName, data: shot.blob});
            captures.push({
              page: target.key,
              page_label: target.label,
              profile: profile.key,
              profile_label: profile.label,
              capture_kind: 'full-page',
              width: shot.width,
              height: shot.height,
              page_state: pageState,
              source_path: identity.path,
              source_review_state: identity.review_state,
              source_media_tab: identity.media_tab,
              file: fileName,
            });
          }
          completed += 1;
          setProgress(completed, targets.length * profiles.length);
        }

        const targetCaptures = captures.filter((capture) => capture.page === target.key);
        const emptyWorkout = target.key === 'workout'
          && targetCaptures.some((capture) => capture.page_state === 'empty');
        setTargetState(
          target.key,
          'done',
          emptyWorkout ? 'No active workout' : 'Captured',
        );
      }

      const manifest = {
        format: deviceMode ? 'getfit-device-review-pack-v2' : 'getfit-ui-review-pack-v4',
        capture_method: deviceMode
          ? 'same-origin-home-assistant-device-dom-vector'
          : 'same-origin-dom-vector',
        app_version: document.body.dataset.appVersion,
        display_name: document.body.dataset.displayName,
        presentation_profile: document.body.dataset.presentationProfile,
        captured_at: new Date().toISOString(),
        browser: navigator.userAgent,
        host_viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
          visual_width: Math.round(window.visualViewport?.width || window.innerWidth),
          visual_height: Math.round(window.visualViewport?.height || window.innerHeight),
          screen_width: window.screen?.width || null,
          screen_height: window.screen?.height || null,
          device_pixel_ratio: window.devicePixelRatio,
          max_touch_points: navigator.maxTouchPoints || 0,
        },
        device_mode: deviceMode,
        home_assistant_shell: deviceMode ? hostShell : null,
        captures,
        review_warnings: captures.some(
          (capture) => capture.page === 'workout' && capture.page_state === 'empty',
        )
          ? ['No active workout was captured. Start or resume a workout before Gate 2 review.']
          : [],
        snapshot_count: files.length,
      };

      const encoder = new TextEncoder();
      const acceptanceResults = getAcceptanceResults();
      const automatedResults = automated
        ? aggregateAutomatedResults(auditSamples)
        : {};
      files.push({
        name: 'acceptance-specification.json',
        data: encoder.encode(JSON.stringify(acceptanceSpecification, null, 2)),
      });
      files.push({
        name: 'acceptance-results.json',
        data: encoder.encode(JSON.stringify(acceptanceResults, null, 2)),
      });
      files.push({
        name: 'review-content.json',
        data: encoder.encode(JSON.stringify({
          format: 'getfit-review-content-v1',
          app_version: document.body.dataset.appVersion,
          generated_at: new Date().toISOString(),
          captures: reviewContent,
        }, null, 2)),
      });
      if (automated) {
        files.push({
          name: 'automated-acceptance-results.json',
          data: encoder.encode(JSON.stringify({
            format: 'getfit-automated-acceptance-v1',
            app_version: document.body.dataset.appVersion,
            spec_version: acceptanceSpecification.spec_version || null,
            generated_at: new Date().toISOString(),
            results: automatedResults,
          }, null, 2)),
        });
        files.push({
          name: 'automated-review-report.html',
          data: encoder.encode(buildAutomatedReport(automatedResults, captures)),
        });
      }
      files.push({
        name: 'review-manifest.json',
        data: encoder.encode(JSON.stringify(manifest, null, 2)),
      });
      if (deviceMode) {
        files.push({
          name: 'device-layout-diagnostics.json',
          data: encoder.encode(JSON.stringify(deviceDiagnostics, null, 2)),
        });
      }
      files.push({
        name: 'review-gallery.html',
        data: encoder.encode(buildReviewGallery(captures)),
      });
      files.push({
        name: 'AI-REVIEW-GUIDE.txt',
        data: encoder.encode(
          'Getfit AI Review Guide\n\n1. Read review-content.json for the rendered text, headings and controls from every captured state.\n2. Inspect ai-screenshots/*.png first when this pack was generated by CI; those are rasterised browser renders specifically for multimodal review.\n3. Use screenshots/*.svg and full-pages/*.svg as lossless backing evidence. Do not infer that an SVG is truncated merely because a text extractor stops inside its embedded CSS.\n4. Use review-manifest.json to map files to page, viewport and review state.\n5. Keep automated-acceptance-results.json separate from visual judgement: REVIEW_REQUIRED is not a failure.\n',
        ),
      });
      files.push({
        name: 'README.txt',
        data: encoder.encode(
          automated
            ? 'Getfit Automated Specification Audit Pack\n\nUpload this ZIP directly into ChatGPT. Start with AI-REVIEW-GUIDE.txt and review-content.json, then inspect the PNG screenshots when present. SVG files are the lossless vector backing evidence and may be truncated by text-only file extractors even when the SVG itself is complete. The pack also contains the versioned specification, automated PASS/FAIL/BLOCKED/REVIEW_REQUIRED results and an automated HTML report. REVIEW_REQUIRED means the check is intentionally left for visual/product judgement rather than unsafe mutation or guesswork.\n'
            : 'Getfit UI Review Pack\n\nUpload this ZIP directly into ChatGPT. Start with review-content.json for rendered text/controls and inspect PNG screenshots when present. SVG files remain the complete lossless vector evidence but should not be judged from partial text extraction.\n',
        ),
      });

      setMessage('Building ZIP…');
      const zip = await createZip(files);
      prepareZipDownload(
        zip,
        deviceMode ? 'getfit-device-review' : 'getfit-ui-review',
        {autoDownload: !deviceMode},
      );
      setProgress(1, 1);
      const emptyWorkout = captures.some(
        (capture) => capture.page === 'workout' && capture.page_state === 'empty',
      );
      setMessage(
        automated
          ? deviceMode
            ? `Done — this device was auto-reviewed across ${completed} Getfit states. Upload the ZIP to ChatGPT.`
            : `Done — automated specification audit complete with ${completed} visual snapshots. Upload the ZIP to ChatGPT.`
          : emptyWorkout
            ? `Done — ${completed} snapshots downloaded. No active workout was captured; start or resume one before the Gate 2 pack.`
            : `Done — ${completed} visual snapshots downloaded in one ZIP. Upload that ZIP to ChatGPT.`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Capture failed.';
      setMessage(message);
      for (const target of targets) {
        const row = document.querySelector(`[data-target="${target.key}"]`);
        if (row?.classList.contains('is-active')) setTargetState(target.key, 'error', 'Failed');
      }
    } finally {
      captureRunning = false;
      if (deviceAuditButton) deviceAuditButton.disabled = false;
      if (automatedAuditButton) automatedAuditButton.disabled = false;
      responsiveButton.disabled = false;
      cancelButton.hidden = true;
    }
  }

  async function runDeviceAudit() {
    document.body.classList.add('is-device-review');
    setMessage('Negotiating the Home Assistant full-canvas viewport…');
    const hostShell = await waitForHostShellReady();
    const profile = currentViewportProfile();
    setMessage(`Auto-reviewing this Home Assistant viewport at ${profile.width}×${profile.height}…`);
    await runCapture([profile], {automated: true, deviceMode: true, hostShell});
  }

  async function runAutomatedAudit() {
    setMessage('Starting full responsive specification audit…');
    await runCapture(fullProfiles, {automated: true});
  }

  deviceAuditButton?.addEventListener('click', () => {
    void runDeviceAudit();
  });

  automatedAuditButton?.addEventListener('click', () => {
    void runAutomatedAudit();
  });

  responsiveButton?.addEventListener('click', () => {
    void runCapture(fullProfiles, {automated: false});
  });

  cancelButton?.addEventListener('click', () => {
    cancelled = true;
    setMessage('Capture will stop after the current page.');
  });

  const initialProfile = currentViewportProfile();
  applyProfile(initialProfile);

  window.addEventListener('beforeunload', () => {
    if (latestDownloadUrl) URL.revokeObjectURL(latestDownloadUrl);
  });

  const params = new URLSearchParams(window.location.search);
  if (params.get('device') === '1') {
    document.body.classList.add('is-device-review');
  }
  if (params.get('device') === '1' && params.get('autorun') === '1') {
    window.setTimeout(() => void runDeviceAudit(), 350);
  }
})();
