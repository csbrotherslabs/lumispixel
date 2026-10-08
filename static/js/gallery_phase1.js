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
    const retryAll = page.querySelector('[data-retry-all-failed]');
    let retryingAll = false;
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
      if (retryAll) {
        retryAll.hidden = !list.querySelector('[data-status="failed"]');
        retryAll.disabled = retryingAll;
      }
      applyQueueVisibility();
    }
    function sortQueueRows() {
      const rows = Array.from(list.querySelectorAll('[data-local-upload]'));
      const rank = {uploading: 0, queued: 1, failed: 2, completed: 3};
      rows.sort(function (a, b) {
        const statusDiff = (rank[a.dataset.status] ?? 9) - (rank[b.dataset.status] ?? 9);
        if (statusDiff) return statusDiff;
        if (a.dataset.status === 'completed') return Number(b.dataset.completedAt || 0) - Number(a.dataset.completedAt || 0);
        return Number(a.dataset.queueOrder || 0) - Number(b.dataset.queueOrder || 0);
      });
      rows.forEach(function (row) { list.append(row); });
    }
    function setStatus(row, status) {
      row.className = 'lp-upload-row is-' + status; row.dataset.status = status;
      if (status === 'completed') row.dataset.completedAt = String(Date.now());
      sortQueueRows(); counts();
    }
    function releasePreview(row) { if (row.dataset.previewUrl) { URL.revokeObjectURL(row.dataset.previewUrl); delete row.dataset.previewUrl; } }
    function removeRow(row) { releasePreview(row); row.remove(); counts(); }
    function finishCheck() {
      if (active || pending.length || !list.querySelector('[data-local-upload]')) return;
      if (list.querySelector('[data-local-upload][data-status="failed"]')) return;
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
      // Keep the browser File object on the row for in-page retry. File objects cannot
      // be reconstructed from DOM metadata after an interrupted upload.
      row._file = file;
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
      return fetch(url, {method: 'POST', credentials: 'same-origin', signal: signal, headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/json'}, body: JSON.stringify(payload || {})}).then(async function (response) {
        let body = {}; try { body = await response.json(); } catch (_) {}
        if (!response.ok) throw new Error(body.error || 'The upload request failed.');
        return body;
      });
    }
    function multipartUrl(uploadId, action) { return page.dataset.multipartBaseUrl.replace(/initiate\/$/, uploadId + '/' + action + '/'); }
    function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }
    function resumeKey(job) { return ['lumispixel-upload-v1', job.galleryId, job.file.name, job.file.size, job.file.lastModified].join(':'); }
    function savedUpload(job) { try { return JSON.parse(localStorage.getItem(resumeKey(job)) || 'null'); } catch (_) { return null; } }
    function saveUpload(job, value) { try { localStorage.setItem(resumeKey(job), JSON.stringify(value)); } catch (_) {} }
    function forgetUpload(job) { try { localStorage.removeItem(resumeKey(job)); } catch (_) {} }
    async function uploadPartWithRetry(url, blob, signal, onProgress) {
      const maxAttempts = 4;
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          return await new Promise(function (resolve, reject) {
            const xhr = new XMLHttpRequest(); xhr.open('PUT', url);
            xhr.upload.onprogress = function (event) { if (event.lengthComputable) onProgress(event.loaded); };
            xhr.onload = function () { if (xhr.status >= 200 && xhr.status < 300) { const etag = xhr.getResponseHeader('ETag'); if (!etag) reject(new Error('Storage did not return an ETag.')); else resolve(etag); } else reject(new Error('Storage rejected an upload part.')); };
            xhr.onerror = function () { reject(new Error('Network interrupted.')); };
            xhr.onabort = function () { reject(new DOMException('Upload cancelled.', 'AbortError')); };
            if (signal.aborted) { xhr.abort(); return; }
            signal.addEventListener('abort', function () { xhr.abort(); }, {once: true}); xhr.send(blob);
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
      if (!file) throw new Error('The original file is no longer available. Please add it again.');
      let init = null;
      const saved = savedUpload(job);
      if (saved && saved.upload) {
        try {
          init = await apiJson(multipartUrl(saved.upload, 'resume'), {}, signal);
          if (Number(init.gallery) !== Number(job.galleryId) || init.name !== file.name || Number(init.size) !== file.size || init.content_type !== file.type) {
            init = null; forgetUpload(job);
          }
        } catch (_) { forgetUpload(job); init = null; }
      }
      if (!init) {
        init = await apiJson(page.dataset.multipartInitUrl, {gallery: job.galleryId, name: file.name, content_type: file.type, size: file.size}, signal);
        saveUpload(job, {upload: init.upload});
      }
      job.multipartId = init.upload;
      const partSize = Math.max(Number(init.part_size) || 5 * 1024 * 1024, 5 * 1024 * 1024);
      const totalParts = Math.ceil(file.size / partSize);
      if (totalParts > Number(init.max_parts || 10000)) throw new Error('This file requires too many upload parts.');
      const loaded = new Array(totalParts).fill(0), completed = new Array(totalParts);
      (init.parts || []).forEach(function (part) {
        const index = Number(part.part_number) - 1;
        if (index >= 0 && index < totalParts) { loaded[index] = Number(part.size) || Math.min(partSize, file.size - index * partSize); completed[index] = {part_number: Number(part.part_number), etag: part.etag}; }
      });
      updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size);
      const remaining = []; for (let index = 0; index < totalParts; index += 1) if (!completed[index]) remaining.push(index);
      let cursor = 0;
      function report(partIndex, bytes) { loaded[partIndex] = bytes; updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size); }
      async function worker() {
        while (true) {
          const position = cursor++; if (position >= remaining.length) return;
          const index = remaining[position], partNumber = index + 1, start = index * partSize, end = Math.min(start + partSize, file.size);
          const signed = await apiJson(multipartUrl(init.upload, 'part'), {part_number: partNumber}, signal);
          const etag = await uploadPartWithRetry(signed.url, file.slice(start, end), signal, function (bytes) { report(index, bytes); });
          loaded[index] = end - start; completed[index] = {part_number: partNumber, etag: etag}; updateProgress(loaded.reduce(function (sum, value) { return sum + value; }, 0), file.size);
        }
      }
      const partConcurrency = Math.min(4, Math.max(remaining.length, 1)); await Promise.all(Array.from({length: partConcurrency}, worker));
      const result = await apiJson(multipartUrl(init.upload, 'complete'), {parts: completed}, signal); forgetUpload(job); return result;
    }
    function upload(job) {
      const row = job.row, file = job.file;
      if (!file) {
        setStatus(row, 'failed');
        const missingState = row.querySelector('.lp-file-state');
        missingState.querySelector('strong').textContent = 'Upload failed';
        missingState.querySelector('span').textContent = 'The original file is no longer available. Please add it again.';
        return;
      }
      active += 1; setStatus(row, 'uploading');
      const state = row.querySelector('.lp-file-state'); state.querySelector('strong').textContent = 'Uploading'; state.querySelector('span').textContent = 'Starting…';
      const slot = row.querySelector('[data-progress-slot]'); slot.innerHTML = '<div class="lp-progress-copy"><span data-percent>0%</span><span data-transfer></span></div><progress max="100" value="0"></progress>';
      const progress = slot.querySelector('progress'); progress.setAttribute('aria-label', file.name + ': Uploading, 0 percent');
      const actions = row.querySelector('.lp-file-actions'); actions.innerHTML = '<button type="button" data-cancel aria-label="Cancel ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
      const controller = new AbortController(), started = performance.now(); let lastPaint = 0;
      function paint(loaded, total) {
        const now = performance.now(); if (now - lastPaint < 100 && loaded < total) return; lastPaint = now;
        const percent = Math.min(100, Math.round(loaded / total * 100)), elapsed = Math.max((now - started) / 1000, .1), speed = loaded / elapsed;
        progress.value = percent; progress.textContent = percent + '%'; progress.setAttribute('aria-label', file.name + ': Uploading, ' + percent + ' percent');
        slot.querySelector('[data-percent]').textContent = percent + '%';
        const remaining = Math.ceil((total - loaded) / Math.max(speed, 1)); slot.querySelector('[data-transfer]').textContent = (speed / 1048576).toFixed(1) + ' MB/s · ' + remaining + ' sec remaining';
      }
      function failed(reason) {
        setStatus(row, 'failed'); state.querySelector('strong').textContent = 'Upload failed'; state.querySelector('span').textContent = reason || 'Network interrupted'; slot.replaceChildren();
        actions.innerHTML = '<button type="button" data-retry aria-label="Retry ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-arrow-clockwise" aria-hidden="true"></i></button><button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>';
      }
      directMultipartUpload(job, paint, controller.signal).then(function (result) {
        setStatus(row, 'completed'); state.querySelector('strong').textContent = 'Uploaded'; state.querySelector('span').textContent = 'Upload complete'; progress.value = 100; progress.textContent = '100%'; slot.querySelector('[data-percent]').textContent = '100%'; slot.querySelector('[data-transfer]').textContent = 'Complete';
        actions.innerHTML = '<button type="button" data-remove aria-label="Remove ' + file.name.replace(/["<>]/g, '') + '"><i class="bi bi-x-lg" aria-hidden="true"></i></button>'; row.dataset.uploadId = result.photo || '';
      }).catch(function (err) { if (err.name === 'AbortError') { removeRow(row); return; } failed(err.message); }).finally(function () { active -= 1; pump(); });
      actions.querySelector('[data-cancel]').addEventListener('click', function () { controller.abort(); if (job.multipartId) apiJson(multipartUrl(job.multipartId, 'abort'), {}).catch(function () {}); });
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
        const row = createRow(file, option.dataset.name); row.dataset.galleryId = galleryId; list.querySelector('[data-queue-empty]')?.remove(); list.append(row); pending.push({file: file, row: row, galleryId: galleryId}); counts();
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
    search?.addEventListener('input', function () { const term = search.value.trim().toLowerCase(); Array.from(gallery.options).forEach(function (option, index) { if (!index) return; option.hidden = term && !option.textContent.toLowerCase().includes(term); }); });
    page.querySelector('[data-clear-completed]')?.addEventListener('click', function (event) {
      const button = event.currentTarget;
      fetch(button.dataset.clearCompletedUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}}).then(function (response) { if (!response.ok) throw new Error('Could not clear completed uploads.'); list.querySelectorAll('[data-status="completed"]').forEach(function (row) { removeRow(row); }); }).catch(function (err) { error.textContent = err.message; });
    });
    function queueRetry(row) {
      if (row.dataset.status !== 'failed') return false;
      if (!row._file) {
        row.querySelector('.lp-file-state strong').textContent = 'Upload failed';
        row.querySelector('.lp-file-state span').textContent = 'The original file is no longer available. Please add it again.';
        return false;
      }
      row.querySelector('[data-retry]').disabled = true;
      setStatus(row, 'queued');
      row.querySelector('.lp-file-state strong').textContent = 'Queued';
      row.querySelector('.lp-file-state span').textContent = 'Waiting to retry';
      pending.push({file: row._file, row: row, galleryId: row.dataset.galleryId || gallery.value});
      return true;
    }
    async function retryServerRow(row, button) {
      if (button.disabled || row.dataset.status !== 'failed') return false;
      button.disabled = true;
      try {
        const form = new FormData(); form.append('action', 'retry');
        const response = await fetch(button.dataset.actionUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form});
        if (!response.ok) throw new Error('The queue action failed.');
        setStatus(row, 'queued');
        row.querySelector('.lp-file-state strong').textContent = 'Queued';
        row.querySelector('.lp-file-state span').textContent = 'Waiting to retry';
        return true;
      } catch (err) {
        error.textContent = err.message;
        button.disabled = false;
        return false;
      }
    }
    retryAll?.addEventListener('click', async function () {
      if (retryingAll) return;
      retryingAll = true; retryAll.disabled = true; retryAll.setAttribute('aria-busy', 'true');
      error.textContent = '';
      const failedRows = Array.from(list.querySelectorAll('[data-status="failed"]'));
      const serverRows = [];
      let retried = 0, skipped = 0;
      failedRows.forEach(function (row) {
        if (row.dataset.localUpload) {
          if (queueRetry(row)) retried += 1; else skipped += 1;
        } else {
          const button = row.querySelector('[data-server-action="retry"]');
          if (button) serverRows.push({row: row, button: button}); else skipped += 1;
        }
      });
      pump();
      let cursor = 0;
      async function worker() {
        while (cursor < serverRows.length) {
          const item = serverRows[cursor++];
          if (await retryServerRow(item.row, item.button)) retried += 1; else skipped += 1;
        }
      }
      try {
        await Promise.all(Array.from({length: Math.min(concurrency, serverRows.length)}, worker));
        if (skipped) error.textContent = skipped + ' upload(s) could not be retried. Re-add any original files that are no longer available.';
        const announcer = page.querySelector('[data-queue-announcer]');
        if (announcer) announcer.textContent = 'Retrying ' + retried + ' failed upload(s).';
      } finally {
        retryingAll = false; retryAll.removeAttribute('aria-busy'); counts();
      }
    });
    list.addEventListener('click', function (event) {
      const button = event.target.closest('button'); if (!button) return;
      const row = button.closest('.lp-upload-row'); if (!row) return;
      if (button.matches('[data-remove]') && row.dataset.localUpload) { removeRow(row); return; }
      if (button.matches('[data-retry]')) {
        if (queueRetry(row)) pump();
        return;
      }
      if (button.dataset.serverAction) {
        if (button.disabled) return;
        if (button.dataset.serverAction === 'retry') {
          retryServerRow(row, button).then(function (saved) {
            if (saved && !active && !pending.length) window.location.reload();
          });
          return;
        }
        const form = new FormData(); form.append('action', button.dataset.serverAction);
        fetch(button.dataset.actionUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}, body: form}).then(function (response) { if (!response.ok) throw new Error('The queue action failed.'); if (button.dataset.serverAction === 'remove') removeRow(row); else window.location.reload(); }).catch(function (err) { error.textContent = err.message; });
      }
    });
    page.querySelector('[data-toggle-queued]')?.addEventListener('click', function () { showAllQueued = !showAllQueued; applyQueueVisibility(); });
    page.querySelector('[data-toggle-completed]')?.addEventListener('click', function () { showAllCompleted = !showAllCompleted; applyQueueVisibility(); });
    page.querySelector('[data-upload-more]')?.addEventListener('click', function () { completion.hidden = true; input.click(); });
  }
  const size=document.querySelector('[data-grid-size]'),grid=document.querySelector('[data-photo-grid]');if(size&&grid)size.oninput=function(){grid.style.setProperty('--photo-size',size.value+'px');};
  const checks=Array.from(document.querySelectorAll('[data-photo-check]')),all=document.querySelector('[data-photo-select-all]'),bulk=document.querySelector('[data-photo-bulk]');
  function selectedPhotoIds(){return checks.filter(function(c){return c.checked&&c.isConnected;}).map(function(c){return Number(c.value);});}
  function update(){const live=checks.filter(function(c){return c.isConnected;}),n=live.filter(function(c){return c.checked;}).length;if(bulk){bulk.hidden=!n;bulk.querySelector('[data-photo-count]').textContent=n;}if(all){all.checked=Boolean(live.length)&&n===live.length;all.indeterminate=n>0&&n<live.length;}}
  if(all)all.onchange=function(){checks.forEach(function(c){if(c.isConnected)c.checked=all.checked;});update();};
  bulk?.querySelector('[data-bulk-select-all]')?.addEventListener('click',function(){checks.forEach(function(c){if(c.isConnected)c.checked=true;});update();});
  bulk?.querySelector('[data-bulk-clear]')?.addEventListener('click',function(){checks.forEach(function(c){if(c.isConnected)c.checked=false;});update();});
  checks.forEach(function(c){c.onchange=update;});document.querySelectorAll('[data-select-photo]').forEach(function(b){b.onclick=function(){const c=b.closest('article').querySelector('[data-photo-check]');c.checked=!c.checked;update();};});
  async function bulkJson(action, extra){
    const response=await fetch(bulk.dataset.bulkActionUrl,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(Object.assign({action:action,photo_ids:selectedPhotoIds()},extra||{}))});
    let body={};try{body=await response.json();}catch(_){}
    if(!response.ok)throw new Error(body.error||'The bulk action could not be completed.');return body;
  }
  function removeSelectedCards(){checks.forEach(function(c){if(c.checked&&c.isConnected)c.closest('article')?.remove();});update();}
  if(bulk){
    const deleteDialog=document.querySelector('[data-bulk-delete-dialog]'),moveDialog=document.querySelector('[data-bulk-move-dialog]'),visibilityDialog=document.querySelector('[data-bulk-visibility-dialog]');
    bulk.querySelector('[data-bulk-delete]')?.addEventListener('click',function(){deleteDialog.querySelector('[data-bulk-delete-count]').textContent=selectedPhotoIds().length;deleteDialog.showModal();});
    document.querySelectorAll('[data-bulk-dialog-cancel]').forEach(function(button){button.addEventListener('click',function(){button.closest('dialog').close();});});
    deleteDialog?.querySelector('[data-bulk-delete-confirm]')?.addEventListener('click',async function(event){const button=event.currentTarget;button.disabled=true;try{await bulkJson('delete');removeSelectedCards();deleteDialog.close();}catch(err){alert(err.message);}finally{button.disabled=false;}});
    function openMoveDialog(ids){moveDialog.dataset.photoIds=ids.join(',');const count=ids.length;moveDialog.querySelector('[data-bulk-move-count]').textContent=count;moveDialog.querySelector('[data-bulk-move-plural]').textContent=count===1?'':'s';moveDialog.querySelector('[data-bulk-album]').value='';moveDialog.showModal();}
    bulk.querySelector('[data-bulk-move]')?.addEventListener('click',function(){openMoveDialog(selectedPhotoIds());});
    document.querySelectorAll('[data-photo-move]').forEach(function(button){button.addEventListener('click',function(){openMoveDialog([Number(button.dataset.photoId)]);});});
    moveDialog?.querySelector('[data-bulk-move-confirm]')?.addEventListener('click',async function(event){const album=moveDialog.querySelector('[data-bulk-album]').value;if(!album){alert('Choose an album.');return;}const button=event.currentTarget;button.disabled=true;try{const moveIds=(moveDialog.dataset.photoIds||'').split(',').filter(Boolean).map(Number);const response=await fetch(bulk.dataset.bulkActionUrl,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({action:'move',photo_ids:moveIds,album_id:Number(album)})});let body={};try{body=await response.json();}catch(_){}if(!response.ok)throw new Error(body.error||'The photos could not be moved.');checks.forEach(function(c){if(moveIds.includes(Number(c.value)))c.checked=false;});update();moveDialog.close();}catch(err){alert(err.message);}finally{button.disabled=false;}});
    bulk.querySelector('[data-bulk-visibility]')?.addEventListener('click',function(){visibilityDialog.showModal();});
    visibilityDialog?.querySelectorAll('[data-bulk-visible]').forEach(function(button){button.addEventListener('click',async function(){button.disabled=true;try{await bulkJson('visibility',{visible:button.dataset.bulkVisible==='true'});checks.forEach(function(c){c.checked=false;});update();visibilityDialog.close();}catch(err){alert(err.message);}finally{button.disabled=false;}});});
    bulk.querySelector('[data-bulk-download]')?.addEventListener('click',function(){const ids=selectedPhotoIds();if(!ids.length)return;const form=document.createElement('form');form.method='POST';form.action=bulk.dataset.bulkDownloadUrl;form.hidden=true;const token=document.createElement('input');token.type='hidden';token.name='csrfmiddlewaretoken';token.value=csrf();form.append(token);ids.forEach(function(id){const input=document.createElement('input');input.type='hidden';input.name='photo_ids';input.value=id;form.append(input);});document.body.append(form);form.submit();form.remove();});
  }
  document.querySelectorAll('[data-photo-action]').forEach(function (button) {
    button.addEventListener('click', async function () {
      if (button.disabled) return;
      const action = button.dataset.photoAction;
      if (action === 'delete' && !confirm('Delete this photo permanently?')) return;
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.actionUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({action: action}).toString()
        });
        let body = {}; try { body = await response.json(); } catch (_) {}
        if (!response.ok) throw new Error(body.error || 'The photo action could not be completed.');
        if (action === 'delete') { button.closest('article').remove(); update(); }
        if (action === 'cover') window.location.reload();
      } catch (err) { alert(err.message); }
      finally { button.disabled = false; }
    });
  });
  const previewDialog=document.querySelector('[data-photo-preview-dialog]');
  if(previewDialog){
    const previewImage=previewDialog.querySelector('[data-photo-preview-image]'),previewTitle=previewDialog.querySelector('[data-photo-preview-title]');
    function setPreviewSize(size){previewDialog.classList.remove('is-compact','is-large','is-fullscreen');previewDialog.classList.add('is-'+size);}
    document.querySelectorAll('[data-photo-preview]').forEach(function(button){button.addEventListener('click',function(){previewImage.src=button.dataset.previewUrl;previewImage.alt=button.dataset.previewName||'Gallery photo';previewTitle.textContent=button.dataset.previewName||'';setPreviewSize('large');previewDialog.showModal();});});
    previewDialog.querySelector('[data-preview-close]')?.addEventListener('click',function(){previewDialog.close();});
    previewDialog.querySelectorAll('[data-preview-size]').forEach(function(button){button.addEventListener('click',function(){setPreviewSize(button.dataset.previewSize);});});
    previewDialog.addEventListener('click',function(event){if(event.target===previewDialog)previewDialog.close();});
    previewDialog.addEventListener('close',function(){previewImage.removeAttribute('src');});
  }
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

/* Touch and keyboard access to the photo card action strip. */
(function () {
  const grid = document.querySelector('.lp-photo-cards');
  if (!grid) return;
  function closeTools(card) {
    card.classList.remove('is-tools-open');
    card.querySelector('[data-photo-tools-toggle]').setAttribute('aria-expanded', 'false');
  }
  grid.querySelectorAll('[data-photo-tools-toggle]').forEach(function (button) {
    button.addEventListener('click', function () {
      const card = button.closest('.lp-photo-card');
      const opening = !card.classList.contains('is-tools-open');
      grid.querySelectorAll('.is-tools-open').forEach(closeTools);
      if (opening) { card.classList.add('is-tools-open'); button.setAttribute('aria-expanded', 'true'); }
    });
  });
  grid.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    const card = event.target.closest('.lp-photo-card');
    if (card && card.classList.contains('is-tools-open')) {
      closeTools(card);
      card.querySelector('[data-photo-tools-toggle]').focus();
    }
  });
  document.addEventListener('click', function (event) {
    grid.querySelectorAll('.is-tools-open').forEach(function (card) {
      if (!card.contains(event.target)) closeTools(card);
    });
  });
})();


// Threaded feedback within the photographer photo preview.
(() => {
  const dialog = document.querySelector('[data-photo-preview-dialog]');
  if (!dialog) return;
  const panel = dialog.querySelector('.lp-preview-comments');
  const list = dialog.querySelector('[data-preview-comments-list]');
  const toggle = dialog.querySelector('[data-preview-comments-toggle]');
  const status = dialog.querySelector('[data-preview-comments-status]');
  const sort = dialog.querySelector('[data-comments-sort]');
  const composer = dialog.querySelector('[data-comment-reply-form]');
  const textarea = composer.querySelector('textarea');
  const send = composer.querySelector('[type=submit]');
  let url = '', createUrl = '', source, controller, version = 0, busy = false, page = '1', replyUrl = '';
  function showPanel(open) {
    panel.hidden = !open;
    dialog.classList.toggle('has-comments', open);
    toggle.setAttribute('aria-expanded', String(open));
  }
  function composerState() {
    send.disabled = busy || !createUrl || !textarea.value.trim();
    textarea.disabled = busy;
    composer.querySelector('[data-reply-cancel]').disabled = busy;
    dialog.querySelector('[data-reply-length]').textContent = textarea.value.length.toLocaleString() + ' / 2,000';
  }
  function cancelReply() {
    composer.hidden = false; replyUrl = ''; textarea.value = '';
    composer.querySelector('[name=action]').value = 'comment';
    dialog.querySelector('[data-composer-label]').textContent = 'Comment on this photo';
    dialog.querySelector('[data-reply-recipient]').hidden = true;
    dialog.querySelector('[data-reply-cancel]').hidden = true;
    dialog.querySelector('[data-composer-input-label]').textContent = 'Write a comment';
    textarea.placeholder = 'Write a comment…';
    dialog.querySelector('[data-composer-submit-label]').textContent = 'Post comment';
    composerState();
  }
  function syncCount(value) {
    const count = value ?? list.querySelector('[data-comment-page]')?.dataset.commentCount;
    if (count === undefined) return;
    dialog.querySelector('[data-preview-comment-count]').textContent = count;
    dialog.querySelector('[data-panel-comment-count]').textContent = count;
    if (source) {
      source.dataset.commentCount = count;
      const metric = source.closest('article')?.querySelector('[data-photo-comment-metric]');
      if (metric) { metric.setAttribute('aria-label', count + ' comments'); metric.lastChild.textContent = count; }
    }
    page = list.querySelector('[data-comment-page]')?.dataset.pageNumber || page;
  }
  function targetUrl(target = url) {
    const targetURL = new URL(target, window.location.href);
    if (targetURL.origin !== window.location.origin) throw new Error('This comment link is unavailable. Refresh the page and try again.');
    targetURL.searchParams.set('sort', sort.value);
    targetURL.searchParams.set('page', page);
    return targetURL;
  }
  function errorState(message) {
    if (list.querySelector('[data-comment-page]')) { status.textContent = message; return; }
    list.replaceChildren();
    const box = document.createElement('div'); box.className = 'lp-preview-comments-empty is-error';
    const title = document.createElement('strong'); title.textContent = 'Comments could not be loaded';
    const text = document.createElement('p'); text.textContent = message;
    const retry = document.createElement('button'); retry.type = 'button'; retry.dataset.commentsRetry = ''; retry.textContent = 'Retry';
    box.append(title, text, retry); list.append(box);
  }
  async function request(target, options = {}) {
    controller?.abort();
    const current = ++version;
    controller = new AbortController();
    list.setAttribute('aria-busy', 'true');
    status.textContent = '';
    if (!options.method && !list.querySelector('[data-comment-page]')) list.textContent = 'Loading comments…';
    try {
      const response = await fetch(targetUrl(target), {credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}, signal: controller.signal, ...options});
      if (!response.ok || response.redirected) {
        let message = response.status === 403 ? 'Your session may have expired. Refresh the page and sign in again.' : response.status === 404 ? 'This photo is no longer available to your workspace.' : 'Please try again. If this continues, refresh the page.';
        if (response.headers.get('content-type')?.includes('application/json')) message = (await response.json()).error || message;
        throw new Error(message);
      }
      const html = await response.text();
      if (current !== version) return false;
      list.innerHTML = html; syncCount();
      status.textContent = options.method === 'POST' ? 'Saved.' : '';
      return true;
    } catch (error) {
      if (error.name !== 'AbortError' && current === version) {
        const message = error instanceof TypeError ? 'Check your connection and try again.' : error.message;
        if (options.method) status.textContent = message + (['reply', 'comment'].includes(options.body?.get('action')) ? ' Your text has been kept.' : ' The reaction could not be confirmed.');
        else errorState(message);
      }
      return false;
    } finally {
      if (current === version) { list.removeAttribute('aria-busy'); busy = false; sort.disabled = false; list.querySelectorAll('button').forEach(b => { b.disabled = false; }); composerState(); }
    }
  }
  document.querySelectorAll('[data-photo-preview]').forEach(button => button.addEventListener('click', () => {
    controller?.abort(); ++version; busy = false; page = '1'; sort.value = 'newest'; sort.disabled = false;
    source = button; url = button.dataset.commentsUrl || ''; createUrl = button.dataset.commentCreateUrl || '';
    list.replaceChildren(); status.textContent = ''; cancelReply();
    dialog.querySelector('[data-comments-photo-name]').textContent = button.dataset.previewName || 'Gallery photo';
    syncCount(button.dataset.commentCount || '0');
    showPanel(false); toggle.disabled = !url;
  }));
  toggle.addEventListener('click', () => {
    showPanel(panel.hidden);
    if (!panel.hidden && !list.querySelector('[data-comment-page]')) request(url);
  });
  dialog.querySelector('[data-preview-comments-close]').addEventListener('click', () => { showPanel(false); toggle.focus(); });
  textarea.addEventListener('input', composerState);
  dialog.querySelector('[data-reply-cancel]').addEventListener('click', () => { cancelReply(); textarea.focus(); });
  sort.addEventListener('change', () => { if (!busy) { page = '1'; list.scrollTop = 0; request(url); } });
  list.addEventListener('click', event => {
    if (busy) return;
    const reply = event.target.closest('[data-comment-reply]');
    if (reply) {
      replyUrl = reply.dataset.replyUrl;
      dialog.querySelector('[data-reply-recipient]').textContent = reply.dataset.replyAuthor;
      dialog.querySelector('[data-reply-recipient]').hidden = false;
      dialog.querySelector('[data-reply-cancel]').hidden = false;
      dialog.querySelector('[data-composer-label]').textContent = 'Replying to ';
      dialog.querySelector('[data-composer-input-label]').textContent = 'Write your reply';
      dialog.querySelector('[data-composer-submit-label]').textContent = 'Send reply';
      composer.querySelector('[name=action]').value = 'reply';
      textarea.placeholder = 'Write your reply…';
      composer.hidden = false; composerState(); textarea.focus(); return;
    }
    if (event.target.closest('[data-comments-retry]')) { request(url); return; }
    const paging = event.target.closest('[data-comments-page]');
    if (paging) { page = paging.dataset.commentsPage; list.scrollTop = 0; request(url); }
  });
  list.addEventListener('submit', async event => {
    const form = event.target.closest('[data-comment-reaction-form]');
    if (!form) return;
    event.preventDefault();
    if (busy || !event.submitter) return;
    const data = new FormData(form);
    data.set(event.submitter.name, event.submitter.value);
    const entryId = form.closest('.lp-preview-comment-entry')?.parentElement.id;
    const reaction = event.submitter.value;
    busy = true; sort.disabled = true; composerState();
    list.querySelectorAll('button').forEach(b => { b.disabled = true; });
    await request(form.action, {method: 'POST', body: data});
    if (entryId) document.getElementById(entryId)?.querySelector('button[value="' + reaction + '"]')?.focus();
  });
  composer.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !createUrl || !textarea.value.trim()) return;
    const draft = textarea.value;
    const data = new FormData(composer);
    busy = true; sort.disabled = true; composerState();
    list.querySelectorAll('button').forEach(b => { b.disabled = true; });
    if (!replyUrl) { page = '1'; sort.value = 'newest'; }
    const current = version + 1;
    const saved = await request(replyUrl || createUrl, {method: 'POST', body: data});
    if (saved && current === version) { cancelReply(); textarea.focus(); }
    else if (current === version) { textarea.value = draft; composerState(); }
  });
  dialog.addEventListener('close', () => { controller?.abort(); ++version; busy = false; list.replaceChildren(); cancelReply(); showPanel(false); });
})();
