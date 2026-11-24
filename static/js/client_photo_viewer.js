/* Shared viewer: move existing forms, rather than duplicating their state/listeners. */
(function () {
  'use strict';
  const viewer = document.querySelector('.lp-viewer');
  if (!viewer) return;
  const image = viewer.querySelector('[data-photo-lightbox-image]');
  const aside = viewer.querySelector('.lp-viewer__comments');
  const commentButton = viewer.querySelector('[data-viewer-comments]');
  const favoriteButton = viewer.querySelector('[data-viewer-favorite]');
  const download = viewer.querySelector('[data-viewer-download]');
  const original = viewer.querySelector('[data-viewer-original]');
  let current, panel, home, opener;
  function restore() {
    if (panel && home) { panel.hidden = true; home.replaceWith(panel); }
    panel = home = null;
  }
  function counts() {
    viewer.querySelector('[data-viewer-comment-count]').textContent = current?.querySelector('[data-comment-count]')?.textContent || '0';
    viewer.querySelector('[data-viewer-favorite-count]').textContent = current?.querySelector('[data-favorite-count]')?.textContent || '0';
    favoriteButton.setAttribute('aria-pressed', String(current?.dataset.favorite === 'true'));
  }
  function renderCommentLike(button, liked, count) {
    button.setAttribute('aria-pressed', String(liked));
    button.setAttribute('aria-label', liked ? 'Unlike comment' : 'Like comment');
    button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10v11H3V10h4Zm0 0 5-7c2 0 3 1 3 3l-1 4h5a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 2H7"/></svg>';
    const label=document.createElement('span');
    label.textContent=String(count);
    button.append(label);
  }
  function decorateComments() {
    if (!panel) return;
    const composer = panel.querySelector('[data-comment-form]');
    if (composer && !composer.classList.contains('lp-comment-composer')) {
      composer.classList.add('lp-comment-composer');
      const input = composer.querySelector('textarea');
      const submit = composer.querySelector('button[type=submit]');
      if(input) {input.placeholder='Write a comment…';input.rows=1;}
      if(submit) {
        submit.setAttribute('aria-label','Send comment');
        submit.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13"/></svg>';
        composer.append(submit);
      }
    }
    panel.querySelectorAll('[data-client-comment-id]').forEach(row => {
      if (!row.querySelector('.lp-comment-avatar')) {
        const author = row.querySelector('strong');
        const paragraph = row.querySelector('p');
        if (author && paragraph) {
          const name = author.textContent.trim();
          const avatar = document.createElement('span');
          avatar.className = 'lp-comment-avatar';
          avatar.setAttribute('aria-hidden','true');
          avatar.textContent = name.split(/\s+/).slice(0,2).map(word=>word[0]||'').join('').toUpperCase() || 'G';
          const content = document.createElement('div');
          content.className = 'lp-comment-content';
          const meta = document.createElement('div');
          meta.className = 'lp-comment-meta';
          meta.append(author);
          const time = row.querySelector('time');
          if(time) meta.append(time);
          const actions = document.createElement('div');
          actions.className = 'lp-comment-actions';
          const deletion = row.querySelector('[data-client-comment-delete]');
          if(deletion) actions.append(deletion);
          content.append(meta, paragraph, actions);
          row.replaceChildren(avatar,content);
        }
      }
      const deleteControl = row.querySelector('[data-client-comment-delete]');
      const deleteButton = deleteControl?.matches('button') ? deleteControl : deleteControl?.querySelector('button');
      if(deleteButton && !deleteButton.classList.contains('lp-comment-trash')) {
        deleteButton.classList.add('lp-comment-trash');
        deleteButton.setAttribute('aria-label','Delete comment');
        deleteButton.title='Delete comment';
        deleteButton.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></svg>';
      }
      if(row.querySelector('[data-comment-like]') || !viewer.hasAttribute('data-can-like-comments')) return;
      const button=document.createElement('button');
      button.type='button'; button.dataset.commentLike='';
      renderCommentLike(button,row.dataset.liked==='true',row.dataset.likes||'0');
      (row.querySelector('.lp-comment-actions') || row).prepend(button);
    });
  }
  viewer.addEventListener('click', async event => {
    const button=event.target.closest('[data-comment-like]');
    if(!button || button.disabled || !panel) return;
    const row=button.closest('[data-client-comment-id]');
    const form=panel.querySelector('[data-comment-form]');
    if(!form) return;
    const url=new URL(form.action);
    url.pathname=url.pathname.replace(/comment\/$/,'comment-like/');
    button.disabled=true;
    try {
      const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':viewer.querySelector('[name=csrfmiddlewaretoken]').value},body:new URLSearchParams({comment_id:row.dataset.clientCommentId,liked:String(button.getAttribute('aria-pressed')!=='true')})});
      if(!response.ok) throw Error();
      const data=await response.json();
      row.dataset.liked=String(data.liked);
      row.dataset.likes=String(data.count);
      renderCommentLike(button,data.liked,data.count);
    } catch { status.textContent='Unable to update comment like'; }
    finally {button.disabled=false;}
  });
  function comments(show) {
    aside.hidden = !show;
    commentButton.setAttribute('aria-expanded', String(show));
    if (show) panel?.querySelector('textarea')?.focus();
    else commentButton.focus();
  }
  function size() {
    if (!current) return;
    const link = current.querySelector('[data-photo-download]');
    if (!link) return;
    const url = new URL(link.href);
    const selected = viewer.querySelector('[name="viewer-size"]').value;
    url.searchParams.set('size', selected);
    viewer.querySelector('[data-viewer-download-label]').textContent = 'Download ' + selected.charAt(0).toUpperCase() + selected.slice(1);
    download.href = url.href;
  }
  const status = viewer.querySelector('[data-viewer-status]');
  const scroll = viewer.querySelector('.lp-viewer-scroll');
  const media = image.parentElement;
  let zoom = 1, pinch = null;
  function setZoom(value) {
    zoom = Math.max(1, Math.min(4, value));
    media.style.setProperty('--viewer-zoom', zoom);
    viewer.querySelector('[data-zoom-level]').textContent = Math.round(zoom * 100) + '%';
    if (zoom === 1) { scroll.scrollLeft = 0; scroll.scrollTop = 0; }
  }
  viewer.querySelector('[data-zoom-in]').onclick = () => setZoom(zoom + .25);
  viewer.querySelector('[data-zoom-out]').onclick = () => setZoom(zoom - .25);
  viewer.querySelector('[data-zoom-fit]').onclick = () => setZoom(1);
  image.addEventListener('load', () => { status.textContent = ''; if (current && viewer.open) recordView(current); });
  image.addEventListener('error', () => { status.textContent = 'High-resolution preview unavailable. Reopen to retry.'; });
  const distance = touches => Math.hypot(touches[0].clientX-touches[1].clientX,touches[0].clientY-touches[1].clientY);
  scroll.addEventListener('touchstart', e => { if(e.touches.length===2) pinch={distance:distance(e.touches),zoom}; }, {passive:true});
  scroll.addEventListener('touchmove', e => { if(pinch && e.touches.length===2){e.preventDefault();setZoom(pinch.zoom*distance(e.touches)/Math.max(1,pinch.distance));} }, {passive:false});
  scroll.addEventListener('touchend', () => {pinch=null;});
  scroll.addEventListener('touchcancel', () => {pinch=null;});
  viewer.querySelector('[data-viewer-share]')?.addEventListener('click', async () => {
    try {
      const url = new URL(location.href); url.hash = '';
      if(navigator.share) await navigator.share({title:document.title,url:url.href});
      else { await navigator.clipboard.writeText(url.href); status.textContent='Gallery link copied'; }
    } catch(e) { if(e.name !== 'AbortError') status.textContent='Unable to share gallery'; }
  });
  const viewed = new Set();
  function recordView(photo) {
    const url = photo.querySelector('[data-view-url]')?.dataset.viewUrl;
    if (!url || viewed.has(url)) return;
    const csrf = viewer.querySelector('[name=csrfmiddlewaretoken]')?.value ||
      document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrf) return;
    viewed.add(url);
    fetch(url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf}})
      .then(response => { if (!response.ok) throw new Error('View tracking unavailable'); return response.json(); })
      .then(data => { const count = photo.querySelector('[data-view-count]'); if (count) count.textContent = data.view_count; })
      .catch(() => viewed.delete(url));
  }
  function open(photo, showComments, trigger) {
    restore(); current = photo; opener = trigger || opener;
    setZoom(1);
    const preview = photo.querySelector('[data-full-view]')?.dataset.src;
    image.removeAttribute('src');
    status.textContent = preview ? 'Loading preview…' : 'Preview unavailable';
    if (preview) image.src = preview;
    panel = photo.querySelector('[data-comment-panel]');
    if (panel) {
      home = document.createComment('comment panel home'); panel.before(home);
      panel.dataset.viewerPhotoId = photo.id; panel.hidden = false;
      viewer.querySelector('[data-viewer-thread]').append(panel);
      decorateComments();
    }
    commentButton.hidden = !panel;
    favoriteButton.hidden = !photo.querySelector('[data-favorite-form]');
    const link = photo.querySelector('[data-photo-download]');
    download.hidden = !link; viewer.querySelector('[data-viewer-download-group]').hidden = !link;
    const originalLink = photo.querySelector('[data-photo-download][href*="original"]');
    original.hidden = !originalLink; if (originalLink) original.href = originalLink.href;
    viewer.querySelector('.lp-viewer-download-menu').open = false;
    size(); counts(); aside.hidden = !(showComments && panel);
    commentButton.setAttribute('aria-expanded', String(!aside.hidden));
    if (!viewer.open) viewer.showModal();
    if (showComments) panel?.querySelector('textarea')?.focus();
  }
  // Capture before design-specific legacy lightbox/comment handlers.
  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('[data-full-view], [data-comment-toggle], [data-client-photo] > a');
    const photo = trigger?.closest('[data-client-photo]');
    if (!photo) return;
    event.preventDefault(); event.stopImmediatePropagation();
    open(photo, trigger.hasAttribute('data-comment-toggle'), trigger);
  }, true);
  commentButton.addEventListener('click', () => comments(aside.hidden));
  viewer.querySelector('[data-viewer-comments-close]').addEventListener('click', () => comments(false));
  favoriteButton.addEventListener('click', () => current?.querySelector('[data-favorite-form]')?.requestSubmit());
  viewer.querySelectorAll('[name="viewer-size"]').forEach(input => input.addEventListener('change', size));
  function step(delta) {
    const photos = Array.from(document.querySelectorAll('[data-client-photo]')).filter(photo => !photo.hidden);
    const index = photos.indexOf(current), next = photos[index + delta];
    if (next) open(next, !aside.hidden);
  }
  viewer.querySelector('[data-viewer-prev]').addEventListener('click', () => step(-1));
  viewer.querySelector('[data-viewer-next]').addEventListener('click', () => step(1));
  viewer.addEventListener('keydown', event => {
    if (event.target.matches('textarea,input')) return;
    if (event.key === 'ArrowLeft') step(-1);
    if (event.key === 'ArrowRight') step(1);
  });
  function close() { restore(); viewer.close(); }
  viewer.querySelector('[data-photo-lightbox-close]').addEventListener('click', close);
  viewer.addEventListener('click', event => { if (event.target === viewer) close(); });
  viewer.addEventListener('cancel', restore);
  viewer.addEventListener('close', () => { restore(); opener?.focus(); });
  document.addEventListener('lumispixel:favorite-changed', counts);
  document.addEventListener('lumispixel:comment-submitted', () => {counts();decorateComments();});
  new MutationObserver(() => {if(panel) decorateComments();}).observe(aside,{childList:true,subtree:true});
  new MutationObserver(counts).observe(document.querySelector('main'), {subtree: true, characterData: true, childList: true});
})();
