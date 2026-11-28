(() => {
  const editor = document.querySelector('[data-equipment-editor]');
  if (!editor) return;
  const items = editor.querySelector('[data-equipment-items]'), template = editor.querySelector('[data-equipment-template]'), indices = editor.querySelector('[data-equipment-indices]');
  let next = Number(editor.dataset.nextIndex || 1);
  const originals = new WeakMap(), urls = new WeakMap();
  const rows = () => [...items.querySelectorAll('[data-equipment-item]')];
  const active = () => rows().filter(r => !r.querySelector('[data-equipment-remove]').value);
  const dirty = () => indices.dispatchEvent(new Event('change', {bubbles:true}));
  function toggle(row, open) {
    row.querySelector('[data-equipment-body]').hidden = !open;
    const b = row.querySelector('[data-equipment-toggle]');
    b.setAttribute('aria-expanded', String(open)); b.textContent = open ? 'Collapse' : 'Expand';
  }
  function sync() {
    indices.value = rows().map(r => r.dataset.equipmentIndex).join(',');
    const list = active();
    editor.querySelector('[data-equipment-count]').textContent = list.length + (list.length === 1 ? ' item' : ' items');
    rows().forEach(r => {
      const n = list.indexOf(r), name = r.querySelector('input[type=text]').value.trim(), description = r.querySelector('textarea').value.trim();
      const complete = !!(name && description && r.querySelector('img'));
      r.querySelector('[data-equipment-number]').textContent = n < 0 ? 'Pending removal' : 'Equipment ' + (n+1);
      r.querySelector('[data-equipment-title]').textContent = name || 'New equipment';
      const status = r.querySelector('[data-equipment-status]'); status.textContent = complete ? 'Complete' : 'Incomplete'; status.dataset.complete = String(complete);
      r.querySelector('[data-equipment-up]').disabled = n <= 0;
      r.querySelector('[data-equipment-down]').disabled = n < 0 || n === list.length-1;
    });
    editor.querySelector('[data-equipment-add]').disabled = rows().length >= 200 || next > 32767;
  }
  function init(r) { originals.set(r, r.querySelector('[data-equipment-photo]').innerHTML); }
  function reset(r) {
    if (urls.has(r)) URL.revokeObjectURL(urls.get(r));
    urls.delete(r); r.querySelector('input[type=file]').value = '';
    r.querySelector('[data-equipment-photo]').innerHTML = originals.get(r);
    r.querySelector('[data-equipment-reset]').hidden = true;
    r.querySelector('[data-equipment-upload-label]').textContent = r.querySelector('img') ? 'Replace image' : 'Choose image';
  }
  rows().forEach((r,i) => {init(r); toggle(r,i===0 || !r.hasAttribute('data-equipment-saved'));});
  editor.querySelector('[data-equipment-add]').addEventListener('click', () => {
    if (rows().length >= 200 || next > 32767) return;
    items.insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__index__', String(next++)));
    const r = items.lastElementChild; init(r); toggle(r,true); sync(); dirty(); r.querySelector('input[type=text]').focus();
  });
  items.addEventListener('input', sync);
  items.addEventListener('change', e => {
    if (e.target.type !== 'file' || !e.target.files.length) return;
    const r = e.target.closest('[data-equipment-item]'), photo = r.querySelector('[data-equipment-photo]');
    if (urls.has(r)) URL.revokeObjectURL(urls.get(r));
    const url = URL.createObjectURL(e.target.files[0]); urls.set(r,url);
    const img = document.createElement('img'); img.src=url; img.alt='Selected equipment photograph'; photo.replaceChildren(img);
    r.querySelector('[data-equipment-reset]').hidden=false; r.querySelector('[data-equipment-upload-label]').textContent='Replace image'; sync();
  });
  items.addEventListener('click', e => {
    const b=e.target.closest('button'), r=b?.closest('[data-equipment-item]'); if(!r)return;
    if(b.matches('[data-equipment-toggle]')) {toggle(r,b.getAttribute('aria-expanded')!=='true');return;}
    if(b.matches('[data-equipment-reset]')) reset(r);
    else if(b.matches('[data-equipment-remove-button]')) {
      if(r.hasAttribute('data-equipment-saved')) {
        const field=r.querySelector('[data-equipment-remove]'); field.value=field.value?'':'1';
        r.classList.toggle('is-removed',!!field.value); b.textContent=field.value?'Undo removal':'Remove equipment'; toggle(r,!field.value);
      } else {if(urls.has(r))URL.revokeObjectURL(urls.get(r));r.remove();}
    } else if(b.matches('[data-equipment-up],[data-equipment-down]')) {
      const list=active(), i=list.indexOf(r);
      if(b.matches('[data-equipment-up]') && i>0)items.insertBefore(r,list[i-1]);
      if(b.matches('[data-equipment-down]') && i<list.length-1)items.insertBefore(list[i+1],r);
    } else return;
    sync();dirty();
  });
  sync();
})();
