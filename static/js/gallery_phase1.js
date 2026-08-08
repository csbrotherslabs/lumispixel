(function () {
  'use strict';
  function csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; }
  const page = document.querySelector('[data-upload-page]');
  if (page) {
    const drop = page.querySelector('[data-upload-drop]'), input = page.querySelector('[data-upload-input]'), gallery = page.querySelector('[data-upload-gallery]'), list = page.querySelector('[data-upload-list]'), error = page.querySelector('[data-upload-error]');
    const picker = page.querySelector('[data-gallery-picker]'), selected = page.querySelector('[data-selected-gallery]'), requirement = page.querySelector('[data-upload-requirement]'), search = page.querySelector('[data-gallery-search]');
    function setDestination() {
      const option = gallery.selectedOptions[0], hasGallery = Boolean(gallery.value);
      picker.hidden = hasGallery; selected.hidden = !hasGallery; input.disabled = !hasGallery;
      drop.classList.toggle('is-disabled', !hasGallery); drop.tabIndex = hasGallery ? 0 : -1; drop.setAttribute('aria-disabled', String(!hasGallery)); requirement.hidden = hasGallery;
      if (!hasGallery) return;
      selected.querySelector('[data-selected-name]').textContent = option.dataset.name;
      selected.querySelector('[data-selected-event]').textContent = option.dataset.event || option.dataset.client || '';
      selected.querySelector('[data-selected-date]').textContent = option.dataset.date || '';
      const thumb = selected.querySelector('[data-selected-thumbnail]');
      thumb.replaceChildren();
      if (option.dataset.thumbnail) { const image = document.createElement('img'); image.src = option.dataset.thumbnail; image.alt = ''; image.width = 64; image.height = 64; thumb.append(image); }
      else { const icon = document.createElement('i'); icon.className = 'bi bi-images'; icon.setAttribute('aria-hidden', 'true'); thumb.append(icon); }
    }
    gallery.addEventListener('change', setDestination);
    page.querySelector('[data-change-gallery]').addEventListener('click', function () { gallery.value = ''; setDestination(); search.focus(); });
    search.addEventListener('input', function () { const query = search.value.trim().toLowerCase(); Array.from(gallery.options).forEach(function (option, index) { option.hidden = index > 0 && !option.textContent.toLowerCase().includes(query); }); });
    setDestination();
    function syncClearButton() { const button = page.querySelector('[data-clear-completed]'); if (button) button.hidden = !list.querySelector('.is-completed'); }
    function queue(files) { error.replaceChildren(); if(!gallery.value){error.textContent='Select a gallery to begin uploading.';return;} Array.from(files).forEach(function(file){
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>25*1024*1024){const message=document.createElement('p');message.textContent=!['image/jpeg','image/png','image/webp'].includes(file.type)?file.name+' isn\u2019t supported.':file.name+' exceeds the 25 MB limit.';error.append(message);return;}
      const row=document.createElement('article'); row.className='lp-upload-row is-uploading'; row.innerHTML='<div class="lp-file-icon"><i class="bi bi-image"></i></div><div class="lp-file-main"><strong></strong><span>Preparing · '+(file.size/1048576).toFixed(1)+' MB</span><div class="lp-file-progress"><i></i></div></div><div class="lp-file-state"><strong>Uploading</strong><span data-speed>Starting…</span></div><div class="lp-file-actions"><button data-pause aria-label="Pause"><i class="bi bi-pause"></i></button><button data-cancel aria-label="Cancel"><i class="bi bi-x-lg"></i></button></div>'; row.querySelector('.lp-file-main strong').textContent=file.name; const empty=list.querySelector('[data-queue-empty]');if(empty)empty.remove();list.prepend(row);
      const data=new FormData();data.append('gallery',gallery.value);data.append('files',file);const xhr=new XMLHttpRequest(),started=Date.now();xhr.open('POST',page.dataset.uploadUrl);xhr.setRequestHeader('X-CSRFToken',csrf());xhr.upload.onprogress=function(e){if(e.lengthComputable){const speed=e.loaded/Math.max((Date.now()-started)/1000,.1);row.querySelector('.lp-file-progress i').style.width=(e.loaded/e.total*100)+'%';row.querySelector('[data-speed]').textContent=(speed/1048576).toFixed(1)+' MB/s · '+Math.ceil((e.total-e.loaded)/Math.max(speed,1))+'s left';}};xhr.onload=function(){const ok=xhr.status>=200&&xhr.status<300;row.className='lp-upload-row '+(ok?'is-completed':'is-failed');row.querySelector('.lp-file-state strong').textContent=ok?'Completed':'Failed';row.querySelector('[data-speed]').textContent=ok?'Complete':'Upload failed';if(ok)row.querySelector('.lp-file-progress i').style.width='100%';syncClearButton();};xhr.onerror=function(){row.className='lp-upload-row is-failed';row.querySelector('.lp-file-state strong').textContent='Failed';};row.querySelector('[data-cancel]').onclick=function(){xhr.abort();row.remove();};row.querySelector('[data-pause]').onclick=function(){xhr.abort();row.querySelector('.lp-file-state strong').textContent='Paused';this.innerHTML='<i class="bi bi-play"></i>';this.onclick=function(){row.remove();queue([file]);};};xhr.send(data);
    });input.value='';}
    input.addEventListener('change',function(){queue(input.files);});drop.addEventListener('click',function(){if(!input.disabled)input.click();});drop.addEventListener('keydown',function(e){if(!input.disabled&&(e.key==='Enter'||e.key===' ')){e.preventDefault();input.click();}});['dragover','dragenter'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();if(!input.disabled){drop.classList.add('is-dragging');page.querySelector('[data-drop-title]').textContent='Drop photos to upload';}});});['dragleave','drop'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();drop.classList.remove('is-dragging');page.querySelector('[data-drop-title]').textContent='Drop photos here';if(n==='drop'&&!input.disabled)queue(e.dataTransfer.files);});});const clear=page.querySelector('[data-clear-completed]');if(clear)clear.onclick=function(){list.querySelectorAll('.is-completed').forEach(function(r){r.remove();});clear.hidden=true;};
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
