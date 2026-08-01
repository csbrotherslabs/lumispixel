(function () {
  const sidebar = document.querySelector('[data-workspace-sidebar]');
  const openButton = document.querySelector('[data-workspace-open]');
  const closeButton = document.querySelector('[data-workspace-close]');
  const collapseButton = document.querySelector('[data-workspace-collapse]');
  const scrim = document.querySelector('[data-workspace-scrim]');

  if (sidebar) sidebar.id = 'workspace-sidebar';

  function openDrawer() {
    sidebar.classList.add('is-open');
    scrim.hidden = false;
    closeButton.focus();
  }

  function setCollapsed(collapsed) {
    sidebar.classList.toggle('is-collapsed', collapsed);
    if (collapseButton) {
      collapseButton.setAttribute('aria-expanded', String(!collapsed));
      collapseButton.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
    }
    window.localStorage.setItem('lpw-sidebar-collapsed', String(collapsed));
  }

  function closeDrawer(restoreFocus) {
    sidebar.classList.remove('is-open');
    scrim.hidden = true;
    if (restoreFocus) openButton.focus();
  }

  if (sidebar && openButton && closeButton && scrim) {
    openButton.addEventListener('click', function () {
      if (window.matchMedia('(max-width: 860px)').matches) openDrawer();
      else setCollapsed(!sidebar.classList.contains('is-collapsed'));
    });
    closeButton.addEventListener('click', function () { closeDrawer(true); });
    scrim.addEventListener('click', function () { closeDrawer(true); });
  }

  if (sidebar && collapseButton) {
    const collapsed = window.localStorage.getItem('lpw-sidebar-collapsed') === 'true';
    setCollapsed(collapsed);
    collapseButton.addEventListener('click', function () {
      const next = !sidebar.classList.contains('is-collapsed');
      setCollapsed(next);
    });
  }

  const searchForm = document.querySelector('[data-workspace-search]');
  const searchInput = document.querySelector('[data-workspace-search-input]');
  if (searchForm && searchInput) {
    searchForm.addEventListener('submit', function (event) {
      event.preventDefault();
      const query = searchInput.value.trim().toLowerCase();
      if (!query) return;
      const match = Array.from(document.querySelectorAll('.lpw-nav a')).find(function (link) {
        return link.textContent.trim().toLowerCase().includes(query);
      });
      if (match) window.location.assign(match.href);
    });
    document.addEventListener('keydown', function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchInput.focus();
      }
    });
  }

  document.querySelectorAll('[data-nav-group-toggle]').forEach(function (toggle) {
    toggle.addEventListener('click', function () {
      const items = document.getElementById(toggle.getAttribute('aria-controls'));
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      const compactDesktop = sidebar.classList.contains('is-collapsed') && !window.matchMedia('(max-width: 860px)').matches;
      if (compactDesktop) {
        setCollapsed(false);
        toggle.setAttribute('aria-expanded', 'true');
        items.hidden = false;
      } else {
        toggle.setAttribute('aria-expanded', String(!expanded));
        items.hidden = expanded;
      }
    });
  });

  const profileMenu = document.querySelector('[data-profile-menu]');

  const bookingSearch = document.querySelector('[data-booking-search]');
  const bookingFilter = document.querySelector('[data-booking-filter]');
  const bookingRows = Array.from(document.querySelectorAll('[data-booking-row]'));
  const bookingFilterEmpty = document.querySelector('[data-booking-filter-empty]');
  function filterBookings() {
    const query = bookingSearch ? bookingSearch.value.trim().toLowerCase() : '';
    const status = bookingFilter ? bookingFilter.value : '';
    let visible = 0;
    bookingRows.forEach(function (row) {
      const show = (!query || row.textContent.toLowerCase().includes(query)) && (!status || row.dataset.status === status);
      row.hidden = !show;
      if (show) visible += 1;
    });
    if (bookingFilterEmpty) bookingFilterEmpty.hidden = visible !== 0;
  }
  if (bookingSearch) bookingSearch.addEventListener('input', filterBookings);
  if (bookingFilter) bookingFilter.addEventListener('change', filterBookings);
  const profileToggle = document.querySelector('[data-profile-toggle]');
  const profileDropdown = document.querySelector('[data-profile-dropdown]');
  function closeProfile() {
    if (!profileToggle || !profileDropdown) return;
    profileToggle.setAttribute('aria-expanded', 'false');
    profileDropdown.hidden = true;
  }
  if (profileMenu && profileToggle && profileDropdown) {
    profileToggle.addEventListener('click', function () {
      const open = profileToggle.getAttribute('aria-expanded') === 'true';
      profileToggle.setAttribute('aria-expanded', String(!open));
      profileDropdown.hidden = open;
    });
    document.addEventListener('click', function (event) {
      if (!profileMenu.contains(event.target)) closeProfile();
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    if (sidebar && sidebar.classList.contains('is-open')) closeDrawer(true);
    closeProfile();
  });

  const viewButtons = document.querySelectorAll('[data-lead-view]');
  const viewPanels = document.querySelectorAll('[data-lead-panel]');
  function setLeadView(view) {
    viewButtons.forEach(function (button) {
      const active = button.dataset.leadView === view;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    viewPanels.forEach(function (panel) { panel.hidden = panel.dataset.leadPanel !== view; });
    window.localStorage.setItem('lpw-lead-view', view);
  }
  if (viewButtons.length) {
    setLeadView(window.localStorage.getItem('lpw-lead-view') || 'board');
    viewButtons.forEach(function (button) { button.addEventListener('click', function () { setLeadView(button.dataset.leadView); }); });
  }

  const filterToggle = document.querySelector('[data-filter-open]');
  const filterDrawer = document.getElementById('lead-filter-drawer');
  if (filterToggle && filterDrawer) {
    filterToggle.addEventListener('click', function () {
      const open = filterToggle.getAttribute('aria-expanded') === 'true';
      filterToggle.setAttribute('aria-expanded', String(!open));
      filterDrawer.classList.toggle('is-open', !open);
      if (!open) filterDrawer.querySelector('input, select').focus();
    });
  }

  const clientViewButtons = document.querySelectorAll('[data-client-view]');
  const clientViewPanels = document.querySelectorAll('[data-client-panel]');
  function setClientView(view) {
    clientViewButtons.forEach(function (button) {
      const active = button.dataset.clientView === view;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    clientViewPanels.forEach(function (panel) { panel.hidden = panel.dataset.clientPanel !== view; });
    window.localStorage.setItem('lpw-client-view', view);
  }
  if (clientViewButtons.length) {
    setClientView(window.localStorage.getItem('lpw-client-view') || 'list');
    clientViewButtons.forEach(function (button) { button.addEventListener('click', function () { setClientView(button.dataset.clientView); }); });
  }

  const clientFilterToggle = document.querySelector('[data-client-filter-open]');
  const clientFilterDrawer = document.getElementById('client-filter-drawer');
  if (clientFilterToggle && clientFilterDrawer) {
    clientFilterToggle.addEventListener('click', function () {
      const open = clientFilterToggle.getAttribute('aria-expanded') === 'true';
      clientFilterToggle.setAttribute('aria-expanded', String(!open));
      clientFilterDrawer.classList.toggle('is-open', !open);
      if (!open) clientFilterDrawer.querySelector('input, select').focus();
    });
  }

  const galleryViewButtons = document.querySelectorAll('[data-gallery-view]');
  const galleryPanels = document.querySelectorAll('[data-gallery-panel]');
  function setGalleryView(view) {
    galleryViewButtons.forEach(function (button) { const active = button.dataset.galleryView === view; button.classList.toggle('is-active', active); button.setAttribute('aria-pressed', String(active)); });
    galleryPanels.forEach(function (panel) { panel.hidden = panel.dataset.galleryPanel !== view; });
    window.localStorage.setItem('lpw-gallery-view', view);
  }
  if (galleryViewButtons.length) {
    setGalleryView(window.localStorage.getItem('lpw-gallery-view') || 'grid');
    galleryViewButtons.forEach(function (button) { button.addEventListener('click', function () { setGalleryView(button.dataset.galleryView); }); });
  }

  const galleryChecks = Array.from(document.querySelectorAll('[data-gallery-check]'));
  const galleryBulkBar = document.querySelector('[data-gallery-bulk-bar]');
  function syncGallerySelection(source) {
    if (source) document.querySelectorAll('[data-gallery-check][value="' + source.value + '"]').forEach(function (box) { box.checked = source.checked; });
    const selected = new Set(galleryChecks.filter(function (box) { return box.checked; }).map(function (box) { return box.value; }));
    if (galleryBulkBar) galleryBulkBar.hidden = selected.size === 0;
    document.querySelectorAll('[data-gallery-count]').forEach(function (count) { count.textContent = selected.size; });
  }
  galleryChecks.forEach(function (box) { box.addEventListener('change', function () { syncGallerySelection(box); }); });
  document.querySelectorAll('[data-gallery-select-all]').forEach(function (all) { all.addEventListener('change', function () { galleryChecks.forEach(function (box) { box.checked = all.checked; }); syncGallerySelection(); }); });
  document.querySelectorAll('[data-single-gallery]').forEach(function (button) { button.addEventListener('click', function () { galleryChecks.forEach(function (box) { box.checked = box.value === button.dataset.singleGallery; }); }); });

  const galleryModal = document.querySelector('[data-gallery-modal]');
  function openGalleryModal(action, id) {
    if (!galleryModal) return;
    galleryModal.querySelector('[data-modal-title]').textContent = action === 'delete' ? 'Delete selected galleries?' : 'Archive selected galleries?';
    galleryModal.querySelector('[data-modal-copy]').textContent = action === 'delete' ? 'This action cannot be undone. Gallery records will be permanently removed.' : 'Archived galleries leave your active workflow, but can be restored later.';
    const submit = galleryModal.querySelector('[data-modal-submit]'); submit.value = action; submit.textContent = action === 'delete' ? 'Delete' : 'Archive'; submit.classList.toggle('lpw-btn-danger', action === 'delete');
    if (id) { galleryChecks.forEach(function (box) { box.checked = box.value === id; }); syncGallerySelection(); }
    galleryModal.showModal();
  }
  document.querySelectorAll('[data-gallery-confirm]').forEach(function (button) { button.addEventListener('click', function () { openGalleryModal(button.dataset.galleryConfirm); }); });
  document.querySelectorAll('[data-card-confirm]').forEach(function (button) { button.addEventListener('click', function () { openGalleryModal(button.dataset.cardConfirm, button.dataset.galleryId); }); });
  const modalCancel = document.querySelector('[data-modal-cancel]'); if (modalCancel) modalCancel.addEventListener('click', function () { galleryModal.close(); });
  document.querySelectorAll('[data-copy-link]').forEach(function (button) { button.addEventListener('click', function () { navigator.clipboard.writeText(new URL(button.dataset.copyLink, window.location.origin).href); button.innerHTML = '<i class="bi bi-check2"></i>Link copied'; }); });

  const coverDrop = document.querySelector('[data-cover-drop]');
  const coverInput = document.querySelector('[data-cover-input]');
  if (coverDrop && coverInput) {
    const preview = coverDrop.querySelector('[data-cover-preview]'); const prompt = coverDrop.querySelector('[data-cover-prompt]');
    function previewCover(file) { if (!file || !file.type.startsWith('image/')) return; preview.src = URL.createObjectURL(file); preview.hidden = false; prompt.hidden = true; }
    coverInput.addEventListener('change', function () { previewCover(coverInput.files[0]); });
    ['dragenter', 'dragover'].forEach(function (name) { coverDrop.addEventListener(name, function (event) { event.preventDefault(); coverDrop.classList.add('is-dragging'); }); });
    ['dragleave', 'drop'].forEach(function (name) { coverDrop.addEventListener(name, function (event) { event.preventDefault(); coverDrop.classList.remove('is-dragging'); }); });
    coverDrop.addEventListener('drop', function (event) { if (event.dataTransfer.files.length) { coverInput.files = event.dataTransfer.files; previewCover(event.dataTransfer.files[0]); } });
  }

  document.querySelectorAll('[data-mutation-form]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (form.dataset.submitting === 'true') { event.preventDefault(); return; }
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) { event.preventDefault(); return; }
      form.dataset.submitting = 'true';
      form.setAttribute('aria-busy', 'true');
      form.querySelectorAll('button[type="submit"]').forEach(function (button) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = 'Saving…';
      });
    });
  });

  let draggedLead = null;
  document.querySelectorAll('[data-lead-id]').forEach(function (card) {
    card.addEventListener('dragstart', function () { draggedLead = card; card.classList.add('is-dragging'); });
    card.addEventListener('dragend', function () { card.classList.remove('is-dragging'); draggedLead = null; });
  });
  document.querySelectorAll('[data-lead-dropzone]').forEach(function (zone) {
    zone.addEventListener('dragover', function (event) { event.preventDefault(); zone.classList.add('is-drag-over'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('is-drag-over'); });
    zone.addEventListener('drop', function (event) {
      event.preventDefault(); zone.classList.remove('is-drag-over');
      if (!draggedLead) return;
      const status = zone.closest('[data-stage]').dataset.stage;
      const select = draggedLead.querySelector('[data-stage-form] select');
      if (select && select.value !== status) { select.value = status; select.form.submit(); }
    });
  });

  const selectAll = document.querySelector('[data-select-all]');
  const leadChecks = Array.from(document.querySelectorAll('[data-lead-check]'));
  const selectedCount = document.querySelector('[data-selected-count]');
  function updateSelectedCount() {
    const count = leadChecks.filter(function (check) { return check.checked; }).length;
    if (selectedCount) selectedCount.textContent = count + ' selected';
    if (selectAll) selectAll.indeterminate = count > 0 && count < leadChecks.length;
  }
  if (selectAll) selectAll.addEventListener('change', function () { leadChecks.forEach(function (check) { check.checked = selectAll.checked; }); updateSelectedCount(); });
  leadChecks.forEach(function (check) { check.addEventListener('change', updateSelectedCount); });

  const clientForm = document.querySelector('[data-crm-form]');
  if (clientForm) {
    const submitButton = clientForm.querySelector('[data-submit-button]');
    clientForm.addEventListener('submit', function () {
      if (submitButton.disabled) return;
      submitButton.disabled = true;
      submitButton.querySelector('span').textContent = 'Saving…';
    });
    const notes = clientForm.querySelector('#id_notes');
    const noteCount = clientForm.querySelector('[data-note-count]');
    function updateCount() { if (notes && noteCount) noteCount.textContent = notes.value.length; }
    if (notes) { notes.addEventListener('input', updateCount); updateCount(); }

    const tagInput = clientForm.querySelector('#id_tags_input');
    const tagList = clientForm.querySelector('[data-tag-list]');
    let tags = tagInput ? tagInput.value.split(',').map(function (tag) { return tag.trim(); }).filter(Boolean) : [];
    function renderTags() {
      if (!tagInput || !tagList) return;
      tagInput.value = '';
      tagList.replaceChildren();
      tags.forEach(function (tag, index) {
        const chip = document.createElement('span'); chip.className = 'tag-chip'; chip.textContent = tag;
        const remove = document.createElement('button'); remove.type = 'button'; remove.setAttribute('aria-label', 'Remove ' + tag); remove.innerHTML = '&times;';
        remove.addEventListener('click', function () { tags.splice(index, 1); renderTags(); }); chip.appendChild(remove); tagList.appendChild(chip);
      });
    }
    if (tagInput) tagInput.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ',') return;
      event.preventDefault(); const value = tagInput.value.trim().replace(/,$/, '');
      if (value && !tags.includes(value) && tags.length < 20) tags.push(value);
      tagInput.value = ''; renderTags();
    });
    renderTags();
    clientForm.addEventListener('formdata', function (event) { event.formData.set('tags_input', tags.join(',')); });

    const dropzone = clientForm.querySelector('[data-upload-dropzone]');
    const photoInput = clientForm.querySelector('[data-photo-input]');
    const preview = clientForm.querySelector('[data-upload-preview]');
    const uploadError = clientForm.querySelector('[data-upload-error]');
    function previewPhoto(file) {
      uploadError.textContent = '';
      if (!file.type.match(/^image\/(jpeg|png|webp)$/)) { uploadError.textContent = 'Choose a JPG, PNG, or WebP image.'; return; }
      if (file.size > 5 * 1024 * 1024) { uploadError.textContent = 'Choose an image smaller than 5 MB.'; return; }
      const image = document.createElement('img'); image.alt = 'Selected profile photo preview'; image.src = URL.createObjectURL(file); preview.replaceChildren(image);
    }
    if (dropzone && photoInput) {
      photoInput.addEventListener('change', function () { if (photoInput.files[0]) previewPhoto(photoInput.files[0]); });
      ['dragenter', 'dragover'].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.add('is-dragging'); }); });
      ['dragleave', 'drop'].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.remove('is-dragging'); }); });
      dropzone.addEventListener('drop', function (event) { if (event.dataTransfer.files[0]) previewPhoto(event.dataTransfer.files[0]); });
      dropzone.addEventListener('keydown', function (event) { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); photoInput.click(); } });
    }
  }
})();

(() => {
  const dialog = document.querySelector('[data-metric-dialog]');
  if (!dialog) return;
  let opener;
  document.querySelectorAll('[data-metric-open]').forEach((button) => button.addEventListener('click', () => {
    opener = button; const card = button.closest('[data-metric-card]');
    ['label', 'definition', 'value', 'previous', 'change'].forEach((key) => { dialog.querySelector(`[data-detail-${key}]`).textContent = card.dataset[key]; });
    dialog.querySelector('[data-detail-contributors]').textContent = card.dataset.contributors || 'No contributing service data is available for this period.';
    const history = card.dataset.history.split(',').map(Number); const chart = dialog.querySelector('[data-detail-history]');
    chart.replaceChildren(...history.map((value) => { const bar = document.createElement('i'); bar.style.height = value + '%'; return bar; }));
    chart.setAttribute('aria-label', `Historical trend for ${card.dataset.label}: ${history.join(', ')} relative index values.`);
    dialog.querySelector('[data-detail-source]').href = card.dataset.source;
    dialog.showModal(); dialog.querySelector('[data-metric-close]').focus();
  }));
  const close = () => { dialog.close(); opener?.focus(); };
  dialog.querySelector('[data-metric-close]').addEventListener('click', close);
  dialog.addEventListener('click', (event) => { if (event.target === dialog) close(); });
  document.querySelector('[data-print-report]')?.addEventListener('click', () => window.print());
})();

(() => {
  const form = document.querySelector('[data-analytics-form]');
  const dialog = document.querySelector('[data-analytics-filter-dialog]');
  if (!form || !dialog) return;
  const opener = form.querySelector('[data-analytics-filter-open]');
  opener?.addEventListener('click', () => { dialog.showModal(); dialog.querySelector('input, select, button')?.focus(); });
  dialog.querySelectorAll('[data-analytics-filter-close]').forEach((button) => button.addEventListener('click', () => { dialog.close(); opener?.focus(); }));
  document.querySelectorAll('[data-remove-filter]').forEach((button) => button.addEventListener('click', () => {
    const control = form.elements.namedItem(button.dataset.removeFilter);
    if (control) control.value = '';
    form.requestSubmit();
  }));
  form.elements.namedItem('range')?.addEventListener('change', (event) => {
    if (event.target.value === 'custom') dialog.showModal();
  });
})();

(() => {
  const grid = document.querySelector('[data-insight-grid]');
  if (!grid) return;
  const empty = document.querySelector('[data-insights-dismissed]');
  const storageKey = 'lumispixel.analytics.dismissed-insights';
  let dismissed = {};
  try { dismissed = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (error) { dismissed = {}; }
  function refresh() {
    const visible = [...grid.querySelectorAll('[data-insight-card]')].some((card) => !card.hidden);
    grid.hidden = !visible;
    if (empty) empty.hidden = visible;
  }
  grid.querySelectorAll('[data-insight-card]').forEach((card) => {
    const metric = card.querySelector('.lpa-insight-metric')?.textContent.trim() || '';
    const signature = `${card.dataset.insightId}:${metric}`;
    card.hidden = dismissed[card.dataset.insightId] === signature;
    card.querySelector('[data-dismiss-insight], [data-acknowledge-insight]')?.addEventListener('click', () => {
      dismissed[card.dataset.insightId] = signature;
      localStorage.setItem(storageKey, JSON.stringify(dismissed));
      card.hidden = true;
      refresh();
    });
  });
  refresh();
})();

(function initBusinessPerformance() {
  const root = document.querySelector('[data-business-performance]');
  const source = document.getElementById('business-performance-data');
  if (!root || !source) return;
  let data;
  try { data = JSON.parse(source.textContent); } catch (error) {
    root.querySelectorAll('[data-chart-state="error"]').forEach((state) => { state.hidden = false; }); return;
  }
  const metricDetails = Object.fromEntries(data.metric_options.map((item) => [item.key, item]));
  function formatted(value, format) {
    if (format === 'money') return new Intl.NumberFormat(undefined, { style: 'currency', currency: data.currency, maximumFractionDigits: 0 }).format(value);
    if (format === 'percent') return Number(value).toFixed(1) + '%';
    return new Intl.NumberFormat().format(value);
  }
  function render(card, metric, values, comparison) {
    const plot = card.querySelector('[data-trend-plot], [data-rolling-plot]');
    if (!plot) return;
    const detail = metricDetails[metric] || { label: 'Revenue', format: 'money' };
    const hasCurrent = values.some((point) => Number(point[metric] || 0));
    card.querySelector('[data-chart-state="empty"]')?.toggleAttribute('hidden', hasCurrent);
    plot.hidden = !hasCurrent;
    const max = Math.max(1, ...values.map((point) => Number(point[metric] || 0)), ...comparison.map((point) => Number(point[metric] || 0)));
    plot.replaceChildren(...values.map(function (point, index) {
      const group = document.createElement('span'); group.className = 'lpa-chart-point';
      const current = Number(point[metric] || 0); const previous = Number((comparison[index] || {})[metric] || 0);
      group.innerHTML = '<i class="is-current"></i><i class="is-comparison"></i><small></small><span class="lpa-chart-tooltip" role="tooltip"></span>';
      group.querySelector('.is-current').style.height = Math.max(current ? 3 : 1, current / max * 100) + '%';
      group.querySelector('.is-comparison').style.height = Math.max(previous ? 3 : 1, previous / max * 100) + '%';
      group.querySelector('small').textContent = data.labels[index] || '';
      group.querySelector('.lpa-chart-tooltip').innerHTML = '<strong>' + (data.labels[index] || '') + '</strong>Selected: ' + formatted(current, detail.format) + (data.comparison_available ? '<br>Comparison: ' + formatted(previous, detail.format) : '');
      group.tabIndex = 0; group.setAttribute('aria-label', group.querySelector('.lpa-chart-tooltip').textContent); return group;
    }));
    const total = values.reduce((sum, point) => sum + Number(point[metric] || 0), 0);
    const previousTotal = comparison.reduce((sum, point) => sum + Number(point[metric] || 0), 0);
    card.querySelector('[data-chart-total]').textContent = formatted(metric === 'conversion' ? total / Math.max(values.length, 1) : total, detail.format);
    const change = previousTotal ? (total - previousTotal) / previousTotal * 100 : null;
    const indicator = card.querySelector('[data-comparison-indicator]');
    if (indicator) indicator.textContent = change === null ? (data.comparison_available ? 'No prior value' : 'Comparison unavailable') : (change >= 0 ? '↑ ' : '↓ ') + Math.abs(change).toFixed(1) + '% vs comparison';
    const summary = detail.label + ' from ' + data.labels[0] + ' to ' + data.labels[data.labels.length - 1] + ' totals ' + formatted(total, detail.format) + (change === null ? ', with no comparable prior value.' : ', ' + Math.abs(change).toFixed(1) + '% ' + (change >= 0 ? 'higher' : 'lower') + ' than the comparison period.');
    card.querySelector('[data-chart-summary]').textContent = summary; plot.setAttribute('aria-label', summary);
  }
  root.querySelectorAll('[data-trend-card]').forEach((card) => render(card, card.dataset.metric, data.current, data.comparison));
  root.querySelectorAll('[data-trend-metric]').forEach((button) => button.addEventListener('click', function () {
    root.querySelectorAll('[data-trend-metric]').forEach((peer) => peer.setAttribute('aria-pressed', String(peer === button)));
    const card = button.closest('[data-trend-card]'); card.dataset.metric = button.dataset.trendMetric; render(card, button.dataset.trendMetric, data.current, data.comparison);
  }));
  root.querySelectorAll('[data-series-toggle]').forEach((button) => button.addEventListener('click', function () {
    const visible = button.getAttribute('aria-pressed') !== 'true'; button.setAttribute('aria-pressed', String(visible));
    button.closest('[data-trend-card]').classList.toggle('hide-' + button.dataset.seriesToggle, !visible);
  }));
  root.querySelector('[data-trend-grouping]')?.addEventListener('change', (event) => event.target.form.requestSubmit());
  const rolling = root.querySelector('[data-rolling-plot]');
  if (rolling) render(rolling.closest('[data-rolling-card]'), 'revenue', data.rolling.map((value) => ({ revenue: value })), []);
  const serviceBars = Array.from(root.querySelectorAll('.lpa-service-bars b'));
  const serviceMax = Math.max(1, ...serviceBars.map((bar) => Number(bar.style.getPropertyValue('--service-value'))));
  serviceBars.forEach((bar) => { bar.style.width = Number(bar.style.getPropertyValue('--service-value')) / serviceMax * 100 + '%'; });
}());

(function initCustomerIntelligence() {
  document.querySelectorAll('.lpa-ci-bars').forEach(function (chart) {
    const bars = Array.from(chart.querySelectorAll('b[style*="--value"]'));
    const values = bars.map((bar) => Number(bar.style.getPropertyValue('--value')) || 0);
    const maximum = chart.classList.contains('is-percent') ? 100 : Math.max(1, ...values);
    bars.forEach((bar, index) => bar.style.setProperty('--bar-width', Math.min(100, values[index] / maximum * 100) + '%'));
  });
}());

(function initBookingListView() {
  const root = document.querySelector('[data-booking-list]');
  if (!root) return;
  const checks = Array.from(root.querySelectorAll('[data-select-booking]'));
  const selectAll = root.querySelector('[data-select-all]');
  const bulk = root.querySelector('[data-booking-bulk]');
  const count = root.querySelector('[data-selected-count]');
  function syncSelection(source) {
    // Desktop rows and mobile cards represent the same bookings; mirror their state.
    if (source) {
      const index = checks.indexOf(source);
      const pairSize = checks.length / 2;
      const peer = checks[index < pairSize ? index + pairSize : index - pairSize];
      if (peer) peer.checked = source.checked;
    }
    const selected = root.querySelectorAll('.lpw-booking-table-wrap [data-select-booking]:checked').length;
    if (count) count.textContent = selected;
    if (bulk) bulk.hidden = selected === 0;
    if (selectAll) {
      const total = root.querySelectorAll('.lpw-booking-table-wrap [data-select-booking]').length;
      selectAll.checked = total > 0 && selected === total;
      selectAll.indeterminate = selected > 0 && selected < total;
    }
  }
  checks.forEach(function (check) { check.addEventListener('change', function () { syncSelection(check); }); });
  if (selectAll) selectAll.addEventListener('change', function () {
    checks.forEach(function (check) { check.checked = selectAll.checked; }); syncSelection();
  });
  const sort = root.querySelector('[data-booking-sort]');
  if (sort) sort.addEventListener('change', function () {
    const url = new URL(window.location.href); url.searchParams.set('sort', sort.value); url.searchParams.delete('page'); window.location.assign(url);
  });
  root.querySelectorAll('[data-booking-export]').forEach(function (button) { button.addEventListener('click', function () {
    const headings = Array.from(root.querySelectorAll('table thead th')).slice(1, -1).map(function (cell) { return cell.textContent.trim(); });
    const rows = Array.from(root.querySelectorAll('table tbody tr')).filter(function (row) {
      const selected = root.querySelectorAll('.lpw-booking-table-wrap [data-select-booking]:checked').length;
      return !selected || row.querySelector('[data-select-booking]').checked;
    }).map(function (row) { return Array.from(row.cells).slice(1, -1).map(function (cell) { return '"' + cell.textContent.trim().replace(/\s+/g, ' ').replace(/"/g, '""') + '"'; }).join(','); });
    const blob = new Blob([[headings.join(',')].concat(rows).join('\n')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'lumispixel-bookings.csv'; link.click(); URL.revokeObjectURL(link.href);
  }); });
}());

(function () {
  const form = document.querySelector('[data-schedule-filter-form]');
  if (!form) return;
  const trigger = document.querySelector('[data-schedule-filter-open]');
  if (trigger) trigger.addEventListener('click', function () {
    const open = trigger.getAttribute('aria-expanded') === 'true';
    trigger.setAttribute('aria-expanded', String(!open));
    form.classList.toggle('is-open', !open);
    if (!open) form.querySelector('input:not([type="hidden"]), select').focus();
  });
  form.querySelectorAll('select, input[type="date"], input[type="radio"], input[type="checkbox"]').forEach(function (control) {
    control.addEventListener('change', function () { form.requestSubmit(); });
  });
  document.querySelectorAll('[data-remove-filter]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      const control = form.elements[chip.dataset.removeFilter];
      if (!control) return;
      if (control instanceof RadioNodeList) Array.from(control).forEach(function (item) { item.checked = item.value === 'studio'; });
      else if (control.type === 'checkbox') control.checked = false;
      else control.value = '';
      form.requestSubmit();
    });
  });
  const save = document.querySelector('[data-save-schedule-view]');
  if (save) save.addEventListener('click', function () {
    const state = {};
    new FormData(form).forEach(function (value, key) { state[key] = value; });
    window.localStorage.setItem('lpw-schedule-saved-view', JSON.stringify(state));
    save.querySelector('span').textContent = 'View saved';
    save.querySelector('i').className = 'bi bi-bookmark-check-fill';
  });
}());

(function () {
  const layer = document.querySelector('[data-event-drawer-layer]');
  const dataNode = document.getElementById('schedule-event-data');
  if (!layer || !dataNode) return;
  const events = JSON.parse(dataNode.textContent).reduce(function (byId, event) {
    byId[event.drawer_id] = event;
    return byId;
  }, {});
  const drawer = layer.querySelector('[data-event-drawer]');
  let opener = null;

  function escapeHtml(value) {
    const node = document.createElement('span');
    node.textContent = String(value);
    return node.innerHTML;
  }
  function detail(label, value) {
    if (!value) return '';
    return '<div><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd></div>';
  }
  function closeDrawer() {
    layer.classList.remove('is-open');
    document.body.classList.remove('lpw-drawer-open');
    window.setTimeout(function () { layer.hidden = true; }, 180);
    if (opener) opener.focus();
  }
  function openDrawer(event, button) {
    opener = button;
    layer.querySelector('[data-event-kind]').textContent = event.kind === 'mini' ? 'Mini session' : event.kind;
    layer.querySelector('[data-event-title]').textContent = event.name;
    layer.querySelector('[data-event-summary]').textContent = event.session_type + ' · ' + event.status;
    const bookingOnly = event.kind === 'booking';
    const clientEvent = bookingOnly || event.kind === 'consultation' || event.kind === 'mini';
    const details = [
      clientEvent ? detail('Client / event', event.name) : '',
      clientEvent && event.contact ? detail('Contact', event.contact) : '',
      bookingOnly ? detail('Booking number', event.booking_number) : '',
      detail(bookingOnly ? 'Session type' : 'Event type', event.session_type),
      detail('Date and time', new Date(event.starts_at).toLocaleString([], {dateStyle: 'long', timeStyle: event.all_day ? undefined : 'short'})),
      detail('Duration', event.all_day ? 'All day' : event.duration),
      event.kind !== 'vacation' ? detail('Location', event.location) : '',
      bookingOnly ? detail('Package', event.package) : '',
      event.kind !== 'vacation' && event.kind !== 'blocked' ? detail('Assigned to', event.photographer) : '',
      detail('Status', event.status),
      bookingOnly ? detail('Contract', event.contract_status) + detail('Payment', event.payment_status) + detail('Questionnaire', event.questionnaire_status) : ''
    ].join('');
    layer.querySelector('[data-event-details]').innerHTML = details;
    const warnings = layer.querySelector('[data-event-warnings]');
    warnings.innerHTML = (event.warnings || []).map(function (warning) { return '<p><i class="bi bi-exclamation-triangle-fill" aria-hidden="true"></i><span>' + escapeHtml(warning) + '</span></p>'; }).join('');
    warnings.hidden = !event.warnings || !event.warnings.length;
    const notesWrap = layer.querySelector('[data-event-notes-wrap]');
    notesWrap.hidden = !event.notes || event.kind === 'vacation';
    layer.querySelector('[data-event-notes]').textContent = event.notes || '';
    layer.querySelector('[data-event-actions]').innerHTML = event.actions.map(function (label, index) {
      const danger = label.indexOf('Cancel') === 0 || label.indexOf('Remove') === 0;
      const canEdit = label.indexOf('Edit ') === 0;
      if (canEdit) return '<button type="button" class="lpw-btn" data-detail-edit="' + escapeHtml(event.drawer_id) + '">' + escapeHtml(label) + '</button>';
      return '<a class="lpw-btn ' + (index === 0 ? 'lpw-btn-primary ' : '') + (danger ? 'is-danger' : '') + '" href="' + encodeURI(event.url) + '">' + escapeHtml(label) + '</a>';
    }).join('');
    const editButton = layer.querySelector('[data-detail-edit]');
    if (editButton) editButton.addEventListener('click', function () {
      closeDrawer();
      window.setTimeout(function () { if (window.LumisScheduleEventForm) window.LumisScheduleEventForm.open(event.kind, button, event); }, 190);
    });
    layer.hidden = false;
    window.requestAnimationFrame(function () { layer.classList.add('is-open'); });
    document.body.classList.add('lpw-drawer-open');
    drawer.focus();
  }
  document.querySelectorAll('[data-schedule-event]').forEach(function (button) {
    button.addEventListener('click', function () { openDrawer(events[button.dataset.scheduleEvent], button); });
  });
  layer.querySelectorAll('[data-event-drawer-close]').forEach(function (button) { button.addEventListener('click', closeDrawer); });
  drawer.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeDrawer();
    if (event.key !== 'Tab') return;
    const focusable = Array.from(drawer.querySelectorAll('a[href], button:not([disabled])'));
    if (!focusable.length) return;
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}());

(function () {
  const summary = document.querySelector('[data-schedule-summary]');
  if (!summary) return;
  const toggle = summary.querySelector('[data-summary-toggle]');
  const panels = summary.querySelector('.lpw-summary-panels');
  toggle.addEventListener('click', function () {
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!expanded));
    toggle.querySelector('span').textContent = expanded ? 'Show' : 'Hide';
    toggle.querySelector('i').className = 'bi ' + (expanded ? 'bi-chevron-down' : 'bi-chevron-up');
    panels.hidden = expanded;
  });
}());

(function () {
  const layer = document.querySelector('[data-event-form-layer]');
  if (!layer) return;
  const drawer = layer.querySelector('[data-event-form-drawer]');
  const form = layer.querySelector('[data-event-form]');
  const title = layer.querySelector('[data-event-form-title]');
  const alert = layer.querySelector('[data-form-alert]');
  const conflict = layer.querySelector('[data-conflict-warning]');
  const initialDefaults = new FormData(form);
  let dirty = false;
  let opener = null;
  let editing = false;

  function currentType() { return form.elements.event_type.value; }
  function syncType() {
    const type = currentType();
    layer.querySelectorAll('[data-type-fields]').forEach(function (section) {
      const visible = section.dataset.typeFields.split(' ').includes(type);
      section.hidden = !visible;
      section.querySelectorAll('[data-required-for]').forEach(function (field) {
        field.required = visible && field.dataset.requiredFor.split(' ').includes(type);
      });
    });
    if (!editing) title.textContent = 'Create ' + form.elements.event_type.closest('fieldset').querySelector('input[value="' + type + '"] + span').textContent.trim();
    checkConflict();
  }
  function syncAllDay() {
    const allDay = form.elements.all_day.checked;
    layer.querySelectorAll('[data-time-field]').forEach(function (label) {
      label.hidden = allDay;
      label.querySelector('input').required = !allDay;
    });
  }
  function checkConflict() {
    if (!form.elements.start_date.value) return;
    const type = currentType();
    const start = form.elements.start_time.value;
    conflict.hidden = form.elements.all_day.checked || !['booking', 'consultation', 'mini'].includes(type) || !(start >= '09:30' && start <= '10:30');
  }
  function resetForm() {
    form.reset();
    initialDefaults.forEach(function (value, key) {
      const field = form.elements[key];
      if (field && field.type !== 'radio' && field.type !== 'checkbox') field.value = value;
    });
    form.querySelectorAll('.has-error').forEach(function (field) { field.classList.remove('has-error'); });
    form.querySelectorAll('.lpw-field-error').forEach(function (error) { error.textContent = ''; });
    alert.hidden = true;
  }
  function close(force) {
    if (!force && dirty && !window.confirm('Discard your unsaved changes?')) return;
    layer.classList.remove('is-open');
    document.body.classList.remove('lpw-drawer-open');
    window.setTimeout(function () { layer.hidden = true; }, 220);
    dirty = false;
    if (opener) opener.focus();
  }
  function setValue(name, value) { if (form.elements[name] && value != null) form.elements[name].value = value; }
  function open(type, button, event) {
    opener = button;
    resetForm();
    editing = Boolean(event);
    const radio = form.querySelector('input[name="event_type"][value="' + type + '"]');
    if (radio) radio.checked = true;
    if (event) {
      title.textContent = 'Edit ' + (type === 'mini' ? 'Mini Session' : type.charAt(0).toUpperCase() + type.slice(1));
      setValue('title', event.name);
      setValue('location', event.location === 'Away' ? '' : event.location);
      setValue('notes', event.notes);
      setValue('session_type', event.session_type);
      setValue('client', event.name);
      setValue('contact', event.name);
      setValue('related_work', event.name);
      setValue('reason', event.name);
      setValue('mini_name', event.name);
      const start = new Date(event.starts_at); const end = new Date(event.ends_at);
      setValue('start_date', start.toISOString().slice(0, 10)); setValue('end_date', end.toISOString().slice(0, 10));
      setValue('start_time', start.toTimeString().slice(0, 5)); setValue('end_time', end.toTimeString().slice(0, 5));
      form.elements.all_day.checked = event.all_day;
    }
    syncType(); syncAllDay();
    layer.hidden = false;
    window.requestAnimationFrame(function () { layer.classList.add('is-open'); });
    document.body.classList.add('lpw-drawer-open');
    drawer.focus();
    window.setTimeout(function () { form.elements.title.focus(); }, 230);
  }
  function validate() {
    let first = null;
    form.querySelectorAll(':invalid').forEach(function (field) {
      if (field.closest('[hidden]')) return;
      field.classList.add('has-error');
      const error = field.parentElement.querySelector('.lpw-field-error');
      if (error) error.textContent = field.validity.valueMissing ? 'This field is required.' : 'Enter a valid value.';
      if (!first) first = field;
    });
    if (form.elements.end_date.value && form.elements.start_date.value) {
      const start = form.elements.start_date.value + 'T' + (form.elements.start_time.value || '00:00');
      const end = form.elements.end_date.value + 'T' + (form.elements.end_time.value || '23:59');
      if (end <= start) { form.elements.end_date.classList.add('has-error'); first = first || form.elements.end_date; }
    }
    alert.hidden = !first;
    if (first) first.focus();
    return !first;
  }
  function toast(message) {
    const node = document.createElement('div'); node.className = 'lpw-event-form-saved'; node.setAttribute('role', 'status'); node.textContent = message;
    document.body.appendChild(node); window.setTimeout(function () { node.remove(); }, 2800);
  }

  document.querySelectorAll('[data-event-form-open]').forEach(function (button) { button.addEventListener('click', function () { open(button.dataset.eventFormOpen, button); }); });
  form.addEventListener('input', function (event) { dirty = true; event.target.classList.remove('has-error'); checkConflict(); });
  form.addEventListener('change', function (event) { dirty = true; if (event.target.name === 'event_type') syncType(); if (event.target.name === 'all_day') syncAllDay(); checkConflict(); });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!validate()) return;
    const another = event.submitter && event.submitter.value === 'another';
    toast(editing ? 'Event updated.' : 'Event saved to your schedule.');
    dirty = false;
    if (another) { const type = currentType(); open(type, opener); }
    else close(true);
  });
  layer.querySelectorAll('[data-event-form-close]').forEach(function (button) { button.addEventListener('click', function () { close(false); }); });
  drawer.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { event.preventDefault(); close(false); }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(drawer.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])')).filter(function (el) { return !el.closest('[hidden]'); });
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  window.addEventListener('beforeunload', function (event) { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  window.LumisScheduleEventForm = { open: open };
}());

(function () {
  const layer = document.querySelector('[data-availability-layer]');
  const opener = document.querySelector('[data-availability-open]');
  if (!layer || !opener) return;
  const drawer = layer.querySelector('.lpw-availability-drawer');
  const form = layer.querySelector('[data-availability-form]');
  const editor = layer.querySelector('[data-exception-editor]');
  const type = form.elements.exception_type;
  const status = layer.querySelector('[data-availability-status]');
  let dirty = false;

  function open() {
    layer.hidden = false;
    window.requestAnimationFrame(function () { layer.classList.add('is-open'); });
    opener.setAttribute('aria-expanded', 'true');
    document.body.classList.add('lpw-drawer-open');
    drawer.focus();
  }
  function close() {
    layer.classList.remove('is-open');
    opener.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('lpw-drawer-open');
    window.setTimeout(function () { layer.hidden = true; opener.focus(); }, 220);
  }
  function syncException() {
    editor.querySelector('.lpw-exception-repeat').hidden = type.value !== 'recurring';
    const timed = type.value !== 'unavailable';
    form.elements.exception_start.closest('label').hidden = !timed;
    form.elements.exception_end.closest('label').hidden = !timed;
  }
  function flash(message) {
    status.textContent = message;
    status.classList.add('lpw-availability-saved');
    window.setTimeout(function () { status.classList.remove('lpw-availability-saved'); }, 1800);
  }

  opener.addEventListener('click', open);
  layer.querySelectorAll('[data-availability-close]').forEach(function (button) { button.addEventListener('click', close); });
  layer.querySelectorAll('[data-add-exception]').forEach(function (button) {
    button.addEventListener('click', function () { editor.hidden = false; type.value = button.dataset.addException; syncException(); form.elements.exception_date.focus(); });
  });
  type.addEventListener('change', syncException);
  layer.querySelector('[data-apply-days]').addEventListener('click', function () {
    const count = form.querySelectorAll('input[name="days"]:checked').length;
    flash('Working hours applied to ' + count + ' selected day' + (count === 1 ? '.' : 's.'));
  });
  layer.querySelector('[data-copy-schedule]').addEventListener('click', function () {
    form.querySelectorAll('input[name="days"]').forEach(function (day) { day.checked = day.value !== 'Sun'; });
    flash('Monday’s schedule copied. Review selected days before saving.');
  });
  layer.querySelector('[data-save-exception]').addEventListener('click', function () {
    if (!form.elements.exception_date.value) { form.elements.exception_date.focus(); return; }
    const labels = { override: 'Date-specific hours', unavailable: 'Temporarily unavailable', recurring: 'Recurring blocked time' };
    const item = document.createElement('li');
    item.innerHTML = '<i class="bi bi-calendar2-x"></i><span><strong>' + labels[type.value] + '</strong><small>' + form.elements.exception_date.value + (type.value === 'unavailable' ? ' · All day' : ' · ' + form.elements.exception_start.value + '–' + form.elements.exception_end.value) + '</small></span><button type="button" aria-label="Remove exception"><i class="bi bi-trash"></i></button>';
    layer.querySelector('[data-exception-list]').appendChild(item);
    editor.hidden = true; dirty = true; flash('Exception added. Save to publish this change.');
  });
  layer.querySelector('[data-exception-list]').addEventListener('click', function (event) { const button = event.target.closest('button'); if (button) { button.closest('li').remove(); dirty = true; } });
  form.addEventListener('input', function () { dirty = true; });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const member = form.elements.member.value;
    window.localStorage.setItem('lpw-availability-' + member, JSON.stringify(Object.fromEntries(new FormData(form).entries())));
    dirty = false; flash('Availability saved. Client booking rules are now up to date.');
    window.setTimeout(close, 650);
  });
  drawer.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') close();
    if (event.key !== 'Tab') return;
    const focusable = Array.from(drawer.querySelectorAll('button:not([hidden]),input:not([hidden]),select:not([hidden])')).filter(function (node) { return !node.closest('[hidden]'); });
    if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable[focusable.length - 1].focus(); }
    else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) { event.preventDefault(); focusable[0].focus(); }
  });
  window.addEventListener('beforeunload', function (event) { if (dirty && !layer.hidden) { event.preventDefault(); event.returnValue = ''; } });
}());

(function () {
  const layer = document.querySelector('[data-move-layer]');
  const dataNode = document.getElementById('schedule-event-data');
  if (!layer || !dataNode) return;
  const events = JSON.parse(dataNode.textContent);
  const byDrawer = Object.fromEntries(events.map(function (item) { return [item.drawer_id, item]; }));
  const checks = layer.querySelector('[data-move-checks]');
  const error = layer.querySelector('[data-move-error]');
  const save = layer.querySelector('[data-move-save]');
  const notify = layer.querySelector('[data-move-notify]');
  let pending = null; let opener = null;

  function csrf() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }
  function request(url, body) {
    return fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify(body)})
      .then(function (response) { return response.json().then(function (json) { if (!response.ok) throw json; return json; }); });
  }
  function formatRange(start, end) {
    const options = {weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'};
    return new Intl.DateTimeFormat(undefined, options).format(start) + ' – ' + new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit'}).format(end);
  }
  function close() { layer.hidden = true; document.body.classList.remove('lpw-drawer-open'); if (opener) opener.focus(); }
  function render(result) {
    const start = new Date(result.starts_at); const end = new Date(result.ends_at);
    layer.querySelector('[data-move-time]').textContent = formatRange(start, end);
    checks.innerHTML = result.checks.map(function (item) {
      return '<div class="lpw-move-check' + (item.ok ? '' : ' is-warning') + '"><i class="bi ' + (item.ok ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill') + '"></i><strong>' + item.label + '</strong><small>' + item.detail + '</small></div>';
    }).join('');
    notify.closest('label').hidden = !result.notify_recommended;
    notify.checked = result.notify_recommended;
    save.disabled = result.blocking;
  }
  function preview(button, start, duration) {
    const item = byDrawer[button.dataset.movableEvent];
    if (!item || !item.persisted) return;
    opener = button; pending = {url: button.dataset.moveUrl, starts_at: start.toISOString(), duration_minutes: duration, previous: {starts_at: item.starts_at, duration_minutes: Math.round((new Date(item.ends_at) - new Date(item.starts_at)) / 60000)}};
    error.hidden = true; checks.innerHTML = '<div class="lpw-schedule-loading">Checking conflicts, availability, blocked time, buffers, and travel…</div>';
    save.disabled = true; layer.hidden = false; document.body.classList.add('lpw-drawer-open'); layer.querySelector('.lpw-move-dialog').focus();
    request(pending.url, {starts_at: pending.starts_at, duration_minutes: duration, preview: true}).then(render).catch(function (problem) { error.textContent = problem.error || 'The schedule check could not be completed. Try again.'; error.hidden = false; });
  }
  function toast(previous) {
    const node = document.createElement('div'); node.className = 'lpw-event-form-saved lpw-undo-toast'; node.setAttribute('role', 'status');
    node.innerHTML = '<span>Schedule updated.</span><button type="button">Undo</button>';
    document.body.appendChild(node);
    const timer = window.setTimeout(function () { node.remove(); }, 7000);
    node.querySelector('button').addEventListener('click', function () {
      clearTimeout(timer); request(pending.url, {starts_at: previous.starts_at, duration_minutes: previous.duration_minutes, preview: false}).then(function () { window.location.reload(); }).catch(function () { node.querySelector('span').textContent = 'Undo failed. Refresh and try again.'; });
    });
  }
  document.querySelectorAll('[data-movable-event]').forEach(function (button) {
    button.setAttribute('aria-describedby', 'schedule-move-help');
    button.addEventListener('dragstart', function (event) { event.dataTransfer.setData('text/plain', button.dataset.movableEvent); button.classList.add('is-dragging'); });
    button.addEventListener('dragend', function () { button.classList.remove('is-dragging'); });
    button.addEventListener('keydown', function (event) {
      if (!event.altKey || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault(); const item = byDrawer[button.dataset.movableEvent]; const start = new Date(item.starts_at); let duration = Math.round((new Date(item.ends_at) - start) / 60000);
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') duration = Math.max(30, duration + (event.key === 'ArrowDown' ? 15 : -15));
      else start.setDate(start.getDate() + (event.key === 'ArrowRight' ? 1 : -1));
      preview(button, start, duration);
    });
  });
  document.querySelectorAll('[data-drop-date]').forEach(function (cell) {
    cell.addEventListener('dragover', function (event) { event.preventDefault(); cell.classList.add('is-drop-target'); });
    cell.addEventListener('dragleave', function () { cell.classList.remove('is-drop-target'); });
    cell.addEventListener('drop', function (event) {
      event.preventDefault(); cell.classList.remove('is-drop-target'); const button = document.querySelector('[data-movable-event="' + event.dataTransfer.getData('text/plain') + '"]'); if (!button) return;
      const item = byDrawer[button.dataset.movableEvent]; const start = new Date(item.starts_at); const parts = cell.dataset.dropDate.split('-'); start.setFullYear(+parts[0], +parts[1] - 1, +parts[2]); preview(button, start, Math.round((new Date(item.ends_at) - new Date(item.starts_at)) / 60000));
    });
  });
  layer.querySelectorAll('[data-move-close]').forEach(function (button) { button.addEventListener('click', close); });
  save.addEventListener('click', function () {
    save.disabled = true; error.hidden = true;
    request(pending.url, {starts_at: pending.starts_at, duration_minutes: pending.duration_minutes, notify_client: notify.checked, preview: false}).then(function () { const previous = pending.previous; close(); toast(previous); window.setTimeout(function () { window.location.reload(); }, 7200); }).catch(function (problem) { save.disabled = false; error.textContent = problem.error || 'This change could not be saved.'; error.hidden = false; if (problem.checks) render(problem); });
  });
  layer.querySelector('.lpw-move-dialog').addEventListener('keydown', function (event) { if (event.key === 'Escape') close(); });
}());

document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-text]');
  if (!button) return;
  await navigator.clipboard.writeText(button.dataset.copyText);
  const label = button.textContent;
  button.textContent = 'Copied';
  window.setTimeout(() => { button.textContent = label; }, 1500);
});

(function () {
  const button = document.querySelector('[data-team-filter-open]');
  const filters = document.querySelector('[data-team-filters]');
  if (!button || !filters) return;
  button.addEventListener('click', function () {
    const open = filters.classList.toggle('is-open');
    button.setAttribute('aria-expanded', String(open));
  });
})();
