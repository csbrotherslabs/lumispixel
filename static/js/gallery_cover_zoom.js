/* Scale background covers using their actual cover-fit dimensions at every viewport. */
(() => {
  document.querySelectorAll('[data-gallery-cover-zoom]').forEach(el => {
    const zoom = Math.min(300, Math.max(100, Number(el.dataset.galleryCoverZoom) || 100)) / 100;
    if (zoom === 1) return;
    const source = new Image();
    const resize = () => {
      if (!source.naturalWidth || !el.clientWidth || !el.clientHeight) return;
      const scale = Math.max(el.clientWidth / source.naturalWidth, el.clientHeight / source.naturalHeight) * zoom;
      el.style.backgroundSize = `${source.naturalWidth * scale}px ${source.naturalHeight * scale}px`;
    };
    source.addEventListener('load', resize);
    source.src = el.dataset.coverSource;
    new ResizeObserver(resize).observe(el);
  });
})();
