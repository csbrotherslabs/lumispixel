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
