/* Responsive private covers, preserving cover-fit zoom and positioning. */
(() => {
  const mobile = matchMedia('(max-width: 767px)');
  document.querySelectorAll('[data-gallery-cover-zoom]').forEach(el => {
    const zoom = Math.min(300, Math.max(100, Number(el.dataset.galleryCoverZoom) || 100)) / 100;
    let source;
    let activeUrl;
    let timer;
    let attempts = 0;
    const resize = () => {
      if (!source?.naturalWidth || !el.clientWidth || !el.clientHeight) return;
      const scale = Math.max(el.clientWidth / source.naturalWidth, el.clientHeight / source.naturalHeight) * zoom;
      el.style.backgroundSize = zoom === 1 ? 'cover' : `${source.naturalWidth * scale}px ${source.naturalHeight * scale}px`;
    };
    function load() {
      const url = mobile.matches && el.dataset.coverMobile ? el.dataset.coverMobile : el.dataset.coverSource;
      if (!url) return;
      clearTimeout(timer);
      if (url !== activeUrl) { attempts = 0; activeUrl = url; }
      const image = new Image();
      image.onload = () => {
        if (activeUrl !== url) return;
        source = image;
        el.style.backgroundImage = `url("${url}")`;
        resize();
      };
      image.onerror = () => {
        if (activeUrl !== url || ++attempts >= 8) return;
        timer = setTimeout(load, Math.min(30000, 3000 * 2 ** (attempts - 1)));
      };
      image.src = url;
    }
    if (el.dataset.coverMobile) {
      mobile.addEventListener('change', load);
      load();
    } else if (zoom !== 1) {
      source = new Image();
      source.addEventListener('load', resize);
      source.src = el.dataset.coverSource;
    }
    new ResizeObserver(resize).observe(el);
  });
})();
