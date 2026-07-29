(function () {
  'use strict';
  function csrf() { return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''; }
  const page = document.querySelector('[data-upload-page]');
  if (page) {
    const drop=page.querySelector('[data-upload-drop]'), input=page.querySelector('[data-upload-input]'), gallery=page.querySelector('[data-upload-gallery]'), list=page.querySelector('[data-upload-list]'), error=page.querySelector('[data-upload-error]');
    const requested=new URLSearchParams(location.search).get('gallery'); if(requested) gallery.value=requested;
    function queue(files) { error.textContent=''; if(!gallery.value){error.textContent='Select a destination gallery first.';return;} Array.from(files).forEach(function(file){
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>25*1024*1024){error.textContent='Skipped unsupported files. Use JPG, PNG or WebP up to 25 MB.';return;}
      const row=document.createElement('article'); row.className='lp-upload-row is-uploading'; row.innerHTML='<div class="lp-file-icon"><i class="bi bi-image"></i></div><div class="lp-file-main"><strong></strong><span>Preparing · '+(file.size/1048576).toFixed(1)+' MB</span><div class="lp-file-progress"><i></i></div></div><div class="lp-file-state"><strong>Uploading</strong><span data-speed>Starting…</span></div><div class="lp-file-actions"><button data-pause aria-label="Pause"><i class="bi bi-pause"></i></button><button data-cancel aria-label="Cancel"><i class="bi bi-x-lg"></i></button></div>'; row.querySelector('.lp-file-main strong').textContent=file.name; const empty=list.querySelector('[data-queue-empty]');if(empty)empty.remove();list.prepend(row);
      const data=new FormData();data.append('gallery',gallery.value);data.append('files',file);const xhr=new XMLHttpRequest(),started=Date.now();xhr.open('POST',page.dataset.uploadUrl);xhr.setRequestHeader('X-CSRFToken',csrf());xhr.upload.onprogress=function(e){if(e.lengthComputable){const speed=e.loaded/Math.max((Date.now()-started)/1000,.1);row.querySelector('.lp-file-progress i').style.width=(e.loaded/e.total*100)+'%';row.querySelector('[data-speed]').textContent=(speed/1048576).toFixed(1)+' MB/s · '+Math.ceil((e.total-e.loaded)/Math.max(speed,1))+'s left';}};xhr.onload=function(){const ok=xhr.status>=200&&xhr.status<300;row.className='lp-upload-row '+(ok?'is-completed':'is-failed');row.querySelector('.lp-file-state strong').textContent=ok?'Completed':'Failed';row.querySelector('[data-speed]').textContent=ok?'Complete':'Upload failed';if(ok)row.querySelector('.lp-file-progress i').style.width='100%';};xhr.onerror=function(){row.querySelector('.lp-file-state strong').textContent='Failed';};row.querySelector('[data-cancel]').onclick=function(){xhr.abort();row.remove();};row.querySelector('[data-pause]').onclick=function(){xhr.abort();row.querySelector('.lp-file-state strong').textContent='Paused';this.innerHTML='<i class="bi bi-play"></i>';this.onclick=function(){row.remove();queue([file]);};};xhr.send(data);
    });input.value='';}
    input.addEventListener('change',function(){queue(input.files);});drop.addEventListener('click',function(){input.click();});drop.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click();}});['dragover','dragenter'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();drop.classList.add('is-dragging');});});['dragleave','drop'].forEach(function(n){drop.addEventListener(n,function(e){e.preventDefault();drop.classList.remove('is-dragging');if(n==='drop')queue(e.dataTransfer.files);});});page.querySelector('[data-clear-completed]').onclick=function(){list.querySelectorAll('.is-completed').forEach(function(r){r.remove();});};
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
