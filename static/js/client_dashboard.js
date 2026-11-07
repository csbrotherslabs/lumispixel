/* Match the saved cover editor framing without modifying the source image. */
(() => {
  'use strict';
  const clamp = (value, fallback, min, max) => {
    const number = Number(value);
    return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
  };
  document.querySelectorAll('[data-client-gallery-image]').forEach(image => {
    const x = clamp(image.dataset.coverX, 50, 0, 100);
    const y = clamp(image.dataset.coverY, 50, 0, 100);
    const zoom = clamp(image.dataset.coverZoom, 100, 100, 300) / 100;
    const position = `${x}% ${y}%`;
    image.style.objectPosition = position;
    image.style.transformOrigin = position;
    image.style.transform = `scale(${zoom})`;
    const unavailable = () => {
      image.hidden = true;
      image.parentElement.querySelector('.client-hub__gallery-placeholder').hidden = false;
    };
    image.addEventListener('error', unavailable);
    if (image.complete && !image.naturalWidth) unavailable();
  });
})();
