/* Purchase Intelligence — front-end behaviour (vanilla JS, no dependencies). */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const root = document.documentElement;
  const live = $('#live-region');
  const announce = (text) => { if (live) { live.textContent = ''; setTimeout(() => { live.textContent = text; }, 30); } };

  /* ------------------------------------------------------------------ toasts */
  const ICONS = { error: '#i-alert', success: '#i-check', info: '#i-alert' };
  const toastHost = $('#toasts');

  function toast(message, tone = 'info', timeout = 5500) {
    if (!toastHost) return;
    while (toastHost.children.length >= 3) toastHost.firstElementChild.remove();
    const el = document.createElement('div');
    el.className = 'toast';
    el.dataset.tone = tone;
    el.setAttribute('role', tone === 'error' ? 'alert' : 'status');
    el.innerHTML = `<svg aria-hidden="true"><use href="${ICONS[tone] || ICONS.info}"/></svg><p></p>` +
      '<button type="button" aria-label="Dismiss notification"><svg aria-hidden="true"><use href="#i-x"/></svg></button>';
    $('p', el).textContent = message;
    const close = () => {
      if (!el.isConnected) return;
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), 200);
    };
    $('button', el).addEventListener('click', close);
    toastHost.append(el);
    if (timeout) setTimeout(close, timeout);
  }

  /* ------------------------------------------------------------------- theme */
  const themeBtn = $('#theme-toggle');
  function applyTheme(theme, persist) {
    root.setAttribute('data-theme', theme);
    if (themeBtn) {
      themeBtn.setAttribute('aria-pressed', String(theme === 'dark'));
      themeBtn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    }
    if (persist) { try { localStorage.setItem('pi-theme', theme); } catch (e) { /* storage unavailable */ } }
  }
  applyTheme(root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light', false);
  if (themeBtn) themeBtn.addEventListener('click', () => applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true));

  /* ------------------------------------------------------------- API health */
  const statusBtn = $('#api-status');
  const statusLabel = $('#api-status-label');
  let lastStatus = null;

  function setStatus(state) {
    if (!statusBtn) return;
    statusBtn.dataset.state = state;
    const text = { checking: 'checking', online: 'online', offline: 'offline' }[state];
    statusLabel.textContent = text;
    statusBtn.setAttribute('aria-label', `Model API ${text}. Activate to check again.`);
    if (state !== 'checking' && lastStatus && lastStatus !== state) announce(`Model API is ${text}.`);
    if (state !== 'checking') lastStatus = state;
  }

  async function checkHealth() {
    setStatus('checking');
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const res = await fetch('/api/health', { cache: 'no-store', signal: ctrl.signal, headers: { Accept: 'application/json' } });
      let body = null;
      try { body = await res.json(); } catch (e) { /* not JSON */ }
      setStatus(res.ok && body && body.status === 'healthy' ? 'online' : 'offline');
    } catch (e) {
      setStatus('offline');
    } finally {
      clearTimeout(timer);
    }
  }
  if (statusBtn) {
    statusBtn.addEventListener('click', checkHealth);
    checkHealth();
    setInterval(() => { if (!document.hidden) checkHealth(); }, 30000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) checkHealth(); });
  }

  /* -------------------------------------------------------------- formatting */
  const fmtInt = (n) => Math.round(n).toLocaleString('en-US');
  function fmtTime(seconds) {
    const s = Math.round(seconds);
    if (s < 60) return `${s} s`;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
    if (h) return `${h} h ${m} min`;
    return r ? `${m} min ${r} s` : `${m} min`;
  }

  /* -------------------------------------------------------------------- form */
  const form = $('#predict-form');
  if (!form) return finishInit();

  const controls = $$('input[name], select[name]', form);
  const byName = Object.fromEntries(controls.map((el) => [el.name, el]));
  let presets = [];
  try { presets = JSON.parse($('#presets-data').textContent); } catch (e) { presets = []; }

  const resultCard = $('#result');
  const predictBtn = $('#predict-btn');
  const btnLabel = $('.btn-label', predictBtn);
  const btnLabelDefault = btnLabel.textContent;
  const banner = $('#form-banner');
  const bannerText = $('#form-banner-text');
  let busy = false;

  /* --- field helpers */
  const fieldOf = (el) => el.closest('.field');
  const errorOf = (el) => $(`#err-${el.name}`);

  function setError(el, message) {
    const field = fieldOf(el), err = errorOf(el);
    field.classList.toggle('has-error', Boolean(message));
    if (message) el.setAttribute('aria-invalid', 'true'); else el.removeAttribute('aria-invalid');
    if (err) { err.textContent = message || ''; err.hidden = !message; }
  }

  function validateField(el) {
    const kind = el.dataset.kind;
    if (kind === 'bool') return '';
    if (kind === 'choice') return el.value ? '' : 'Select an option.';
    if (el.validity && el.validity.badInput) return 'Enter a number.';
    const raw = el.value.trim();
    if (raw === '') return 'This field is required.';
    const n = Number(raw);
    if (!Number.isFinite(n)) return 'Enter a number.';
    if (kind === 'int' && !Number.isInteger(n)) return 'Use a whole number.';
    if (el.min !== '' && n < Number(el.min)) return `Must be at least ${Number(el.min)}.`;
    const max = el.dataset.hardMax !== undefined ? Number(el.dataset.hardMax) : (el.max !== '' ? Number(el.max) : Infinity);
    if (n > max) return `Must be at most ${fmtInt(max)}.`;
    return '';
  }

  function validateAll() {
    const bad = [];
    controls.forEach((el) => {
      const message = validateField(el);
      setError(el, message);
      if (message) bad.push(el);
    });
    return bad;
  }

  function readValue(el) {
    switch (el.dataset.kind) {
      case 'bool': return el.checked;
      case 'choice': return el.dataset.numeric === 'true' ? Number(el.value) : el.value;
      default: return Number(el.value);
    }
  }
  const buildPayload = () => Object.fromEntries(controls.map((el) => [el.name, readValue(el)]));
  const numeric = (name) => { const v = Number(byName[name] && byName[name].value); return Number.isFinite(v) && v > 0 ? v : 0; };

  function showBanner(message) {
    bannerText.textContent = message;
    banner.hidden = false;
  }
  const hideBanner = () => { banner.hidden = true; };

  /* --- sliders */
  function syncRange(el) {
    const min = Number(el.min), max = Number(el.max), v = Number(el.value);
    el.style.setProperty('--fill', `${((v - min) / (max - min)) * 100}%`);
    const out = $('.readout', fieldOf(el));
    if (out) out.textContent = el.dataset.kind === 'rate' ? `${(v * 100).toFixed(1)}%` : v.toFixed(1);
  }
  $$('input[type="range"]', form).forEach(syncRange);

  /* --- live session mix */
  const TYPES = [
    { label: 'Administrative', count: 'Administrative', time: 'Administrative_Duration', color: 'var(--c-admin)' },
    { label: 'Informational', count: 'Informational', time: 'Informational_Duration', color: 'var(--c-info)' },
    { label: 'Product related', count: 'ProductRelated', time: 'ProductRelated_Duration', color: 'var(--c-prod)' },
  ];
  const stacks = {
    pages: { bar: $('#stack-pages'), legend: $('#legend-pages'), fmt: fmtInt, key: 'count', noun: 'pages' },
    time: { bar: $('#stack-time'), legend: $('#legend-time'), fmt: fmtTime, key: 'time', noun: 'time' },
  };
  Object.values(stacks).forEach((s) => {
    s.segs = TYPES.map((t) => {
      const seg = document.createElement('span');
      seg.style.setProperty('--seg', t.color);
      s.bar.append(seg);
      const li = document.createElement('li');
      const sw = document.createElement('span');
      sw.className = 'swatch';
      sw.style.background = t.color;
      const txt = document.createElement('span');
      li.append(sw, txt);
      s.legend.append(li);
      return { seg, txt, label: t.label };
    });
  });

  function renderTrace() {
    let anyActivity = false;
    Object.values(stacks).forEach((s) => {
      const values = TYPES.map((t) => numeric(t[s.key]));
      const total = values.reduce((a, b) => a + b, 0);
      anyActivity = anyActivity || total > 0;
      s.segs.forEach((item, i) => {
        item.seg.style.setProperty('--w', total ? `${(values[i] / total) * 100}%` : '0%');
        item.txt.textContent = `${item.label} ${s.fmt(values[i])}`;
      });
      s.bar.setAttribute('aria-label', TYPES.map((t, i) => `${t.label} ${s.fmt(values[i])}`).join(', '));
    });
    $('#trace-empty').hidden = anyActivity;
  }

  /* --- presets */
  function applyValues(values) {
    controls.forEach((el) => {
      if (!(el.name in values)) return;
      if (el.dataset.kind === 'bool') el.checked = Boolean(values[el.name]);
      else el.value = values[el.name];
      if (el.type === 'range') syncRange(el);
      setError(el, '');
    });
    renderTrace();
  }
  const chips = $$('[data-preset]');
  const clearChips = () => chips.forEach((c) => c.classList.remove('is-active'));

  chips.forEach((chip) => chip.addEventListener('click', () => {
    const preset = presets.find((p) => p.id === chip.dataset.preset);
    if (!preset) return;
    applyValues(preset.values);
    hideBanner();
    clearChips();
    chip.classList.add('is-active');
    showView('idle');
    toast(`Loaded "${preset.label}". Adjust anything, then predict.`, 'info', 3200);
  }));

  $('#reset-btn').addEventListener('click', () => {
    const typical = presets.find((p) => p.id === 'typical');
    if (typical) applyValues(typical.values);
    hideBanner();
    clearChips();
    showView('idle');
  });

  /* --- input events */
  form.addEventListener('input', (e) => {
    const el = e.target;
    if (!(el instanceof HTMLElement) || !el.name) return;
    if (el.type === 'range') syncRange(el);
    if (fieldOf(el) && fieldOf(el).classList.contains('has-error')) setError(el, validateField(el));
    clearChips();
    renderTrace();
  });
  form.addEventListener('focusout', (e) => {
    const el = e.target;
    if (el instanceof HTMLElement && el.name && el.dataset.kind && el.dataset.kind !== 'bool') setError(el, validateField(el));
  });

  /* --- result views */
  function showView(name) {
    $$('[data-view]', resultCard).forEach((v) => { v.hidden = v.dataset.view !== name; });
    resultCard.dataset.state = name;
    resultCard.setAttribute('aria-busy', String(name === 'loading'));
  }

  let stepTimers = [];
  function startSteps() {
    const items = $$('#loading-steps li');
    stepTimers.forEach(clearTimeout);
    stepTimers = [];
    items.forEach((li) => li.classList.remove('is-active', 'is-done'));
    items.forEach((li, i) => {
      stepTimers.push(setTimeout(() => {
        if (i > 0) items[i - 1].classList.replace('is-active', 'is-done');
        li.classList.add('is-active');
      }, i * 260));
    });
  }
  function finishSteps() {
    stepTimers.forEach(clearTimeout);
    $$('#loading-steps li').forEach((li) => { li.classList.remove('is-active'); li.classList.add('is-done'); });
  }

  function setBusy(state) {
    busy = state;
    predictBtn.disabled = state;
    predictBtn.classList.toggle('is-loading', state);
    btnLabel.textContent = state ? 'Analyzing session' : btnLabelDefault;
  }

  function countUp(el, target, ms) {
    if (reduceMotion) { el.textContent = `${target.toFixed(1)}%`; return; }
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = `${(target * eased).toFixed(1)}%`;
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function metric(label, value) {
    const wrap = document.createElement('div');
    const dt = document.createElement('dt'); dt.textContent = label;
    const dd = document.createElement('dd'); dd.textContent = value;
    wrap.append(dt, dd);
    return wrap;
  }

  function renderResult(data, payload) {
    const likely = data.prediction === true;
    const label = typeof data.label === 'string' && data.label ? data.label : (likely ? 'Purchase likely' : 'Purchase unlikely');
    const prob = typeof data.probability === 'number' && Number.isFinite(data.probability) && data.probability >= 0 && data.probability <= 1 ? data.probability : null;
    const threshold = typeof data.threshold === 'number' && Number.isFinite(data.threshold) ? data.threshold : null;

    resultCard.dataset.tone = likely ? 'likely' : 'unlikely';
    $('#verdict').dataset.tone = likely ? 'likely' : 'unlikely';
    $('#verdict-label').textContent = label;

    const probBlock = $('#prob-block');
    probBlock.hidden = prob === null;   // never show a score the API did not return
    const note = $('#verdict-note');
    if (prob !== null) {
      const pct = prob * 100;
      note.textContent = threshold !== null
        ? `The model scores this session at ${pct.toFixed(0)}%, ${likely ? 'above' : 'at or below'} the ${Math.round(threshold * 100)}% decision threshold.`
        : `The model scores this session at ${pct.toFixed(0)}%.`;
      const meter = $('#meter'), fill = $('#meter-fill'), marker = $('.meter-threshold', meter);
      meter.setAttribute('aria-valuenow', pct.toFixed(1));
      marker.hidden = threshold === null;
      if (threshold !== null) marker.style.left = `${threshold * 100}%`;
      const scaleMid = $('.meter-scale span:nth-child(2)', probBlock);
      scaleMid.hidden = threshold === null;
      if (threshold !== null) scaleMid.textContent = `${Math.round(threshold * 100)}% threshold`;
      fill.style.width = '0%';
      requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = `${pct}%`; }));
      countUp($('#prob-value'), pct, 900);
    } else {
      note.textContent = 'The model classified this session, but did not return a probability.';
    }

    const warnings = Array.isArray(data.warnings) ? data.warnings.filter((w) => typeof w === 'string' && w) : [];
    const warnList = $('#result-warnings');
    warnList.replaceChildren(...warnings.map((w) => { const li = document.createElement('li'); li.textContent = w; return li; }));
    warnList.hidden = warnings.length === 0;

    const pages = payload.Administrative + payload.Informational + payload.ProductRelated;
    const seconds = payload.Administrative_Duration + payload.Informational_Duration + payload.ProductRelated_Duration;
    const metrics = $('#result-metrics');
    metrics.replaceChildren(
      metric('Pages viewed', fmtInt(pages)),
      metric('Time on site', fmtTime(seconds)),
      metric('Time per product page', payload.ProductRelated > 0 ? fmtTime(payload.ProductRelated_Duration / payload.ProductRelated) : 'None viewed'),
      metric('Page value', payload.PageValues.toFixed(2)),
      metric('Bounce rate', `${(payload.BounceRates * 100).toFixed(1)}%`),
      metric('Exit rate', `${(payload.ExitRates * 100).toFixed(1)}%`),
    );

    $('#payload-json').textContent = JSON.stringify({ request: payload, response: data }, null, 2);
    showView('result');
    announce(prob !== null ? `${label}. Purchase probability ${(prob * 100).toFixed(0)} percent.` : `${label}.`);
  }

  function showFailure(title, text) {
    $('#error-title').textContent = title;
    $('#error-text').textContent = text;
    showView('error');
    announce(`${title}. ${text}`);
  }

  function revealResult() {
    if (window.matchMedia('(max-width: 1023px)').matches) {
      resultCard.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    }
    resultCard.focus({ preventScroll: true });
  }

  /* --- submit */
  async function runPrediction(payload) {
    setBusy(true);
    showView('loading');
    startSteps();
    if (window.matchMedia('(max-width: 1023px)').matches) resultCard.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' });

    const started = performance.now();
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 15000);
    let outcome;
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      let data = null;
      try { data = await res.json(); } catch (e) { /* non-JSON body */ }
      outcome = { res, data };
    } catch (err) {
      outcome = { error: err };
    } finally {
      clearTimeout(timeout);
    }

    // Keep the loading state visible long enough to read; it is not a fake delay on the model itself.
    if (!reduceMotion) await sleep(Math.max(0, 750 - (performance.now() - started)));
    finishSteps();
    setBusy(false);

    if (outcome.error) {
      const timedOut = outcome.error && outcome.error.name === 'AbortError';
      showFailure(timedOut ? 'The request timed out' : "Couldn't reach the server",
        timedOut ? 'The model took too long to respond. Try again in a moment.' : 'Check your connection and try again.');
      toast(timedOut ? 'The request timed out.' : 'Network error. Could not reach the model API.', 'error');
      checkHealth();
      revealResult();
      return;
    }

    const { res, data } = outcome;
    if (!res.ok || !data || data.success !== true) {
      const serverErrors = data && data.errors && typeof data.errors === 'object' ? data.errors : null;
      if (serverErrors) {
        let first = null;
        Object.entries(serverErrors).forEach(([name, message]) => {
          if (byName[name]) { setError(byName[name], String(message)); first = first || byName[name]; }
        });
        showBanner('Some values need attention before we can predict.');
        showView('idle');
        if (first) first.focus();
        toast('Please fix the highlighted fields.', 'error');
        return;
      }
      const message = (data && data.error) || `The server responded with an error (${res.status}).`;
      showFailure("Couldn't get a prediction", message);
      toast(message, 'error');
      if (res.status >= 500) checkHealth();
      revealResult();
      return;
    }

    if (typeof data.prediction !== 'boolean') {
      showFailure('No prediction returned', 'The model responded without a prediction. Please try again.');
      toast('The server response was missing a prediction.', 'error');
      revealResult();
      return;
    }

    renderResult(data, payload);
    revealResult();
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (busy) return;
    const invalid = validateAll();
    if (invalid.length) {
      showBanner(invalid.length === 1 ? 'One value needs attention.' : `${invalid.length} values need attention.`);
      invalid[0].focus();
      toast('Please fix the highlighted fields.', 'error');
      return;
    }
    hideBanner();
    runPrediction(buildPayload());
  });

  $('#retry-btn').addEventListener('click', () => form.requestSubmit());

  $('#copy-payload').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('#payload-json').textContent);
      toast('Copied to clipboard.', 'success', 2500);
    } catch (e) {
      toast('Copy is not available in this browser.', 'error', 3500);
    }
  });

  renderTrace();
  finishInit();

  /* -------------------------------------------------------------- shared init */
  function finishInit() {
    // Reveal the model section as it scrolls into view. Without JS or IntersectionObserver it is simply visible.
    const items = $$('.reveal');
    if (!('IntersectionObserver' in window) || reduceMotion) { items.forEach((el) => el.classList.add('is-visible')); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); io.unobserve(entry.target); } });
    }, { threshold: 0.12 });
    items.forEach((el) => io.observe(el));
  }
})();
