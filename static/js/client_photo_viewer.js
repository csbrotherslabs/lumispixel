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
    url.searchParams.set('size', viewer.querySelector('[name="viewer-size"]:checked').value);
    download.href = url.href;
  }
  function open(photo, showComments, trigger) {
    restore(); current = photo; opener = trigger || opener;
    image.src = photo.querySelector('[data-full-view]')?.dataset.src || photo.querySelector('img').src;
    panel = photo.querySelector('[data-comment-panel]');
    if (panel) {
      home = document.createComment('comment panel home'); panel.before(home);
      panel.dataset.viewerPhotoId = photo.id; panel.hidden = false;
      viewer.querySelector('[data-viewer-thread]').append(panel);
    }
    commentButton.hidden = !panel;
    favoriteButton.hidden = !photo.querySelector('[data-favorite-form]');
    const link = photo.querySelector('[data-photo-download]');
    download.hidden = !link; viewer.querySelector('[data-viewer-sizes]').hidden = !link;
    const originalLink = photo.querySelector('[data-photo-download][href*="original"]');
    original.hidden = !originalLink; if (originalLink) original.href = originalLink.href;
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
  [download, original].forEach(link => link.addEventListener('click', () => {
    // Reuse the existing counter handler on the card, without a second navigation.
    const source = current?.querySelector('[data-photo-download]');
    if (source) {
      const cancel = event => event.preventDefault();
      source.addEventListener('click', cancel, {once: true}); source.click();
    }
  }));
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
  viewer.querySelector('[data-photo-lightbox-close]').addEventListener('click', () => viewer.close());
  viewer.addEventListener('click', event => { if (event.target === viewer) viewer.close(); });
  viewer.addEventListener('close', () => { restore(); opener?.focus(); });
  document.addEventListener('lumispixel:favorite-changed', counts);
  document.addEventListener('lumispixel:comment-submitted', counts);
  new MutationObserver(counts).observe(document.querySelector('main'), {subtree: true, characterData: true, childList: true});
})();
