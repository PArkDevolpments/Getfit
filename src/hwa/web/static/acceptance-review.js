(() => {
  const root = document.querySelector('.acceptance-review');
  const specNode = document.getElementById('acceptance-spec');
  if (!root || !specNode) return;

  const appVersion = root.dataset.appVersion || 'unknown';
  const specVersion = root.dataset.specVersion || 'unknown';
  const storageKey = root.dataset.storageKey || `getfit-acceptance:${appVersion}:${specVersion}`;
  const spec = JSON.parse(specNode.textContent || '{}');
  const validStatuses = new Set(['NOT_TESTED', 'PASS', 'FAIL', 'BLOCKED']);

  function emptyState() {
    return {
      format: 'getfit-acceptance-results-v1',
      app_version: appVersion,
      spec_version: specVersion,
      updated_at: null,
      criteria: {},
    };
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return emptyState();
      const parsed = JSON.parse(raw);
      if (parsed.app_version !== appVersion || parsed.spec_version !== specVersion) {
        return emptyState();
      }
      if (!parsed.criteria || typeof parsed.criteria !== 'object') parsed.criteria = {};
      return parsed;
    } catch (_) {
      return emptyState();
    }
  }

  let state = loadState();

  function saveState() {
    state.updated_at = new Date().toISOString();
    localStorage.setItem(storageKey, JSON.stringify(state));
  }

  function criterionRecord(id) {
    const existing = state.criteria[id];
    if (existing && validStatuses.has(existing.status)) return existing;
    return {
      criterion_id: id,
      status: 'NOT_TESTED',
      notes: '',
      updated_at: null,
    };
  }

  function statusClass(status) {
    if (status === 'PASS') return 'acceptance-status--pass';
    if (status === 'FAIL') return 'acceptance-status--fail';
    if (status === 'BLOCKED') return 'acceptance-status--blocked';
    return 'acceptance-status--not-tested';
  }

  function paintStatus(node, status) {
    if (!node) return;
    node.textContent = status.replace('_', ' ');
    node.classList.remove(
      'acceptance-status--not-tested',
      'acceptance-status--pass',
      'acceptance-status--fail',
      'acceptance-status--blocked',
    );
    node.classList.add(statusClass(status));
  }

  function gateStatus(gateNode) {
    const criteria = Array.from(
      gateNode.querySelectorAll('.acceptance-criterion[data-mandatory="true"]'),
    );
    const records = criteria.map((node) => criterionRecord(node.dataset.criterionId));
    if (records.some((record) => record.status === 'FAIL')) return 'FAIL';
    if (records.some((record) => record.status === 'BLOCKED')) return 'BLOCKED';
    if (records.length && records.every((record) => record.status === 'PASS')) return 'PASS';
    return 'NOT_TESTED';
  }

  function render() {
    let totalMandatory = 0;
    let passed = 0;
    let failed = 0;
    let blocked = 0;

    document.querySelectorAll('.acceptance-criterion').forEach((criterion) => {
      const id = criterion.dataset.criterionId;
      const record = criterionRecord(id);
      paintStatus(criterion.querySelector('[data-criterion-status]'), record.status);

      criterion.querySelectorAll('[data-decision]').forEach((button) => {
        button.classList.toggle('is-selected', button.dataset.decision === record.status);
      });

      const notes = criterion.querySelector('[data-criterion-notes]');
      if (notes && notes.value !== record.notes) notes.value = record.notes || '';

      const updated = criterion.querySelector('[data-criterion-updated]');
      if (updated) {
        updated.textContent = record.updated_at
          ? `Last reviewed ${new Date(record.updated_at).toLocaleString()}`
          : 'Not yet reviewed';
      }

      if (criterion.dataset.mandatory === 'true') {
        totalMandatory += 1;
        if (record.status === 'PASS') passed += 1;
        if (record.status === 'FAIL') failed += 1;
        if (record.status === 'BLOCKED') blocked += 1;
      }
    });

    const gateStatuses = [];
    document.querySelectorAll('.acceptance-gate').forEach((gate) => {
      const gateId = gate.dataset.gateId;
      const status = gateStatus(gate);
      gateStatuses.push(status);
      paintStatus(document.querySelector(`[data-gate-status="${gateId}"]`), status);

      const mandatory = Array.from(
        gate.querySelectorAll('.acceptance-criterion[data-mandatory="true"]'),
      );
      const gatePassed = mandatory.filter(
        (node) => criterionRecord(node.dataset.criterionId).status === 'PASS',
      ).length;
      const progress = document.querySelector(`[data-gate-progress="${gateId}"]`);
      if (progress) progress.textContent = `${gatePassed} / ${mandatory.length} mandatory passed`;

      const navStatus = document.querySelector(`[data-gate-nav-status="${gateId}"]`);
      if (navStatus) navStatus.textContent = status.replace('_', ' ');
    });

    let overall = 'NOT_TESTED';
    if (gateStatuses.some((status) => status === 'FAIL')) overall = 'FAIL';
    else if (gateStatuses.some((status) => status === 'BLOCKED')) overall = 'BLOCKED';
    else if (gateStatuses.length && gateStatuses.every((status) => status === 'PASS')) overall = 'PASS';

    paintStatus(document.getElementById('overall-status'), overall);
    const passedCount = document.getElementById('passed-count');
    const failedCount = document.getElementById('failed-count');
    const blockedCount = document.getElementById('blocked-count');
    if (passedCount) passedCount.textContent = `${passed} / ${totalMandatory}`;
    if (failedCount) failedCount.textContent = String(failed);
    if (blockedCount) blockedCount.textContent = String(blocked);
  }

  document.querySelectorAll('.acceptance-criterion').forEach((criterion) => {
    const criterionId = criterion.dataset.criterionId;

    criterion.querySelectorAll('[data-decision]').forEach((button) => {
      button.addEventListener('click', () => {
        const status = button.dataset.decision;
        if (!validStatuses.has(status)) return;
        const current = criterionRecord(criterionId);
        state.criteria[criterionId] = {
          ...current,
          criterion_id: criterionId,
          status,
          updated_at: new Date().toISOString(),
        };
        saveState();
        render();
      });
    });

    const notes = criterion.querySelector('[data-criterion-notes]');
    notes?.addEventListener('change', () => {
      const current = criterionRecord(criterionId);
      state.criteria[criterionId] = {
        ...current,
        criterion_id: criterionId,
        notes: notes.value.trim(),
        updated_at: new Date().toISOString(),
      };
      saveState();
      render();
    });
  });

  document.getElementById('download-acceptance')?.addEventListener('click', () => {
    saveState();
    const payload = {
      specification: spec,
      results: state,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `getfit-acceptance-${appVersion}-${specVersion}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
  });

  document.getElementById('reset-acceptance')?.addEventListener('click', () => {
    if (!window.confirm('Reset every PASS / FAIL / BLOCKED decision for this app/spec version?')) return;
    localStorage.removeItem(storageKey);
    state = emptyState();
    render();
  });

  render();
})();
