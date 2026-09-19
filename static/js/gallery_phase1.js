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
    const visibleQueuedLimit = 40;
    const visibleCompletedLimit = 20;
    let showAllQueued = false;
    let showAllCompleted = false;
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
    function applyQueueVisibility() {
      const queuedRows = Array.from(list.querySelectorAll('[data-local-upload][data-status="queued"]'));
      const completedRows = Array.from(list.querySelectorAll('[data-local-upload][data-status="completed"]'));
      queuedRows.forEach(function (row, index) { row.hidden = !showAllQueued && index >= visibleQueuedLimit; });
      completedRows.forEach(function (row, index) { row.hidden = !showAllCompleted && index >= visibleCompletedLimit; });
      const queuedToggle = page.querySelector('[data-toggle-queued]');
      const completedToggle = page.querySelector('[data-toggle-completed]');
      if (queuedToggle) {
        const hidden = Math.max(queuedRows.length - visibleQueuedLimit, 0);
        queuedToggle.hidden = !hidden && !showAllQueued;
        queuedToggle.textContent = showAllQueued ? 'Collapse queued' : 'Show ' + hidden + ' more queued';
      }
      if (completedToggle) {
        const hidden = Math.max(completedRows.length - visibleCompletedLimit, 0);
        completedToggle.hidden = !hidden && !showAllCompleted;
        completedToggle.textContent = showAllCompleted ? 'Collapse completed' : 'Show ' + hidden + ' more completed';
      }
    }
    function counts() {
      const batch = page.querySelector('[data-batch-progress]');
      const localRows = list.querySelectorAll('[data-local-upload]');
      if (batch) {
        const total = localRows.length;
        const completed = list.querySelectorAll('[data-local-upload][data-status="completed"]').length;
        const failed = list.querySelectorAll('[data-local-upload][data-status="failed"]').length;
        const uploading = list.querySelectorAll('[data-local-upload][data-status="uploading"]').length;
        const queued = list.querySelectorAll('[data-local-upload][data-status="queued"]').length;
        const percent = total ? Math.round(completed / total * 100) : 0;
        batch.hidden = !total;
        batch.querySelector('[data-batch-done]').textContent = completed;
        batch.querySelector('[data-batch-total]').textContent = total;
        batch.querySelector('[data-batch-percent]').textContent = percent + '%';
        batch.querySelector('[data-batch-uploading]').textContent = uploading;
        batch.querySelector('[data-batch-queued]').textContent = queued;
        batch.querySelector('[data-batch-completed]').textContent = completed;
        batch.querySelector('[data-batch-failed]').textContent = failed;
        const bar = batch.querySelector('[data-batch-progress-bar]');
        bar.value = percent; bar.textContent = percent + '%';
      }
      ['uploading', 'queued', 'completed', 'failed'].forEach(function (status) {
        const target = page.querySelector('[data-count="' + status + '"]');
        if (target) target.textContent = list.querySelectorAll('[data-status="' + status + '"]').length;
      });
      const clear = page.querySelector('[data-clear-completed]');
      if (clear) clear.hidden = !list.querySelector('[data-status="completed"]');
      applyQueueVisibility();
    }
    function sortQueueRows() {
      const rows = Array.from(list.querySelectorAll('[data-local-upload]'));
      const rank = {uploading: 0, queued: 1, failed: 2, completed: 3};
      rows.sort(function (a, b) {
        const statusDiff = (rank[a.dataset.status] ?? 9) - (rank[b.dataset.status] ?? 9);
        if (statusDiff) return statusDiff;
        if (a.dataset.status === 'completed') {
          return Number(b.dataset.completedAt || 0) - Number(a.dataset.completedAt || 0);
        }
        return Number(a.dataset.queueOrder || 0) - Number(b.dataset.queueOrder || 0);
      });
      rows.forEach(function (row) { list.append(row); });
    }
    function setStatus(row, status) {
      row.className = 'lp-upload-row is-' + status; row.dataset.status = status;
      if (status === 'completed') row.dataset.completedAt = String(Date.now());
      sortQueueRows(); counts();
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
      row.dataset.status = 'queued'; row.dataset.localUpload = 'true'; row.dataset.queueOrder = String(Date.now() + Math.random());
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
    function apiJson(url, payload, signal) {
      return fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        signal: signal,
        headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/json'},
        body: JSON.stringify(payload || {})
      }).then(async function (response) {
        let body = {};
        try { body = await response.json(); } catch (_) {}
        if (!response.ok) throw new Error(body.error || 'The upload request failed.');
        return body;
      });
    }
    function multipartUrl(uploadId, action) {
      return page.dataset.multipartBaseUrl.replace(/initiate\/$/, uploadId + '/' + action + '/');
    }
    function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }
    function resumeKey(job) {
      return ['lumispixel-upload-v1', job.galleryId, job.file.name, job.file.size, job.file.lastModified].join(':');
    }
    function savedUpload(job) {
      try { return JSON.parse(localStorage.getItem(resumeKey(job)) || 'null'); } catch (_) { return null; }
    }
    function saveUpload(job, value) {
      try { localStorage.setItem(resumeKey(job), JSON.stringify(value)); } catch (_) {}
    }
    function forgetUpload(job) {
      try { localStorage.removeItem(resumeKey(job)); } catch (_) {}
    }
    async function uploadPartWithRetry(url, blob, signal, onProgress) {
      const maxAttempts = 4;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          return await new Promise(function (resolve, reject) {
            const xhr = new XMLHttpRequest();
            xhr.open('PUT', url);
            xhr.upload.onprogress = function (event) { if (event.lengthComputable) onProgress(event.loaded); };
            xhr.onload = function () {
              if (xhr.status >= 200 && xhr.status < 300) {
                const etag = xhr.getResponseHeader('ETag');
                if (!etag) reject(new Error('Storage did not return an ETag.'));
                else resolve(etag);
              } else reject(new Error('Storage rejected an upload part.'));
            };
            xhr.onerror = function () { reject(new Error('Network interrupted.')); };
            xhr.onabort = function () { reject(new DOMException('Upload cancelled.', 'AbortError')); };
            if (signal.aborted) { xhr.abort(); return; }
            signal.addEventListener('abort', function () { xhr.abort(); }, {once: true});
            xhr.send(blob);
          });
        } catch (err) {
          if (signal.aborted || err.name === 'AbortError') throw err;
          if (attempt === maxAttempts) throw err;
          await sleep(500 * Math.pow(2, attempt - 1));
        }
      }
    }
    async function directMultipartUpload(job, updateProgress, signal) {
      const file = job.file;
      let init = null;
      const saved = savedUpload(job);
      if (saved && saved.upload) {
        try {
          init = await apiJson(multipartUrl(saved.upload, 'resume'), {}, signal);
          if (Number(init.gallery) !== Number(job.galleryId) || init.name !== file.name ||
              Number(init.size) !== file.size || init.content_type !== file.type) {
            init = null;
            forgetUpload(job);
          }
        } catch (_) {
          forgetUpload(job);
          init = null;
        }
      }
      if (!init) {
        init = await apiJson(page.dataset.multipartInitUrl, {
          gallery: job.galleryId, name: file.name, content_type: file.type, size: file.size
        }, signal);
        saveUpload(job, {upload: init.upload});
      }
      job.multipartId = init.upload;
      const partSize = Math.max(Number(init.part_size) || 5 * 1024 * 1024, 5 * 1024 * 1024);
      const totalParts = Math.ceil(file.size / partSize);
      if (totalParts > Number(init.max_parts || 10000)) throw new Error('This file requires too many upload parts.');
      const loaded = new Array(totalParts).fill(0);
      const completed = new Array(totalParts);
      (init.parts || []).forEach(function (part) {
        const index = Number(part.part_number) - 1;
        if (index >= 0 && index < totalParts) {
          loaded[index] = Number(part.size) || Math.min(partSize, file.size - index * partSize);
          completed[index] = {part_number: Number(part.part_number), etag: part.etag};
        }
      });
      updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size);
      const remaining = [];
      for (let index = 0; index < totalParts; index += 1) if (!completed[index]) remaining.push(index);
      let cursor = 0;
      function report(partIndex, bytes) {
        loaded[partIndex] = bytes;
        updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size);
      }
      async function worker() {
        while (true) {
          const position = cursor++;
          if (position >= remaining.length) return;
          const index = remaining[position], partNumber = index + 1;
          const start = index * partSize, end = Math.min(start + partSize, file.size);
          const signed = await apiJson(multipartUrl(init.upload, 'part'), {part_number: partNumber}, signal);
          const etag = await uploadPartWithRetry(signed.url, file.slice(start, end), signal, function (bytes) { report(index, bytes); });
          loaded[index] = end - start;
          completed[index] = {part_number: partNumber, etag: etag};
          updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size);
        }
      }
      const partConcurrency = Math.min(4, Math.max(remaining.length, 1));
      await Promise.all(Array.from({length: partConcurrency}, worker));
      const result = await apiJson(multipartUrl(init.upload, 'complete'), {parts: completed}, signal);
      forgetUpload(job);
      return result;
    }
    function upload(job) {
      const row = job.row, file = job.file;
      active += 1; setStatus(row, 'uploading');
      const state = row.querySelector('.lp-file-state'); state.querySelector('strong').textContent = 'Uploading'; state.querySelector('span').textContent = 'Starting…';
      const slot = row.querySelector('[data-progress-slot]');
      slot.innerHTML = '<div class="lp-progress-copy"><span data-percent>0%</span><span data-transfer></span></div><progress max="100" value="0"></progress>';
      const progress = slot.querySelector('progress'); progress.setAttribute('aria-label', file.name + ': Uploading, 0 percent');
      const actions = row.querySelector('.lp-file-actions'); actions.innerHTML = '<button type="button" data-cancel aria-label="Cancel ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
      const controller = new AbortController(), started = performance.now(); let lastPaint = 0;
      function paint(loaded, total) {
        const now = performance.now(); if (now - lastPaint < 100 && loaded < total) return; lastPaint = now;
        const percent = Math.min(100, Math.round(loaded / total * 100));
        const elapsed = Math.max((now - started) / 1000, .1), speed = loaded / elapsed;
        progress.value = percent; progress.textContent = percent + '%'; progress.setAttribute('aria-label', file.name + ': Uploading, ' + percent + ' percent');
        slot.querySelector('[data-percent]').textContent = percent + '%';
        const remaining = Math.ceil((total - loaded) / Math.max(speed, 1));
        slot.querySelector('[data-transfer]').textContent = (speed / 1048576).toFixed(1) + ' MB/s · ' + remaining + ' sec remaining';
      }
      function failed(reason) {
        setStatus(row, 'failed'); state.querySelector('strong').textContent = 'Upload failed'; state.querySelector('span').textContent = reason || 'Network interrupted'; slot.replaceChildren();
        actions.innerHTML = '<button type="button" data-retry aria-label="Retry ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-arrow-clockwise" aria-hidden="true"></i></button><button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
        actions.querySelector('[data-retry]').onclick = function () { setStatus(row, 'queued'); state.querySelector('strong').textContent = 'Queued'; state.querySelector('span').textContent = 'Waiting to upload'; actions.innerHTML = '<button type="button" data-remove aria-label="Remove queued file"><i class="bi bi-x-lg" aria-hidden="true"></i></button>'; pending.push(job); pump(); };
        actions.querySelector('[data-remove]').onclick = function () { removeRow(row); finishCheck(); };
      }
      actions.querySelector('[data-cancel]').onclick = function () {
        controller.abort();
        if (job.multipartId) {
          apiJson(multipartUrl(job.multipartId, 'abort'), {}, undefined).catch(function () {});
          forgetUpload(job);
        }
      };
      directMultipartUpload(job, paint, controller.signal).then(function () {
        active -= 1; paint(file.size, file.size);
        setStatus(row, 'completed'); availableStorage -= file.size; state.querySelector('strong').textContent = 'Uploaded'; state.querySelector('span').textContent = 'Upload complete';
        slot.innerHTML = '<div class="lp-upload-success"><i class="bi bi-check2-circle" aria-hidden="true"></i>100%</div>';
        actions.innerHTML = '<button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + ' from queue"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
        actions.querySelector('[data-remove]').onclick = function () { removeRow(row); };
        pump();
      }).catch(function (err) {
        active -= 1;
        if (controller.signal.aborted) removeRow(row);
        else failed(err.message || 'The upload could not be completed.');
        pump();
      });
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
    page.querySelector('[data-toggle-queued]')?.addEventListener('click', function () { showAllQueued = !showAllQueued; applyQueueVisibility(); });
    page.querySelector('[data-toggle-completed]')?.addEventListener('click', function () { showAllCompleted = !showAllCompleted; applyQueueVisibility(); });
    page.querySelector('[data-clear-completed]')?.addEventListener('click', async function (event) {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.clearCompletedUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!response.ok) throw new Error('Completed uploads could not be cleared.');
        // Dismiss both server-rendered history and current-session rows. This never deletes photos.
        list.querySelectorAll('[data-status="completed"]').forEach(function (row) {
          if (row.matches('[data-local-upload]')) removeRow(row);
          else row.remove();
        });
        completion.hidden = true;
        counts();
      } catch (err) {
        error.textContent = err.message || 'Completed uploads could not be cleared.';
      } finally {
        button.disabled = false;
      }
    });
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
