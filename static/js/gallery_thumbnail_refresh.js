(() => {
  const grid = document.querySelector("[data-thumbnail-refresh-url]");
  if (!grid) return;
  const pending = new Map();
  const maxAttempts = 12;
  let busy = false;
  const status = img => img.parentElement.querySelector("[data-thumbnail-status]");
  function loaded(img) {
    pending.delete(img);
    img.style.visibility = "";
    status(img).hidden = true;
  }
  function failed(img) {
    const item = pending.get(img) || { attempts: 0, next: Date.now() + 3000 };
    img.style.visibility = "hidden";
    const label = status(img);
    label.hidden = false;
    if (item.attempts >= maxAttempts) {
      pending.delete(img);
      label.textContent = "Photo unavailable. Refresh to retry.";
      return;
    }
    item.next = Date.now() + Math.min(30000, 3000 * Math.pow(2, Math.min(item.attempts, 4)));
    pending.set(img, item);
  }
  grid.querySelectorAll("[data-gallery-thumbnail]").forEach(img => {
    img.addEventListener("load", () => loaded(img));
    img.addEventListener("error", () => failed(img));
    if (img.complete && img.getAttribute("src")) {
      if (img.naturalWidth) loaded(img);
      else failed(img);
    }
  });
  async function refresh() {
    if (busy || document.hidden) return;
    const batch = [];
    for (const [img, item] of pending) {
      if (!img.isConnected) { pending.delete(img); continue; }
      if (item.next <= Date.now()) batch.push([img, item]);
      if (batch.length === 50) break;
    }
    if (!batch.length) return;
    busy = true;
    try {
      const url = new URL(grid.dataset.thumbnailRefreshUrl, location.href);
      batch.forEach(([img]) => url.searchParams.append("id", img.dataset.galleryThumbnail));
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Thumbnail refresh unavailable");
      const data = await response.json();
      for (const [img, item] of batch) {
        if (!pending.has(img)) continue;
        item.attempts++;
        const src = data.photos[img.dataset.galleryThumbnail];
        if (src) {
          item.next = Date.now() + 30000;
          img.src = src;
        } else failed(img);
      }
    } catch (_) {
      for (const [img, item] of batch) {
        if (!pending.has(img)) continue;
        item.attempts++;
        failed(img);
      }
    } finally {
      busy = false;
    }
  }
  setInterval(refresh, 3000);
})();
