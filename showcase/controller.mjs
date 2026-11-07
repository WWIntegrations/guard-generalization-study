const clamp = (x, min, max) => Math.max(min, Math.min(max, x));

export function createMotion(reduced = false) {
  let motionMs = 0, motionPaused = reduced, pointerX = 0, pointerY = 0;
  return {
    frame(ms) { if (!reduced) motionMs = Math.max(0, Number.isFinite(ms) ? ms : 0); },
    tick(ms) { if (!motionPaused && !reduced) motionMs += clamp(ms, 0, 1000); },
    pointer(x, y) { if (!motionPaused && !reduced) { pointerX = clamp(x, -1, 1); pointerY = clamp(y, -1, 1); } },
    pause() { motionPaused = true; },
    resume() { if (!reduced) motionPaused = false; },
    setReduced(value) { reduced = Boolean(value); if (reduced) motionPaused = true; },
    snapshot() { return { motionMs, motionPaused, reducedMotion: reduced, pointerX, pointerY }; }
  };
}

export function motionPolicy(state, fallbackReason) {
  if (fallbackReason) return { disabled: true, playing: false, text: 'Static', label: 'Static artwork; decorative motion unavailable' };
  const playing = !state.motionPaused && !state.reducedMotion;
  return { disabled: state.reducedMotion, playing, text: playing ? 'Pause' : 'Play', label: playing ? 'Pause decorative motion' : 'Resume decorative motion' };
}

export function focusVisibleTarget(...candidates) {
  const target = candidates.find(element => element && element.getClientRects().length > 0);
  target?.focus({ preventScroll: true });
  return target ?? null;
}

export function layout(width, height) {
  const mobile = width <= 700;
  return {
    mobile, width, height, header: mobile ? 40 : 60, margin: 20,
    title: { x: 20, y: mobile ? 60 : 76, width: width - 40, height: mobile ? 402 : (width - 40) * 493 / 1400 },
    cta: { x: mobile ? 20 : width - 237, y: height - (mobile ? 80 : 100), width: mobile ? width - 40 : 217, height: mobile ? 60 : 80 },
    ribbon: mobile ? { x: width * .24, y: height * .45, scale: width / 720, rotation: -.61 } : { x: width * .5, y: height * .5, scale: width / 1440, rotation: -.43 }
  };
}

export function displayRate(numerator, denominator) {
  if (!Number.isInteger(numerator) || !Number.isInteger(denominator) || numerator < 0 || denominator < numerator) throw new Error('Invalid rate counts');
  return denominator === 0 ? 'Not available (0/0)' : `${(100 * numerator / denominator).toFixed(2)}% (${numerator}/${denominator})`;
}

export function tileSummary(report, variant) {
  const format = cohort => {
    const summary = selectSummary(report, cohort).variants[variant];
    return {
      fpr: summary.expected === 0 || summary.ok === 0
        ? `Not available (${summary.status}; ${summary.fp}/${summary.ok})`
        : displayRate(summary.fp, summary.ok),
      coverage: `${summary.ok}/${summary.expected} (${summary.status})`
    };
  };
  return { primary: format('audited_eligible_primary'), descriptive: format('raw_unique_descriptive') };
}

export function decodeExact(base64) {
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

export function pairedSelection(id, base, v2) {
  return { base: base.find(row => row.representative_id === id) ?? null, v2: v2.find(row => row.representative_id === id) ?? null };
}

export function selectSummary(report, cohort, dimension = null, value = null) {
  if (!Object.hasOwn(report.cohorts, cohort)) throw new Error('Unknown cohort');
  const selected = report.cohorts[cohort];
  if (dimension === null) return selected;
  if (!Object.hasOwn(selected.groups, dimension) || !Object.hasOwn(selected.groups[dimension], value)) throw new Error('Unknown recorded group');
  return selected.groups[dimension][value];
}

export function selectClusters(dataset, protocol, cohort, dimension = null, value = null) {
  if (!Object.hasOwn(protocol.cohorts, cohort)) throw new Error('Unknown cohort');
  if (dimension !== null && !['partition', 'category'].includes(dimension)) throw new Error('Unknown group dimension');
  const eligible = new Set(protocol.cohorts[cohort].representative_ids);
  return dataset.clusters.filter(cluster => eligible.has(cluster.representative_id) && (dimension === null || cluster[dimension === 'partition' ? 'partitions' : 'categories'].includes(value)));
}
