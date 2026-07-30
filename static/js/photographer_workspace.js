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

(function () {
  const select = document.querySelector('[data-analytics-metric]');
  const chart = document.querySelector('[data-analytics-chart]');
  if (!select || !chart) return;
  function draw() {
    const metric = select.value;
    const points = Array.from(chart.children);
    const max = Math.max(1, ...points.map(function (point) { return Number(point.dataset[metric] || 0); }));
    points.forEach(function (point) {
      const value = Number(point.dataset[metric] || 0);
      point.querySelector('b').style.height = Math.max(value ? 6 : 2, value / max * 100) + '%';
      point.title = point.querySelector('small').textContent + ': ' + value + ' ' + select.options[select.selectedIndex].text.toLowerCase();
    });
  }
  select.addEventListener('change', draw);
  draw();
}());
