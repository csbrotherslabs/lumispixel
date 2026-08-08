(function () {
  'use strict';
  function csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; }
  const page = document.querySelector('[data-upload-page]');
  if (page) {
    const drop = page.querySelector('[data-upload-drop]');
    const input = page.querySelector('[data-upload-input]');
    const gallery = page.querySelector('[data-upload-gallery]');
    const list = page.querySelector('[data-upload-list]');
    const error = page.querySelector('[data-upload-error]');
    const picker = page.querySelector('[data-gallery-picker]');
    const selected = page.querySelector('[data-selected-gallery]');
    const requirement = page.querySelector('[data-upload-requirement]');
    const search = page.querySelector('[data-gallery-search]');
    const completion = page.querySelector('[data-queue-complete]');
    const pending = [];
    let active = 0;
    let availableStorage = Number(page.dataset.storageAvailable);
    const concurrency = 3;

    function setDestination() {
      const option = gallery.selectedOptions[0], hasGallery = Boolean(gallery.value);
      picker.hidden = hasGallery; selected.hidden = !hasGallery; input.disabled = !hasGallery;
      drop.classList.toggle('is-disabled', !hasGallery); drop.tabIndex = hasGallery ? 0 : -1;
      drop.setAttribute('aria-disabled', String(!hasGallery)); requirement.hidden = hasGallery;
      if (!hasGallery) return;
      selected.querySelector('[data-selected-name]').textContent = option.dataset.name;
      selected.querySelector('[data-selected-event]').textContent = option.dataset.event || option.dataset.client || '';
      selected.querySelector('[data-selected-date]').textContent = option.dataset.date || '';
      const thumb = selected.querySelector('[data-selected-thumbnail]'); thumb.replaceChildren();
      if (option.dataset.thumbnail) { const image = document.createElement('img'); image.src = option.dataset.thumbnail; image.alt = ''; image.width = 64; image.height = 64; thumb.append(image); }
      else { const icon = document.createElement('i'); icon.className = 'bi bi-images'; icon.setAttribute('aria-hidden', 'true'); thumb.append(icon); }
    }
    function counts() {
      ['uploading', 'queued', 'completed', 'failed'].forEach(function (status) {
        const target = page.querySelector('[data-count="' + status + '"]');
        if (target) target.textContent = list.querySelectorAll('[data-status="' + status + '"]').length;
      });
      const clear = page.querySelector('[data-clear-completed]');
      if (clear) clear.hidden = !list.querySelector('[data-status="completed"]');
    }
    function setStatus(row, status) {
      row.className = 'lp-upload-row is-' + status; row.dataset.status = status; counts();
    }
    function releasePreview(row) {
      if (row.dataset.previewUrl) { URL.revokeObjectURL(row.dataset.previewUrl); delete row.dataset.previewUrl; }
    }
    function removeRow(row) { releasePreview(row); row.remove(); counts(); }
    function serverMessage(xhr) {
      try { const body = JSON.parse(xhr.responseText); return body.error || body.errors?.[0]?.error; } catch (_) { return ''; }
    }
    function finishCheck() {
      if (active || pending.length || !list.querySelector('[data-local-upload]')) return;
      const failed = list.querySelector('[data-local-upload][data-status="failed"]');
      if (failed) return;
      const completed = list.querySelectorAll('[data-local-upload][data-status="completed"]').length;
      if (!completed) return;
      const option = gallery.selectedOptions[0];
      completion.querySelector('span').textContent = completed + ' photo' + (completed === 1 ? '' : 's') + ' uploaded to ' + option.dataset.name + '.';
      completion.querySelector('[data-view-gallery]').href = option.dataset.galleryUrl;
      completion.hidden = false;
    }
    function createRow(file, galleryName) {
      const row = document.createElement('article'); row.className = 'lp-upload-row is-queued';
      row.dataset.status = 'queued'; row.dataset.localUpload = 'true';
      row.innerHTML = '<div class="lp-file-icon"><img alt=""></div><div class="lp-file-main"><strong></strong><span></span><div data-progress-slot></div></div><div class="lp-file-state"><strong>Queued</strong><span>Waiting to upload</span></div><div class="lp-file-actions"><button type="button" data-remove aria-label="Remove queued file"><i class="bi bi-x-lg" aria-hidden="true"></i></button></div>';
      row.querySelector('.lp-file-main strong').textContent = file.name;
      row.querySelector('.lp-file-main span').textContent = (file.size / 1048576).toFixed(1) + ' MB · ' + galleryName;
      const image = row.querySelector('img'); const preview = URL.createObjectURL(file); row.dataset.previewUrl = preview;
      image.src = preview; image.onload = function () { URL.revokeObjectURL(preview); delete row.dataset.previewUrl; };
      image.onerror = function () { releasePreview(row); image.replaceWith(Object.assign(document.createElement('i'), {className: 'bi bi-image'})); };
      return row;
    }
    function pump() {
      while (active < concurrency && pending.length) {
        const job = pending.shift();
        if (!job.row.isConnected) continue;
        upload(job);
      }
      finishCheck();
    }
    function upload(job) {
      const row = job.row, file = job.file;
      active += 1; setStatus(row, 'uploading');
      const state = row.querySelector('.lp-file-state'); state.querySelector('strong').textContent = 'Uploading'; state.querySelector('span').textContent = 'Starting…';
      const slot = row.querySelector('[data-progress-slot]');
      slot.innerHTML = '<div class="lp-progress-copy"><span data-percent>0%</span><span data-transfer></span></div><progress max="100" value="0"></progress>';
      const progress = slot.querySelector('progress'); progress.setAttribute('aria-label', file.name + ': Uploading, 0 percent');
      const actions = row.querySelector('.lp-file-actions'); actions.innerHTML = '<button type="button" data-cancel aria-label="Cancel ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
      const data = new FormData(); data.append('gallery', job.galleryId); data.append('files', file);
      const xhr = new XMLHttpRequest(), started = performance.now(); let lastPaint = 0;
      xhr.open('POST', page.dataset.uploadUrl); xhr.setRequestHeader('X-CSRFToken', csrf());
      xhr.upload.onprogress = function (event) {
        if (!event.lengthComputable) return;
        const now = performance.now(); if (now - lastPaint < 100 && event.loaded < event.total) return; lastPaint = now;
        const percent = Math.round(event.loaded / event.total * 100);
        const elapsed = Math.max((now - started) / 1000, .1), speed = event.loaded / elapsed;
        progress.value = percent; progress.textContent = percent + '%'; progress.setAttribute('aria-label', file.name + ': Uploading, ' + percent + ' percent');
        slot.querySelector('[data-percent]').textContent = percent + '%';
        const remaining = Math.ceil((event.total - event.loaded) / Math.max(speed, 1));
        slot.querySelector('[data-transfer]').textContent = (speed / 1048576).toFixed(1) + ' MB/s · ' + remaining + ' sec remaining';
      };
      function failed(reason) {
        setStatus(row, 'failed'); state.querySelector('strong').textContent = 'Upload failed'; state.querySelector('span').textContent = reason || 'Network interrupted'; slot.replaceChildren();
        actions.innerHTML = '<button type="button" data-retry aria-label="Retry ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-arrow-clockwise" aria-hidden="true"></i></button><button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
        actions.querySelector('[data-retry]').onclick = function () { setStatus(row, 'queued'); state.querySelector('strong').textContent = 'Queued'; state.querySelector('span').textContent = 'Waiting to upload'; actions.innerHTML = '<button type="button" data-remove aria-label="Remove queued file"><i class="bi bi-x-lg" aria-hidden="true"></i></button>'; pending.push(job); pump(); };
        actions.querySelector('[data-remove]').onclick = function () { removeRow(row); finishCheck(); };
      }
      xhr.onload = function () {
        active -= 1;
        if (xhr.status >= 200 && xhr.status < 300) {
          setStatus(row, 'completed'); availableStorage -= file.size; state.querySelector('strong').textContent = 'Uploaded'; state.querySelector('span').textContent = 'Upload complete';
          slot.innerHTML = '<div class="lp-upload-success"><i class="bi bi-check2-circle" aria-hidden="true"></i>100%</div>';
          actions.innerHTML = '<button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + ' from queue"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
          actions.querySelector('[data-remove]').onclick = function () { removeRow(row); };
        } else failed(serverMessage(xhr) || 'The upload could not be completed.');
        pump();
      };
      xhr.onerror = function () { active -= 1; failed('Network interrupted'); pump(); };
      xhr.onabort = function () { active -= 1; removeRow(row); pump(); };
      actions.querySelector('[data-cancel]').onclick = function () { xhr.abort(); };
    }
    function queue(files) {
      error.replaceChildren(); completion.hidden = true;
      if (!gallery.value) { error.textContent = 'Select a gallery to begin uploading.'; return; }
      const accepted = [];
      Array.from(files).forEach(function (file) {
        let message = '';
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) message = file.name + ' isn’t supported.';
        else if (file.size > 25 * 1024 * 1024) message = file.name + ' exceeds the 25 MB limit.';
        if (message) { const note = document.createElement('p'); note.textContent = message; error.append(note); }
        else accepted.push(file);
      });
      if (accepted.reduce((total, file) => total + file.size, 0) > availableStorage) { const note = document.createElement('p'); note.textContent = 'Not enough storage to upload these files.'; error.append(note); input.value = ''; return; }
      accepted.forEach(function (file) {
        const row = createRow(file, gallery.selectedOptions[0].dataset.name); const empty = list.querySelector('[data-queue-empty]'); if (empty) empty.remove(); list.append(row);
        const job = {file: file, row: row, galleryId: gallery.value}; pending.push(job);
        row.querySelector('[data-remove]').onclick = function () { const index = pending.indexOf(job); if (index >= 0) pending.splice(index, 1); removeRow(row); };
      });
      counts(); input.value = ''; pump();
    }
    gallery.addEventListener('change', setDestination);
    page.querySelector('[data-change-gallery]').addEventListener('click', function () { gallery.value = ''; setDestination(); search.focus(); });
    search.addEventListener('input', function () { const query = search.value.trim().toLowerCase(); Array.from(gallery.options).forEach(function (option, index) { option.hidden = index > 0 && !option.textContent.toLowerCase().includes(query); }); });
    input.addEventListener('change', function () { queue(input.files); });
    drop.addEventListener('click', function () { if (!input.disabled) input.click(); });
    drop.addEventListener('keydown', function (event) { if (!input.disabled && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); input.click(); } });
    ['dragover', 'dragenter'].forEach(function (name) { drop.addEventListener(name, function (event) { event.preventDefault(); if (!input.disabled) drop.classList.add('is-dragging'); }); });
    ['dragleave', 'drop'].forEach(function (name) { drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.remove('is-dragging'); if (name === 'drop' && !input.disabled) queue(event.dataTransfer.files); }); });
    page.querySelector('[data-clear-completed]')?.addEventListener('click', function () { list.querySelectorAll('[data-status="completed"]').forEach(removeRow); completion.hidden = true; });
    page.querySelector('[data-upload-more]')?.addEventListener('click', function () { completion.hidden = true; drop.focus(); input.click(); });
    window.addEventListener('beforeunload', function (event) { if (active || pending.length) { event.preventDefault(); event.returnValue = ''; } });
    setDestination(); counts();
  }
  const size=document.querySelector('[data-grid-size]'),grid=document.querySelector('[data-photo-grid]');if(size&&grid)size.oninput=function(){grid.style.setProperty('--photo-size',size.value+'px');};
  const checks=Array.from(document.querySelectorAll('[data-photo-check]')),all=document.querySelector('[data-photo-select-all]'),bulk=document.querySelector('[data-photo-bulk]');function update(){const n=checks.filter(function(c){return c.checked;}).length;if(bulk){bulk.hidden=!n;bulk.querySelector('[data-photo-count]').textContent=n;}if(all)all.indeterminate=n>0&&n<checks.length;}if(all)all.onchange=function(){checks.forEach(function(c){c.checked=all.checked;});update();};checks.forEach(function(c){c.onchange=update;});document.querySelectorAll('[data-select-photo]').forEach(function(b){b.onclick=function(){const c=b.closest('article').querySelector('[data-photo-check]');c.checked=!c.checked;update();};});
  document.querySelectorAll('[data-photo-action],[data-server-action]').forEach(function(b){b.onclick=function(){if(b.dataset.photoAction==='delete'&&!confirm('Delete this photo permanently?'))return;fetch(b.dataset.actionUrl,{method:'POST',headers:{'X-CSRFToken':csrf(),'Content-Type':'application/x-www-form-urlencoded'},body:'action='+(b.dataset.photoAction||b.dataset.serverAction)}).then(function(r){if(r.ok&&(b.dataset.photoAction==='delete'||b.dataset.serverAction==='remove'))b.closest('article').remove();});};});
})();

// Album curation controls and cross-album drag-and-drop.
(() => {
  const form = document.querySelector('[data-album-photos]');
  if (form) {
    const checks = [...form.querySelectorAll('[data-album-photo-check]')];
    const bulk = form.querySelector('[data-album-bulk]');
    const count = bulk?.querySelector('strong span');
    const refresh = () => {
      const selected = checks.filter((item) => item.checked).length;
      if (bulk) bulk.hidden = !selected;
      if (count) count.textContent = selected;
    };
    checks.forEach((item) => item.addEventListener('change', refresh));
    document.querySelector('[data-album-select-all]')?.addEventListener('change', (event) => {
      checks.forEach((item) => { item.checked = event.target.checked; });
      refresh();
    });
    form.querySelectorAll('[data-album-photo]').forEach((card) => {
      card.addEventListener('dragstart', (event) => {
        const checked = card.querySelector('[data-album-photo-check]');
        if (checked && !checked.checked) checked.checked = true;
        refresh();
        event.dataTransfer.setData('application/x-lumispixel-photos', JSON.stringify(checks.filter((item) => item.checked).map((item) => item.value)));
        event.dataTransfer.effectAllowed = 'move';
      });
    });
  }
  document.querySelectorAll('[data-album-drop-url]').forEach((card) => {
    card.addEventListener('dragover', (event) => { event.preventDefault(); card.classList.add('is-drop-target'); });
    card.addEventListener('dragleave', () => card.classList.remove('is-drop-target'));
    card.addEventListener('drop', async (event) => {
      event.preventDefault();
      card.classList.remove('is-drop-target');
      let photoIds = [];
      try { photoIds = JSON.parse(event.dataTransfer.getData('application/x-lumispixel-photos')); } catch (_) { return; }
      const sourceForm = document.querySelector('[data-album-photos]');
      if (!sourceForm || !photoIds.length) return;
      const data = new FormData(sourceForm);
      data.set('action', 'move');
      data.set('target_album', card.dataset.albumDropUrl.match(/albums\/(\d+)/)?.[1] || '');
      data.delete('photo_ids');
      photoIds.forEach((id) => data.append('photo_ids', id));
      const response = await fetch(sourceForm.action, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (response.ok) window.location.reload();
    });
  });
  document.querySelectorAll('[data-album-delete]').forEach((button) => button.addEventListener('click', () => button.closest('form').querySelector('dialog').showModal()));
  document.querySelectorAll('[data-album-cancel]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
})();

// Contextual activity details drawer.
document.querySelectorAll('[data-activity-open]').forEach((button) => button.addEventListener('click', () => document.getElementById(button.dataset.activityOpen)?.showModal()));
document.querySelectorAll('[data-activity-close]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('.lp-activity-panel').forEach((panel) => panel.addEventListener('click', (event) => { if (event.target === panel) panel.close(); }));

// Gallery archive selection and high-friction workflows.
(() => {
  const page = document.querySelector('[data-archive-page]');
  if (!page) return;
  const form = page.querySelector('[data-archive-form]');
  const checks = [...form.querySelectorAll('[data-archive-check]')];
  const bulk = form.querySelector('[data-archive-bulk]');
  const sync = () => { const n = checks.filter(c => c.checked).length; bulk.hidden = !n; bulk.querySelector('span').textContent = n; };
  checks.forEach(c => c.addEventListener('change', sync));
  page.querySelector('[data-archive-all]')?.addEventListener('change', e => { checks.forEach(c => c.checked = e.target.checked); sync(); });
  const open = selector => page.querySelector(selector)?.showModal();
  page.querySelectorAll('[data-archive-open]').forEach(b => b.addEventListener('click', () => open('[data-archive-modal]')));
  page.querySelectorAll('[data-retention-open]').forEach(b => b.addEventListener('click', () => open('[data-retention-modal]')));
  page.querySelectorAll('[data-single-retention]').forEach(b => b.addEventListener('click', () => { checks.forEach(c => c.checked = c.value === b.dataset.singleRetention); sync(); open('[data-retention-modal]'); }));
  page.querySelectorAll('[data-single]').forEach(b => b.addEventListener('click', () => { checks.forEach(c => c.checked = c.value === b.dataset.single); }));
  page.querySelectorAll('[data-dialog-close]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));
  const gallerySelect = page.querySelector('[data-archive-gallery]');
  gallerySelect?.addEventListener('change', () => { const option = gallerySelect.selectedOptions[0]; page.querySelector('[data-preview-photos]').textContent = option?.dataset.photos || '—'; page.querySelector('[data-preview-storage]').textContent = option?.dataset.storage || '—'; page.querySelector('[data-preview-access]').textContent = option?.dataset.access || '—'; });
  page.querySelectorAll('[data-delete-open]').forEach(b => b.addEventListener('click', () => { checks.forEach(c => c.checked = false); const modal = page.querySelector('[data-delete-modal]'); const id = modal.querySelector('[data-delete-id]'); id.disabled = false; id.value = b.dataset.id; modal.querySelector('[data-delete-name]').textContent = b.dataset.name; modal.querySelector('[name=gallery_name]').value = ''; modal.querySelector('[name=acknowledge_delete]').checked = false; modal.showModal(); }));
})();
