(function () {
  'use strict';
  function init() {
    const controls = document.querySelector('[data-cover-position]');
    const image = document.querySelector('[data-cover-preview]');
    if (!controls || !image) return;
    const x = controls.querySelector('[name="cover_position_x"]');
    const y = controls.querySelector('[name="cover_position_y"]');
    const zoom = controls.querySelector('[name="cover_zoom"]');
    const crop = image.parentElement;
    const clamp = (v, low=0, high=100) => Math.min(high, Math.max(low, Math.round(v)));
    let drag = null;
    function geometry() {
      const box = crop.getBoundingClientRect();
      const scale = Math.max(box.width / image.naturalWidth, box.height / image.naturalHeight) * Number(zoom.value) / 100;
      return {overflowX: image.naturalWidth * scale - box.width, overflowY: image.naturalHeight * scale - box.height};
    }
    function sync() {
      const position = `${x.value}% ${y.value}%`;
      const scale = Number(zoom.value) / 100;
      [image, ...document.querySelectorAll('[data-gallery-preview-cover] img')].forEach(el => {
        el.style.objectPosition = position;
        el.style.transformOrigin = position;
        el.style.transform = `scale(${scale})`;
      });
      controls.querySelector('[data-cover-zoom-value]').textContent = `${zoom.value}%`;
      const available = !!image.getAttribute('src') && !image.hidden;
      controls.querySelectorAll('input,button').forEach(el => { el.disabled = !available; });
      image.classList.toggle('is-repositioning', available);
      if (available && image.naturalWidth) {
        const g = geometry();
        controls.querySelectorAll('[data-cover-move]').forEach(button => {
          const direction = button.dataset.coverMove;
          button.disabled = (direction === 'left' || direction === 'right') ? g.overflowX <= 1 : g.overflowY <= 1;
        });
      }
      controls.querySelectorAll('[data-cover-zoom-step]').forEach(button => {
        button.disabled = !available || (Number(button.dataset.coverZoomStep) < 0 ? +zoom.value <= 100 : +zoom.value >= 300);
      });
    }
    controls.querySelectorAll('[data-cover-move]').forEach(button => button.addEventListener('click', () => {
      const direction = button.dataset.coverMove;
      // Match dragging: moving pixels right reduces the crop's X percentage.
      if (direction === 'left') x.value = clamp(+x.value + 2);
      if (direction === 'right') x.value = clamp(+x.value - 2);
      if (direction === 'up') y.value = clamp(+y.value + 2);
      if (direction === 'down') y.value = clamp(+y.value - 2);
      sync();
    }));
    controls.querySelector('[data-cover-center]').addEventListener('click', () => { x.value = 50; y.value = 50; sync(); });
    controls.querySelector('[data-cover-reset]').addEventListener('click', () => { x.value = 50; y.value = 50; zoom.value = 100; sync(); });
    controls.querySelectorAll('[data-cover-zoom-step]').forEach(button => button.addEventListener('click', () => {
      zoom.value = clamp(+zoom.value + Number(button.dataset.coverZoomStep), 100, 300); sync();
    }));
    zoom.addEventListener('input', sync);
    image.draggable = false;
    image.addEventListener('pointerdown', event => {
      if (image.hidden || !image.naturalWidth || (event.button !== undefined && event.button !== 0)) return;
      event.preventDefault();
      drag = {id:event.pointerId, startX:event.clientX, startY:event.clientY, x:+x.value, y:+y.value, ...geometry()};
      image.setPointerCapture(event.pointerId);
    });
    image.addEventListener('pointermove', event => {
      if (!drag || event.pointerId !== drag.id) return;
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
      queueMicrotask(sync);
    });
    new MutationObserver(sync).observe(image, {attributes:true, attributeFilter:['src','hidden']});
    new ResizeObserver(sync).observe(crop);
    sync();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
