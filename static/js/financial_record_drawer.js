(function () {
  const layer = document.querySelector('[data-record-layer]');
  if (!layer) return;
  const panel = layer.querySelector('[data-record-panel]');
  const content = layer.querySelector('[data-record-content]');
  const baseEndpoint = layer.dataset.endpoint;
  let opener = null; let controller = null;
  const selector = 'a[href],button:not([disabled]),summary,[tabindex]:not([tabindex="-1"])';

  function recordFromUrl(url) {
    const params = new URL(url, location.href).searchParams;
    for (const kind of ['invoice', 'payment', 'refund', 'credit']) if (params.get(kind)) return {kind: kind, id: params.get(kind)};
    return null;
  }
  function endpoint(record) { return baseEndpoint.replace('__type__', record.kind).replace('/0/', '/' + encodeURIComponent(record.id) + '/'); }
  function setUrl(record) {
    const url = new URL(location.href); ['invoice', 'payment', 'refund', 'credit'].forEach(function (key) { url.searchParams.delete(key); });
    if (record) url.searchParams.set(record.kind, record.id); history.pushState({financialRecord: record}, '', url);
  }
  function state(title, message, icon, retry) {
    content.innerHTML = '<div class="lpw-record-state" role="status"><i class="bi ' + icon + '"></i><h2 id="financial-record-title">' + title + '</h2><p>' + message + '</p>' + (retry ? '<button class="lpw-btn" type="button" data-record-retry>Try again</button>' : '') + '<button class="lpw-record-drawer__close" type="button" data-record-close aria-label="Close record details"><i class="bi bi-x-lg"></i></button></div>';
  }
  function close(updateUrl) {
    if (controller) controller.abort(); layer.hidden = true; document.body.classList.remove('lpw-record-open');
    if (updateUrl !== false) setUrl(null); if (opener && document.contains(opener)) opener.focus();
  }
  function load(record, updateUrl) {
    if (!record || !/^\d+$/.test(record.id)) return;
    if (controller) controller.abort(); controller = new AbortController(); layer.hidden = false; document.body.classList.add('lpw-record-open');
    state('Loading record', 'Loading secure financial details…', 'bi-arrow-repeat', false); panel.focus(); if (updateUrl !== false) setUrl(record);
    fetch(endpoint(record), {credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}, signal: controller.signal})
      .then(function (response) { return response.json().then(function (data) { if (!response.ok) throw {status: response.status, data: data}; return data; }); })
      .then(function (data) { content.innerHTML = data.html; panel.focus(); })
      .catch(function (error) { if (error.name === 'AbortError') return; if (error.status === 403) state('Access restricted', 'You do not have permission to view this financial record.', 'bi-shield-lock', false); else if (error.status === 404) state('Record not found', 'This record may have been removed or belongs to another studio.', 'bi-file-earmark-x', false); else state('Details could not be loaded', 'Check your connection and try again.', 'bi-exclamation-circle', true); });
  }
  document.addEventListener('click', function (event) {
    const closeButton = event.target.closest('[data-record-close]'); if (closeButton) { close(); return; }
    const retry = event.target.closest('[data-record-retry]'); if (retry) { const record = recordFromUrl(location.href); if (record) load(record, false); return; }
    const link = event.target.closest('a'); const row = event.target.closest('[data-row-url]'); const url = link ? link.href : row && row.dataset.rowUrl; const record = url && recordFromUrl(url);
    if (record && (link?.closest('.lpw-transactions-workspace') || row || link?.matches('[data-related-record]'))) { event.preventDefault(); opener = link || row; load(record, true); }
  });
  document.addEventListener('keydown', function (event) {
    if (layer.hidden) return; if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    if (event.key !== 'Tab') return; const focusable = Array.from(panel.querySelectorAll(selector)); if (!focusable.length) { event.preventDefault(); panel.focus(); return; }
    const first = focusable[0], last = focusable[focusable.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  layer.addEventListener('click', function (event) { if (event.target === layer) close(); });
  window.addEventListener('popstate', function () { const record = recordFromUrl(location.href); if (record) load(record, false); else close(false); });
  const direct = recordFromUrl(location.href); if (direct) load(direct, false);
}());
