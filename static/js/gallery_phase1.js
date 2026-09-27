(function () {
  'use strict';
  function csrf() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    return decodeURIComponent((document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '');
  }
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
      }
      directMultipartUpload(job, paint, controller.signal).then(function (result) {
        setStatus(row, 'completed'); state.querySelector('strong').textContent = 'Uploaded'; state.querySelector('span').textContent = 'Upload complete'; progress.value = 100; progress.textContent = '100%'; slot.querySelector('[data-percent]').textContent = '100%'; slot.querySelector('[data-transfer]').textContent = 'Complete';
        actions.innerHTML = '<button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
        row.dataset.uploadId = result.photo || '';
      }).catch(function (err) {
        if (err.name === 'AbortError') { removeRow(row); return; }
        failed(err.message);
      }).finally(function () { active -= 1; pump(); });
      actions.querySelector('[data-cancel]').addEventListener('click', function () {
        controller.abort();
        if (job.multipartId) apiJson(multipartUrl(job.multipartId, 'abort'), {}).catch(function () {});
      });
    }
    function queueFiles(files) {
      error.textContent = '';
      const galleryId = gallery.value;
      if (!galleryId) { error.textContent = 'Select a gallery before adding photos.'; return; }
      const option = gallery.selectedOptions[0], accepted = ['image/jpeg', 'image/png', 'image/webp'];
      Array.from(files).forEach(function (file) {
        if (!accepted.includes(file.type)) { error.textContent = file.name + ': Unsupported format.'; return; }
        if (file.size > 25 * 1024 * 1024) { error.textContent = file.name + ': File exceeds the 25 MB limit.'; return; }
        if (file.size > availableStorage) { error.textContent = file.name + ': Not enough storage remaining.'; return; }
        availableStorage -= file.size;
        const row = createRow(file, option.dataset.name); list.querySelector('[data-queue-empty]')?.remove();
        list.append(row); pending.push({file: file, row: row, galleryId: galleryId}); counts();
      });
      input.value = ''; pump();
    }
    input.addEventListener('change', function () { queueFiles(input.files); });
    drop.addEventListener('click', function () { if (!input.disabled) input.click(); });
    drop.addEventListener('keydown', function (event) { if ((event.key === 'Enter' || event.key === ' ') && !input.disabled) { event.preventDefault(); input.click(); } });
    ['dragenter', 'dragover'].forEach(function (name) { drop.addEventListener(name, function (event) { event.preventDefault(); if (!input.disabled) drop.classList.add('is-dragging'); }); });
    ['dragleave', 'drop'].forEach(function (name) { drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.remove('is-dragging'); }); });
    drop.addEventListener('drop', function (event) { if (!input.disabled) queueFiles(event.dataTransfer.files); });
    gallery.addEventListener('change', setDestination); setDestination(); counts();
    page.querySelector('[data-change-gallery]')?.addEventListener('click', function () { gallery.value = ''; setDestination(); gallery.focus(); });
    search?.addEventListener('input', function () {
      const term = search.value.trim().toLowerCase();
      Array.from(gallery.options).forEach(function (option, index) {
        if (!index) return;
        option.hidden = term && !option.textContent.toLowerCase().includes(term);
      });
    });
    page.querySelector('[data-clear-completed]')?.addEventListener('click', function (event) {
      const button = event.currentTarget;
      fetch(button.dataset.clearCompletedUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}}).then(function (response) {
        if (!response.ok) throw new Error('Could not clear completed uploads.');
        list.querySelectorAll('[data-status="completed"]').forEach(function (row) { removeRow(row); });
      }).catch(function (err) { error.textContent = err.message; });
    });
    list.addEventListener('click', function (event) {
      const button = event.target.closest('button'); if (!button) return;
      const row = button.closest('.lp-upload-row'); if (!row) return;
      if (button.matches('[data-remove]') && row.dataset.localUpload) { removeRow(row); return; }
      if (button.matches('[data-retry]')) { setStatus(row, 'queued'); pending.push({file: row._file, row: row, galleryId: gallery.value}); pump(); return; }
      if (button.dataset.serverAction) {
        const form = new FormData(); form.append('action', button.dataset.serverAction);
        fetch(button.dataset.actionUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form}).then(function (response) {
          if (!response.ok) throw new Error('The queue action failed.');
          if (button.dataset.serverAction === 'remove') removeRow(row); else window.location.reload();
        }).catch(function (err) { error.textContent = err.message; });
      }
    });
    page.querySelector('[data-toggle-queued]')?.addEventListener('click', function () { showAllQueued = !showAllQueued; applyQueueVisibility(); });
    page.querySelector('[data-toggle-completed]')?.addEventListener('click', function () { showAllCompleted = !showAllCompleted; applyQueueVisibility(); });
    page.querySelector('[data-upload-more]')?.addEventListener('click', function () { completion.hidden = true; input.click(); });
  }
})();