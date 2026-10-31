(function () {
  'use strict';
  function init() {
    const controls = document.querySelector('[data-cover-position]');
    const image = document.querySelector('[data-cover-preview]');
    if (!controls || !image) return;
    const x = controls.querySelector('[name="cover_position_x"]');
    const y = controls.querySelector('[name="cover_position_y"]');
    const toggle = controls.querySelector('[data-cover-reposition]');
    let drag = null;
    function sync() {
      const position = `${x.value || 50}% ${y.value || 50}%`;
      image.style.objectPosition = position;
      document.querySelectorAll('[data-gallery-preview-cover] img').forEach(el => { el.style.objectPosition = position; });
      const available = !!image.getAttribute('src') && !image.hidden;
      controls.querySelectorAll('input,button').forEach(el => { el.disabled = !available; });
      if (!available) { image.classList.remove('is-repositioning'); toggle.setAttribute('aria-pressed', 'false'); toggle.textContent = 'Reposition'; }
    }
    toggle.addEventListener('click', () => {
      const active = image.classList.toggle('is-repositioning');
      toggle.setAttribute('aria-pressed', String(active));
      toggle.textContent = active ? 'Done repositioning' : 'Reposition';
    });
    [x, y].forEach(el => el.addEventListener('input', sync));
    controls.querySelector('[data-cover-center]').addEventListener('click', () => { x.value = 50; y.value = 50; sync(); });
    image.draggable = false;
    image.addEventListener('pointerdown', event => {
      if (!image.classList.contains('is-repositioning') || !image.naturalWidth) return;
      event.preventDefault();
      const box = image.getBoundingClientRect();
      const scale = Math.max(box.width / image.naturalWidth, box.height / image.naturalHeight);
      drag = {id: event.pointerId, startX: event.clientX, startY: event.clientY, x: +x.value, y: +y.value,
        overflowX: image.naturalWidth * scale - box.width, overflowY: image.naturalHeight * scale - box.height};
      image.setPointerCapture(event.pointerId);
    });
    image.addEventListener('pointermove', event => {
      if (!drag || event.pointerId !== drag.id) return;
      const clamp = v => Math.round(Math.min(100, Math.max(0, v)));
      if (drag.overflowX > 1) x.value = clamp(drag.x - (event.clientX - drag.startX) * 100 / drag.overflowX);
      if (drag.overflowY > 1) y.value = clamp(drag.y - (event.clientY - drag.startY) * 100 / drag.overflowY);
      sync();
    });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(name => image.addEventListener(name, () => { drag = null; }));
    image.addEventListener('load', sync);
    document.addEventListener('gallery:cover-preview', event => {
      const preview = document.querySelector('[data-gallery-preview-cover]');
      if (preview && event.detail.url) {
        let img = preview.querySelector('img');
        if (!img) { img = document.createElement('img'); img.alt = ''; preview.replaceChildren(img); }
        img.src = event.detail.url;
      }
      // Other gallery listeners may replace the live-preview image in this event.
      queueMicrotask(sync);
    });
    new MutationObserver(sync).observe(image, {attributes: true, attributeFilter: ['src', 'hidden']});
    sync();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
