(() => {
  const player = document.getElementById('workout-player');
  if (!player) return;

  const saveStatus = document.getElementById('save-status');
  const completionStatus = document.getElementById('completion-status');
  const completeButton = document.getElementById('complete-workout');
  const formInputs = [...document.querySelectorAll('.workout-item input, #session-rpe')];
  let version = Number(player.dataset.draftVersion || '0');
  let saveTimer = null;
  let saving = false;
  let pendingSave = false;

  const valueOf = (name) => document.querySelector(`[name="${name}"]`);
  const optionalNumber = (element) => {
    if (!element || element.value === '') return null;
    const value = Number(element.value);
    return Number.isFinite(value) ? value : null;
  };
  const checked = (name) => Boolean(valueOf(name)?.checked);

  function collectStateData() {
    const state = {};
    for (const input of formInputs) {
      if (!input.name) continue;
      state[input.name] = input.type === 'checkbox' ? input.checked : input.value;
    }
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
    for (const input of formInputs) {
      if (!input.name || !Object.prototype.hasOwnProperty.call(state, input.name)) continue;
      if (input.type === 'checkbox') input.checked = state[input.name] === true;
      else input.value = String(state[input.name] ?? '');
    }
  }

  async function autosave() {
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
            phase: 'ACTIVE_SET',
            state_data: collectStateData()
          },
          saved_at: new Date().toISOString()
        })
      });
      if (response.status === 409) {
        const detail = await response.json().catch(() => ({}));
        if (detail?.detail?.code === 'DRAFT_VERSION_CONFLICT') {
          if (saveStatus) saveStatus.textContent = 'This workout changed elsewhere. Reload before continuing.';
          for (const input of formInputs) input.disabled = true;
          if (completeButton) completeButton.disabled = true;
          return;
        }
      }
      if (!response.ok) throw new Error('AUTOSAVE_FAILED');
      const saved = await response.json();
      version = Number(saved.version);
      player.dataset.draftVersion = String(version);
      if (saveStatus) saveStatus.textContent = `Server saved · version ${version}`;
    } catch (_) {
      if (saveStatus) saveStatus.textContent = 'Save failed. Your last server-saved version is unchanged.';
    } finally {
      saving = false;
      if (pendingSave) {
        pendingSave = false;
        void autosave();
      }
    }
  }

  function queueAutosave() {
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

  async function completeWorkout() {
    if (!completeButton) return;
    completeButton.disabled = true;
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
    }
  }

  restoreStateData();
  for (const input of formInputs) {
    input.addEventListener('input', queueAutosave);
    input.addEventListener('change', queueAutosave);
  }
  completeButton?.addEventListener('click', () => void completeWorkout());
})();
