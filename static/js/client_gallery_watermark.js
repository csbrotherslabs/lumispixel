(() => {
  'use strict';
  const ready = new WeakMap();
  const namespace = 'http://www.w3.org/2000/svg';
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  const backgrounds = new Map();

  function decorate(overlay) {
    const raw = Number(overlay.dataset.watermarkDensity || 3);
    const density = Number.isInteger(raw) && raw >= 1 && raw <= 5 ? raw : 3;
    const key = JSON.stringify([overlay.dataset.watermarkLabel, density]);
    if (ready.get(overlay) === key) return;
    const label = overlay.dataset.watermarkLabel?.trim();
    if (!label) return;
    ready.set(overlay, key);
    if (!backgrounds.has(key)) {
      // Measure the actual brand so long names are not truncated within a tile.
      context.font = '600 16px Arial';
      const spacing = 1 + (3 - density) * .25;
      const width = Math.ceil(Math.max(context.measureText(label).width + 24, 220 * spacing));
      const height = Math.round(112 * spacing);
      const svg = document.createElementNS(namespace, 'svg');
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      for (const [x, y] of [[12, height * .27], [12 - width / 2, height * .77], [12 + width / 2, height * .77]]) {
        const text = document.createElementNS(namespace, 'text');
        text.setAttribute('x', x);
        text.setAttribute('y', y);
        text.setAttribute('fill', 'white');
        text.setAttribute('fill-opacity', '.35');
        text.setAttribute('font-family', 'Arial, sans-serif');
        text.setAttribute('font-size', '16');
        text.setAttribute('font-weight', '600');
        // Text nodes and XML serialization keep photographer names as data.
        text.textContent = label;
        svg.append(text);
      }
      const xml = new XMLSerializer().serializeToString(svg);
      backgrounds.set(key, {image: `url("data:image/svg+xml,${encodeURIComponent(xml)}")`, width, height});
    }
    const tile = backgrounds.get(key);
    overlay.style.backgroundImage = tile.image;
    overlay.style.backgroundSize = `${tile.width}px ${tile.height}px`;
  }

  function refresh(root) {
    if (root.nodeType !== Node.ELEMENT_NODE && root !== document) return;
    if (root.matches?.('[data-gallery-watermark]')) decorate(root);
    root.querySelectorAll('[data-gallery-watermark]').forEach(decorate);
  }
  refresh(document);
  // Semantic results are inserted after page load. Observe only added nodes;
  // watermark style updates do not retrigger this observer.
  new MutationObserver(records => {
    records.forEach(record => { if (record.type === 'attributes') decorate(record.target); else record.addedNodes.forEach(refresh); });
  }).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['data-watermark-label', 'data-watermark-density']});
})();
