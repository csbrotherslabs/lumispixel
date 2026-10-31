(() => {
  'use strict';
  const ready = new WeakSet();
  const namespace = 'http://www.w3.org/2000/svg';
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  const backgrounds = new Map();

  function decorate(overlay) {
    if (ready.has(overlay)) return;
    const label = overlay.dataset.watermarkLabel?.trim();
    if (!label) return;
    ready.add(overlay);
    if (!backgrounds.has(label)) {
      // Measure the actual brand so long names are not truncated within a tile.
      context.font = '600 16px Arial';
      const width = Math.ceil(Math.max(220, context.measureText(label).width + 40));
      const height = 112;
      const svg = document.createElementNS(namespace, 'svg');
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      for (const [x, y] of [[20, 30], [20 - width / 2, 86], [20 + width / 2, 86]]) {
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
      backgrounds.set(label, `url("data:image/svg+xml,${encodeURIComponent(xml)}")`);
    }
    overlay.style.backgroundImage = backgrounds.get(label);
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
    records.forEach(record => record.addedNodes.forEach(refresh));
  }).observe(document.body, {childList: true, subtree: true});
})();
