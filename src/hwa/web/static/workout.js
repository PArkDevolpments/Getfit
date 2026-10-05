(() => {
  const player = document.getElementById('workout-player');
  if (!player) return;

  const reviewMode = player.dataset.reviewMode === 'true';
  const reviewState = player.dataset.reviewState || '';
  const draftPhase = player.dataset.draftPhase || 'ACTIVE_SET';
  const saveStatus = document.getElementById('save-status');
  const completionStatus = document.getElementById('completion-status');
  const completeButton = document.getElementById('complete-workout');
  const formInputs = [...document.querySelectorAll('.workout-item input, #session-rpe')];
  const stages = [...document.querySelectorAll('.workout-stage')];
  const progressBar = document.getElementById('workout-progress-bar');
  const progressLabel = document.getElementById('workout-progress-label');
  const progressValue = document.getElementById('workout-progress-value');
  const nextStageTitle = document.getElementById('next-stage-title');
  const previousButton = document.getElementById('previous-stage');
  const pauseButton = document.getElementById('pause-workout');
  const skipButton = document.getElementById('skip-stage');
  const nextButton = document.getElementById('next-stage');
  const stopButton = document.getElementById('stop-workout');
  const restLabel = document.getElementById('rest-timer-label');
  const restStartButton = document.getElementById('rest-start');
  const restResetButton = document.getElementById('rest-reset');
  const restDisplays = [...document.querySelectorAll('[data-rest-display]')];

  let version = Number(player.dataset.draftVersion || '0');
  let saveTimer = null;
  let saving = false;
  let pendingSave = false;
  let stageIndex = 0;
  let paused = false;
  let restSeconds = 0;
  let restRemaining = 0;
  let restInterval = null;
  let feedbackSet = null;
  let restoredUiState = {};
  const cardioTimers = [];

  const valueOf = (name) => document.querySelector(`[name="${name}"]`);
  const optionalNumber = (element) => {
    if (!element || element.value === '') return null;
    const value = Number(element.value);
    return Number.isFinite(value) ? value : null;
  };
  const checked = (name) => Boolean(valueOf(name)?.checked);

  function formatSeconds(totalSeconds) {
    const safe = Math.max(0, Math.round(Number(totalSeconds) || 0));
    const minutes = Math.floor(safe / 60);
    const seconds = safe % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  function collectStateData() {
    const state = {};
    for (const input of formInputs) {
      if (!input.name) continue;
      state[input.name] = input.type === 'checkbox' ? input.checked : input.value;
    }
    if (player.classList.contains('is-pain-stop')) {
      state.__pain_stop_item = stages[stageIndex]?.dataset.itemId || null;
    }
    if (player.classList.contains('is-resting')) {
      state.__rest_remaining = restRemaining;
      state.__rest_total = restSeconds;
    }
    const selectedFeedback = stages[stageIndex]?.querySelector(
      '[data-set-feedback][aria-pressed="true"]',
    );
    if (selectedFeedback) state.__feedback_choice = selectedFeedback.dataset.setFeedback || null;
    return state;
  }

  function restoreStateData() {
    const node = document.getElementById('draft-state');
    if (!node) return;
    let state = {};
    try {
      state = JSON.parse(node.textContent || '{}');
    } catch (_) {
      return;
    }
    restoredUiState = state;
    for (const input of formInputs) {
      if (!input.name || !Object.prototype.hasOwnProperty.call(state, input.name)) continue;
      if (input.type === 'checkbox') input.checked = state[input.name] === true;
      else input.value = String(state[input.name] ?? '');
    }
  }

  async function autosave() {
    if (reviewMode || !player.dataset.autosaveUrl) return;
    if (saving) {
      pendingSave = true;
      return;
    }
    saving = true;
    if (saveStatus) saveStatus.textContent = 'Saving…';
    try {
      const response = await fetch(player.dataset.autosaveUrl, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          expected_version: version,
          snapshot: {
            phase: player.classList.contains('is-resting')
              ? 'REST_TIMER'
              : player.classList.contains('is-set-feedback')
                || player.classList.contains('is-pain-stop')
                ? 'SET_FEEDBACK'
                : 'ACTIVE_SET',
            current_item_kind: stages[stageIndex]?.dataset.kind || null,
            current_sequence: Number(stages[stageIndex]?.dataset.sequence || 0) || null,
            current_set_number: Number(
              stages[stageIndex]?.querySelector('.set-entry.is-current-set')?.dataset.setNumber || 0
            ) || null,
            state_data: collectStateData()
          },
          saved_at: new Date().toISOString()
        })
      });
      if (response.status === 409) {
        const detail = await response.json().catch(() => ({}));
        if (detail?.detail?.code === 'DRAFT_VERSION_CONFLICT') {
          if (saveStatus) saveStatus.textContent = 'Changed elsewhere · reload to continue';
          for (const input of formInputs) input.disabled = true;
          if (completeButton) completeButton.disabled = true;
          return;
        }
      }
      if (!response.ok) throw new Error('AUTOSAVE_FAILED');
      const saved = await response.json();
      version = Number(saved.version);
      player.dataset.draftVersion = String(version);
      if (saveStatus) saveStatus.textContent = 'Saved';
    } catch (_) {
      if (saveStatus) saveStatus.textContent = 'Save failed · draft unchanged';
    } finally {
      saving = false;
      if (pendingSave) {
        pendingSave = false;
        void autosave();
      }
    }
  }

  function queueAutosave() {
    if (reviewMode) return;
    if (saveTimer) window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => void autosave(), 350);
  }

  function strengthPerformance() {
    return [...document.querySelectorAll('.strength-item')].map((item) => {
      const itemId = item.dataset.itemId;
      const targetType = item.dataset.targetType;
      const loadMode = item.dataset.loadMode;
      const loadUnit = item.dataset.loadUnit || null;
      const laterality = item.dataset.laterality;
      const sets = [...item.querySelectorAll('.set-entry')].map((set) => {
        const number = Number(set.dataset.setNumber);
        const prefix = `${itemId}-set-${number}`;
        const load = optionalNumber(valueOf(`${prefix}-load`));
        return {
          set_number: number,
          laterality,
          target_type: targetType,
          load_value: load,
          load_unit: load === null ? null : loadUnit,
          load_mode: loadMode,
          reps: targetType === 'REPS' ? optionalNumber(valueOf(`${prefix}-reps`)) : null,
          duration_seconds: targetType === 'DURATION'
            ? optionalNumber(valueOf(`${prefix}-duration`))
            : null,
          rir: optionalNumber(valueOf(`${prefix}-rir`)),
          rpe: optionalNumber(valueOf(`${prefix}-rpe`)),
          completed: checked(`${prefix}-completed`),
          pain_flag: checked(`${prefix}-pain`)
        };
      });
      return {
        exercise_id: item.dataset.exerciseId,
        completed: sets.length > 0 && sets.every((set) => set.completed),
        sets
      };
    });
  }

  function cardioPerformance() {
    return [...document.querySelectorAll('.cardio-item')].map((item) => {
      const itemId = item.dataset.itemId;
      const equipment = item.dataset.equipment;
      const bike = equipment === 'SPIN_BIKE';
      return {
        equipment,
        duration_seconds: optionalNumber(valueOf(`${itemId}-duration`)) || 0,
        speed_kmh: bike ? null : optionalNumber(valueOf(`${itemId}-speed`)),
        incline_percent: bike ? null : optionalNumber(valueOf(`${itemId}-incline`)),
        cadence_rpm_min: bike ? optionalNumber(valueOf(`${itemId}-cadence-min`)) : null,
        cadence_rpm_max: bike ? optionalNumber(valueOf(`${itemId}-cadence-max`)) : null,
        resistance: bike ? (valueOf(`${itemId}-resistance`)?.value || null) : null,
        rpe: optionalNumber(valueOf(`${itemId}-rpe`)),
        completed: checked(`${itemId}-completed`)
      };
    });
  }

  function completionEvent() {
    const start = new Date(player.dataset.startedAt);
    start.setMilliseconds(0);
    const end = new Date();
    end.setMilliseconds(0);
    const durationSeconds = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000));
    return {
      schema: 'home-workout-assistant.workout-event',
      schema_version: 1,
      event_id: `workout:${player.dataset.draftId}`,
      source_event_id: `draft:${player.dataset.draftId}`,
      start_at: start.toISOString(),
      end_at: end.toISOString(),
      duration_seconds: durationSeconds,
      workout_type: player.dataset.workoutType,
      programme: {
        programme_id: 'home-workout-12m-v1',
        programme_week: Number(player.dataset.programmeWeek),
        programme_day: Number(player.dataset.programmeDay),
        block: player.dataset.workoutBlock
      },
      effort: {session_rpe: optionalNumber(valueOf('session-rpe'))},
      heart_rate_response: {status: 'UNAVAILABLE'},
      training_load: {status: 'UNAVAILABLE'},
      performance: {
        completed: true,
        strength: strengthPerformance(),
        cardio: cardioPerformance()
      },
      provenance: {
        authority: 'HOME_WORKOUT_ASSISTANT',
        source_instance: 'getfit-web',
        recorded_at: end.toISOString()
      }
    };
  }

  function isStageComplete(stage) {
    const completionInputs = [...stage.querySelectorAll('input[name$="-completed"]')];
    return completionInputs.length > 0 && completionInputs.every((input) => input.checked);
  }

  function updateCurrentSet(stage) {
    for (const set of stage.querySelectorAll('.set-entry')) set.classList.remove('is-current-set');
    if (stage.dataset.kind !== 'STRENGTH') return;
    const sets = [...stage.querySelectorAll('.set-entry')];
    const requestedSet = Number(player.dataset.currentSetNumber || 0);
    const requested = requestedSet
      ? sets.find((set) => Number(set.dataset.setNumber) === requestedSet)
      : null;
    const requestedIncomplete = requested
      && !requested.querySelector('input[name$="-completed"]')?.checked
      ? requested
      : null;
    const current = requestedIncomplete
      || sets.find((set) => !set.querySelector('input[name$="-completed"]')?.checked)
      || sets.at(-1);
    current?.classList.add('is-current-set');
    const label = stage.querySelector('[data-current-set-label]');
    if (label && current) label.textContent = current.dataset.setNumber || '1';
  }

  function nextPreviewFor(stage) {
    if (stage.dataset.kind === 'STRENGTH') {
      const sets = [...stage.querySelectorAll('.set-entry')];
      const current = stage.querySelector('.set-entry.is-current-set');
      const currentNumber = Number(current?.dataset.setNumber || 0);
      const nextSet = sets.find(
        (set) => Number(set.dataset.setNumber) > currentNumber
          && !set.querySelector('input[name$="-completed"]')?.checked,
      );
      if (nextSet) {
        return `${stage.dataset.stageTitle} · Set ${nextSet.dataset.setNumber} of ${sets.length}`;
      }
    }
    return stages[stageIndex + 1]?.dataset.stageTitle || 'Workout summary';
  }

  function setActiveStage(index, {scroll = false} = {}) {
    if (!stages.length) return;
    stageIndex = Math.max(0, Math.min(index, stages.length - 1));
    for (const [position, stage] of stages.entries()) {
      stage.hidden = position !== stageIndex;
    }

    const active = stages[stageIndex];
    player.classList.toggle('is-strength-stage', active.dataset.kind === 'STRENGTH');
    player.classList.toggle('is-cardio-stage', active.dataset.kind === 'CARDIO');
    player.classList.toggle('is-last-stage', stageIndex === stages.length - 1);
    updateCurrentSet(active);
    const progress = Math.round(((stageIndex + 1) / stages.length) * 100);
    if (progressBar) progressBar.style.width = `${progress}%`;
    if (progressValue) progressValue.textContent = `${progress}%`;
    if (progressLabel) {
      const strengthCount = stages.filter((stage) => stage.dataset.kind === 'STRENGTH').length;
      const currentStrength = stages
        .slice(0, stageIndex + 1)
        .filter((stage) => stage.dataset.kind === 'STRENGTH').length;
      progressLabel.textContent = active.dataset.kind === 'STRENGTH'
        ? `Exercise ${Math.max(1, currentStrength)} of ${strengthCount}`
        : `Stage ${stageIndex + 1} of ${stages.length}`;
    }
    if (nextStageTitle) nextStageTitle.textContent = nextPreviewFor(active);
    if (previousButton) previousButton.disabled = stageIndex === 0;
    if (nextButton) nextButton.textContent = stageIndex === stages.length - 1 ? 'Review →' : 'Next →';

    const prescribedRest = Number(active.dataset.restSeconds || 0);
    restSeconds = prescribedRest || restSeconds;
    if (restStartButton) restStartButton.dataset.restSeconds = String(prescribedRest);
    if (restLabel && active.dataset.kind === 'STRENGTH') {
      restLabel.textContent = prescribedRest
        ? `Prescribed rest: ${prescribedRest} seconds`
        : 'Use the prescribed recovery before the next set.';
    } else if (restLabel) {
      restLabel.textContent = 'Rest timer is available whenever you need it.';
    }

    if (scroll) active.scrollIntoView({behavior: 'smooth', block: 'start'});
  }

  function clearRestInterval() {
    if (restInterval) window.clearInterval(restInterval);
    restInterval = null;
  }

  function renderRestTimer() {
    for (const display of restDisplays) display.textContent = formatSeconds(restRemaining);
  }

  function addRestTime() {
    restRemaining += 15;
    renderRestTimer();
  }

  function startRestTimer(seconds = null) {
    const requested = seconds === null
      ? Number(restStartButton?.dataset.restSeconds || restSeconds || 60)
      : Number(seconds);
    if (restRemaining <= 0 || seconds !== null) {
      restSeconds = Math.max(0, requested);
      restRemaining = restSeconds;
    }
    clearRestInterval();
    renderRestTimer();
    if (restRemaining <= 0 || paused || reviewMode) return;
    if (restStartButton) restStartButton.textContent = 'Pause';
    restInterval = window.setInterval(() => {
      if (paused) return;
      restRemaining = Math.max(0, restRemaining - 1);
      renderRestTimer();
      if (restRemaining > 0 && restRemaining % 15 === 0) queueAutosave();
      if (restRemaining === 0) {
        queueAutosave();
        clearRestInterval();
        if (restStartButton) restStartButton.textContent = 'Start';
        if (restLabel) restLabel.textContent = 'Rest complete. Start the next set when you are ready.';
      }
    }, 1000);
  }

  function pauseRestTimer() {
    clearRestInterval();
    if (restStartButton) restStartButton.textContent = 'Resume';
  }

  function resetRestTimer() {
    clearRestInterval();
    restSeconds = Number(restStartButton?.dataset.restSeconds || restSeconds || 0);
    restRemaining = restSeconds;
    renderRestTimer();
    if (restStartButton) restStartButton.textContent = 'Start';
  }

  function currentCompletedSet(stage) {
    return [...stage.querySelectorAll('.set-entry')]
      .reverse()
      .find((set) => set.querySelector('input[name$="-completed"]')?.checked) || null;
  }

  function feedbackPanelFor(stage) {
    return stage?.querySelector('[data-set-feedback-panel]') || null;
  }

  function restPanelFor(stage) {
    return stage?.querySelector('[data-main-rest-panel]') || null;
  }

  function painPanelFor(stage) {
    return stage?.querySelector('[data-pain-stop-panel]') || null;
  }

  function showFeedback(stage, set) {
    if (!stage) return;
    feedbackSet = set;
    player.classList.add('is-set-feedback');
    player.classList.remove('is-resting', 'is-pain-stop');
    const feedbackPanel = feedbackPanelFor(stage);
    const mainRestPanel = restPanelFor(stage);
    const painPanel = painPanelFor(stage);
    if (feedbackPanel) feedbackPanel.hidden = false;
    if (mainRestPanel) mainRestPanel.hidden = true;
    if (painPanel) painPanel.hidden = true;
    for (const button of feedbackPanel?.querySelectorAll('[data-set-feedback]') || []) {
      button.setAttribute('aria-pressed', 'false');
    }
    const continueButton = feedbackPanel?.querySelector('[data-feedback-continue]');
    if (continueButton) continueButton.disabled = true;
    const stack = stage.querySelector('.set-stack');
    if (stack) stack.setAttribute('aria-hidden', 'true');
  }

  function showPainStop(stage) {
    if (!stage) return;
    clearRestInterval();
    player.classList.remove('is-set-feedback', 'is-resting');
    player.classList.add('is-pain-stop');
    const feedbackPanel = feedbackPanelFor(stage);
    const mainRestPanel = restPanelFor(stage);
    const painPanel = painPanelFor(stage);
    if (feedbackPanel) feedbackPanel.hidden = true;
    if (mainRestPanel) mainRestPanel.hidden = true;
    if (painPanel) painPanel.hidden = false;
    stage.querySelector('.set-stack')?.setAttribute('aria-hidden', 'true');
    queueAutosave();
  }

  function showRest(stage, remaining = null) {
    if (!stage) return;
    player.classList.remove('is-set-feedback', 'is-pain-stop');
    player.classList.add('is-resting');
    const feedbackPanel = feedbackPanelFor(stage);
    const mainRestPanel = restPanelFor(stage);
    const painPanel = painPanelFor(stage);
    if (feedbackPanel) feedbackPanel.hidden = true;
    if (mainRestPanel) mainRestPanel.hidden = false;
    if (painPanel) painPanel.hidden = true;
    const prescribed = Number(stage.dataset.restSeconds || 90);
    restSeconds = remaining === null
      ? prescribed
      : Number(restoredUiState.__rest_total || prescribed);
    restRemaining = remaining === null
      ? prescribed
      : Math.max(0, Number(remaining) || 0);
    renderRestTimer();
    if (restRemaining > 0) startRestTimer();
    queueAutosave();
  }

  function endRest() {
    clearRestInterval();
    const stage = stages[stageIndex];
    player.classList.remove('is-resting', 'is-set-feedback', 'is-pain-stop');
    const mainRestPanel = restPanelFor(stage);
    const feedbackPanel = feedbackPanelFor(stage);
    const painPanel = painPanelFor(stage);
    if (mainRestPanel) mainRestPanel.hidden = true;
    if (feedbackPanel) feedbackPanel.hidden = true;
    if (painPanel) painPanel.hidden = true;
    stage?.querySelector('.set-stack')?.removeAttribute('aria-hidden');
    if (stage) {
      updateCurrentSet(stage);
      if (nextStageTitle) nextStageTitle.textContent = nextPreviewFor(stage);
    }
  }

  function applyFeedback(choice) {
    const stage = stages[stageIndex];
    const set = feedbackSet || currentCompletedSet(stage);
    if (!set || !stage) return;
    const number = Number(set.dataset.setNumber);
    const itemId = stage.dataset.itemId;
    const prefix = `${itemId}-set-${number}`;
    const rpe = valueOf(`${prefix}-rpe`);
    const rir = valueOf(`${prefix}-rir`);
    const pain = valueOf(`${prefix}-pain`);

    if (choice === 'pain') {
      if (pain) pain.checked = true;
      queueAutosave();
      showPainStop(stage);
      return;
    }

    const estimates = {
      'too-easy': {rpe: '6', rir: '4'},
      'about-right': {rpe: '8', rir: '2'},
      'too-hard': {rpe: '10', rir: '0'},
    };
    const estimate = estimates[choice];
    if (!estimate) return;

    // Quick feedback is an explicit estimate. Manual RPE/RIR always wins.
    const manualEffort = checked(`${prefix}-effort-manual`);
    if (!manualEffort) {
      if (rpe) rpe.value = estimate.rpe;
      if (rir) rir.value = estimate.rir;
    }

    const feedbackPanel = feedbackPanelFor(stage);
    for (const button of feedbackPanel?.querySelectorAll('[data-set-feedback]') || []) {
      const selected = button.dataset.setFeedback === choice;
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      button.classList.toggle('is-selected', selected);
    }
    const continueButton = feedbackPanel?.querySelector('[data-feedback-continue]');
    if (continueButton) continueButton.disabled = false;
    queueAutosave();
  }

  function initCardioTimers() {
    for (const host of document.querySelectorAll('[data-cardio-timer]')) {
      const stage = host.closest('.cardio-item');
      const display = host.querySelector('[data-cardio-display]');
      const start = stage?.querySelector('.cardio-timer-start')
        || host.querySelector('.cardio-timer-start');
      const reset = stage?.querySelector('.cardio-timer-reset')
        || host.querySelector('.cardio-timer-reset');
      const durationInput = stage?.querySelector('input[name$="-duration"]');
      let remaining = Number(durationInput?.value || stage?.dataset.durationTarget || 0);
      let interval = null;

      const render = () => {
        if (display) display.textContent = formatSeconds(remaining);
      };
      const pause = () => {
        if (interval) window.clearInterval(interval);
        interval = null;
        if (start) start.textContent = remaining > 0 ? 'Resume' : 'Start';
      };
      const run = () => {
        if (reviewMode) return;
        if (remaining <= 0) remaining = Number(durationInput?.value || 0);
        if (remaining <= 0 || paused) {
          render();
          return;
        }
        if (interval) window.clearInterval(interval);
        if (start) start.textContent = 'Pause';
        interval = window.setInterval(() => {
          if (paused) return;
          remaining = Math.max(0, remaining - 1);
          render();
          if (remaining === 0) pause();
        }, 1000);
      };
      start?.addEventListener('click', () => {
        if (interval) pause();
        else run();
      });
      reset?.addEventListener('click', () => {
        pause();
        remaining = Number(durationInput?.value || 0);
        render();
      });
      durationInput?.addEventListener('change', () => {
        if (!interval) {
          remaining = Number(durationInput.value || 0);
          render();
        }
      });
      cardioTimers.push({pause});
      render();
    }
  }

  function syncEffortPreset(set) {
    if (!set) return;
    const rpe = set.querySelector('input[name$="-rpe"]')?.value || '';
    for (const button of set.querySelectorAll('[data-effort-preset]')) {
      const selected = rpe !== '' && Number(button.dataset.rpe) === Number(rpe);
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      button.classList.toggle('is-selected', selected);
    }
  }

  function applyEffortPreset(button) {
    const set = button.closest('.set-entry');
    if (!set) return;
    const rpe = set.querySelector('input[name$="-rpe"]');
    const rir = set.querySelector('input[name$="-rir"]');
    const manual = set.querySelector('input[name$="-effort-manual"]');
    if (rpe) rpe.value = button.dataset.rpe || '';
    if (rir) rir.value = button.dataset.rir || '';
    if (manual) manual.checked = true;
    for (const option of set.querySelectorAll('[data-effort-preset]')) {
      const selected = option === button;
      option.setAttribute('aria-pressed', selected ? 'true' : 'false');
      option.classList.toggle('is-selected', selected);
    }
    queueAutosave();
  }

  function initialStageIndex() {
    const requestedKind = player.dataset.currentItemKind;
    const requestedSequence = Number(player.dataset.currentSequence || 0);
    if (requestedKind && requestedSequence) {
      const requested = stages.findIndex(
        (stage) => stage.dataset.kind === requestedKind
          && Number(stage.dataset.sequence) === requestedSequence
      );
      if (requested >= 0) return requested;
    }
    const firstIncomplete = stages.findIndex((stage) => !isStageComplete(stage));
    return firstIncomplete === -1 ? Math.max(0, stages.length - 1) : firstIncomplete;
  }

  async function completeWorkout() {
    if (!completeButton || reviewMode) return;
    completeButton.disabled = true;
    completeButton.setAttribute('aria-busy', 'true');
    if (completionStatus) completionStatus.textContent = 'Saving final workout…';
    await autosave();
    try {
      const response = await fetch(player.dataset.completeUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          idempotency_key: `complete:${player.dataset.draftId}`,
          completed_at: new Date().toISOString(),
          event: completionEvent()
        })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.detail?.code || 'WORKOUT_COMPLETION_FAILED');
      }
      if (completionStatus) completionStatus.textContent = 'Workout completed and saved.';
      window.location.assign(player.dataset.todayUrl || './');
    } catch (error) {
      if (completionStatus) {
        completionStatus.textContent = `Workout not completed: ${error.message}. Your draft remains saved.`;
      }
      completeButton.disabled = false;
      completeButton.removeAttribute('aria-busy');
    }
  }

  restoreStateData();
  for (const set of document.querySelectorAll('.set-entry')) syncEffortPreset(set);
  initCardioTimers();
  setActiveStage(initialStageIndex());

  const restoredStage = stages[stageIndex];
  if (
    restoredUiState.__pain_stop_item
    && restoredUiState.__pain_stop_item === restoredStage?.dataset.itemId
  ) {
    feedbackSet = currentCompletedSet(restoredStage);
    showPainStop(restoredStage);
  } else if (reviewState === 'strength-feedback' || draftPhase === 'SET_FEEDBACK') {
    showFeedback(restoredStage, currentCompletedSet(restoredStage));
    if (restoredUiState.__feedback_choice) {
      applyFeedback(restoredUiState.__feedback_choice);
    }
  } else if (reviewState === 'strength-rest' || draftPhase === 'REST_TIMER') {
    feedbackSet = currentCompletedSet(restoredStage);
    const remaining = Object.prototype.hasOwnProperty.call(restoredUiState, '__rest_remaining')
      ? restoredUiState.__rest_remaining
      : null;
    showRest(restoredStage, remaining);
  }

  for (const input of formInputs) {
    input.addEventListener('input', queueAutosave);
    input.addEventListener('change', () => queueAutosave());
  }

  function stepNumericInput(button) {
    const host = button.closest('.stepper-control');
    const input = host?.querySelector('input[type="number"]');
    if (!input || button.disabled) return;

    const delta = Number(button.dataset.delta || 0);
    const minimum = input.min === '' ? -Infinity : Number(input.min);
    const maximum = input.max === '' ? Infinity : Number(input.max);
    const fallback = Number.isFinite(minimum) ? minimum : 0;
    const current = input.value === '' ? fallback : Number(input.value);
    if (!Number.isFinite(delta) || !Number.isFinite(current)) return;

    const precision = Math.max(
      (String(delta).split('.')[1] || '').length,
      (String(input.step || '').split('.')[1] || '').length,
    );
    const next = Math.min(maximum, Math.max(minimum, current + delta));
    input.value = precision ? next.toFixed(precision).replace(/\.0+$/, '') : String(next);
    input.dispatchEvent(new Event('input', {bubbles: true}));
  }

  for (const button of document.querySelectorAll('[data-stepper], [data-cardio-rpe-step]')) {
    button.addEventListener('click', () => stepNumericInput(button));
  }

  for (const button of document.querySelectorAll('[data-effort-preset]')) {
    button.addEventListener('click', () => applyEffortPreset(button));
  }

  for (const input of document.querySelectorAll('[data-effort-value]')) {
    const markManual = () => {
      const marker = valueOf(input.dataset.effortManualName || '');
      if (marker) marker.checked = true;
    };
    input.addEventListener('input', markManual);
    input.addEventListener('change', markManual);
  }

  for (const button of document.querySelectorAll('[data-complete-set]')) {
    button.addEventListener('click', () => {
      const set = button.closest('.set-entry');
      const stage = button.closest('.strength-item');
      const completed = set?.querySelector('input[name$="-completed"]');
      if (!set || !stage || !completed) return;
      completed.checked = true;
      queueAutosave();
      const preset = set.querySelector('[data-effort-preset][aria-pressed="true"]');
      if (preset) showRest(stage);
      else showFeedback(stage, set);
    });
  }

  for (const button of document.querySelectorAll('[data-set-pain]')) {
    button.addEventListener('click', () => {
      const set = button.closest('.set-entry');
      const stage = button.closest('.strength-item');
      const pain = set?.querySelector('input[name$="-pain"]');
      if (!set || !stage || !pain) return;
      pain.checked = true;
      feedbackSet = set;
      queueAutosave();
      showPainStop(stage);
    });
  }

  for (const button of document.querySelectorAll('[data-set-feedback]')) {
    button.addEventListener('click', () => applyFeedback(button.dataset.setFeedback));
  }
  for (const button of document.querySelectorAll('[data-feedback-continue]')) {
    button.addEventListener('click', () => showRest(stages[stageIndex]));
  }
  for (const input of document.querySelectorAll('.cardio-completion-toggle input[name$="-completed"]')) {
    input.addEventListener('change', () => {
      queueAutosave();
      if (!input.checked || reviewMode) return;
      const stage = input.closest('.cardio-item');
      const completedIndex = stages.indexOf(stage);
      if (completedIndex !== stageIndex) return;
      window.setTimeout(() => {
        if (stageIndex < stages.length - 1) setActiveStage(stageIndex + 1);
        else document.querySelector('.workout-summary-controls')?.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });
      }, 120);
    });
  }

  for (const button of document.querySelectorAll('[data-pain-skip]')) {
    button.addEventListener('click', () => {
      const stage = stages[stageIndex];
      endRest();
      queueAutosave();
      if (stageIndex < stages.length - 1) setActiveStage(stageIndex + 1, {scroll: true});
      else document.querySelector('.workout-summary-controls')?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    });
  }

  previousButton?.addEventListener('click', () => setActiveStage(stageIndex - 1, {scroll: true}));
  nextButton?.addEventListener('click', () => {
    endRest();
    if (stageIndex < stages.length - 1) setActiveStage(stageIndex + 1, {scroll: true});
    else document.querySelector('.workout-summary-controls')?.scrollIntoView({
      behavior: 'smooth',
      block: 'center'
    });
  });
  skipButton?.addEventListener('click', () => {
    endRest();
    if (stageIndex < stages.length - 1) setActiveStage(stageIndex + 1, {scroll: true});
  });
  pauseButton?.addEventListener('click', () => {
    paused = !paused;
    player.classList.toggle('is-paused', paused);
    pauseButton.textContent = paused ? 'Resume' : 'Pause';
    if (paused) {
      pauseRestTimer();
      for (const timer of cardioTimers) timer.pause();
    } else if (restRemaining > 0) {
      startRestTimer();
    }
  });
  async function endWorkout() {
    if (reviewMode) return;
    if (stopButton) stopButton.disabled = true;
    await autosave();
    window.location.assign(player.dataset.todayUrl || './');
  }

  stopButton?.addEventListener('click', () => void endWorkout());
  for (const button of document.querySelectorAll('[data-pain-end]')) {
    button.addEventListener('click', () => void endWorkout());
  }
  restStartButton?.addEventListener('click', () => {
    if (restInterval) pauseRestTimer();
    else startRestTimer();
  });
  restResetButton?.addEventListener('click', resetRestTimer);
  for (const button of document.querySelectorAll('[data-add-rest]')) {
    button.addEventListener('click', addRestTime);
  }
  for (const button of document.querySelectorAll('[data-end-rest]')) {
    button.addEventListener('click', endRest);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void autosave();
  });
  completeButton?.addEventListener('click', () => void completeWorkout());
})();
