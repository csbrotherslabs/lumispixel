(() => {
  document.querySelectorAll('[data-semantic-client]').forEach(section => {
    const form = section.querySelector('[data-semantic-client-form]');
    const input = form.elements.q;
    const status = section.querySelector('[data-semantic-status]');
    const results = section.querySelector('[data-semantic-results]');
    const submit = section.querySelector('[data-semantic-submit]');
    const clear = section.querySelector('[data-semantic-clear]');
    const preview = section.querySelector('[data-semantic-preview]');
    const previewImage = section.querySelector('[data-semantic-preview-image]');
    const caption = section.querySelector('[data-semantic-preview-caption]');
    let controller;
    let generation = 0;
    let lastTrigger;
    let returningFocus = false;

    const toggle = section.querySelector('[data-semantic-toggle]');
    const panel = section.querySelector('[data-semantic-panel]');
    const viewAll = section.querySelector('[data-semantic-view-all]');
    const heading = section.querySelector('[data-semantic-heading]');
    const setResultMode = () => {
      const rows = Array.from(results.children);
      rows.forEach((row, index) => { row.hidden = index >= 10; });
      heading.textContent = rows.length ? `Top ${Math.min(10, rows.length)} matches` : 'AI photo search';
      viewAll.hidden = !rows.length;
    };
    const openSearch = (focus = false) => {
      section.classList.add('is-open'); form.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      if (status.textContent || results.children.length) panel.hidden = false;
      if (focus) input.focus();
    };
    const closeSearch = (focus = false) => {
      section.classList.remove('is-open'); form.hidden = true; panel.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      if (focus) { returningFocus = true; toggle.focus(); returningFocus = false; }
    };
    section.addEventListener('pointerenter', event => {
      if (event.pointerType === 'mouse') openSearch();
    });
    section.addEventListener('pointerleave', () => {
      if (!section.contains(document.activeElement) && !input.value && !status.textContent) closeSearch();
    });
    toggle.addEventListener('focus', () => { if (!returningFocus) openSearch(); });
    toggle.addEventListener('click', () => openSearch(true));
    section.querySelector('[data-semantic-dismiss]').addEventListener('click', () => closeSearch(true));
    section.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !preview.open) { event.preventDefault(); closeSearch(true); }
    });
    document.addEventListener('pointerdown', event => {
      if (!section.contains(event.target) && !preview.open) closeSearch();
    });
    const closePreview = () => preview.close();
    section.querySelector('[data-semantic-close]').addEventListener('click', closePreview);
    preview.addEventListener('click', event => { if (event.target === preview) closePreview(); });
    preview.addEventListener('close', () => {
      previewImage.removeAttribute('src');
      lastTrigger?.focus();
    });
    const setBusy = busy => {
      results.setAttribute('aria-busy', String(busy));
      submit.disabled = busy;
      submit.setAttribute('aria-label', busy ? 'Searching…' : 'Search photos');
      submit.title = busy ? 'Searching…' : 'Search photos';
    };
    clear.addEventListener('click', () => {
      generation += 1;
      controller?.abort();
      form.reset();
      results.replaceChildren();
      setResultMode();
      results.hidden = true;
      status.textContent = '';
      panel.hidden = true;
      clear.hidden = true;
      setBusy(false);
      input.focus();
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      input.value = input.value.trim();
      if (!form.reportValidity()) return;
      openSearch(); panel.hidden = false;
      const query = input.value;
      const resultsUrl = new URL(viewAll.getAttribute('href'), window.location.href);
      resultsUrl.searchParams.set('q', query);
      viewAll.href = resultsUrl.href;
      const current = ++generation;
      controller?.abort();
      controller = new AbortController();
      results.replaceChildren();
      setResultMode();
      results.hidden = true;
      clear.hidden = false;
      status.textContent = 'Finding photos… The first search may take a little longer.';
      setBusy(true);
      try {
        const url = new URL(form.dataset.searchUrl, window.location.href);
        url.searchParams.set('q', query);
        const response = await fetch(url, {
          credentials: 'same-origin', cache: 'no-store',
          headers: {Accept: 'application/json'}, signal: controller.signal,
        });
        if (!response.ok || response.redirected) {
          throw new Error([403, 404].includes(response.status) ? 'access' : 'unavailable');
        }
        const payload = await response.json();
        if (current !== generation) return;
        if (!Array.isArray(payload.results)) throw new Error('unavailable');
        const fragment = document.createDocumentFragment();
        // Append in API order; neither photo IDs nor gallery order determine rank.
        payload.results.forEach((item, index) => {
          if (!item.thumbnail_url) return;
          const row = document.createElement('li');
          row.dataset.photoId = String(item.photo_id);
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'lp-semantic-client__result';
          button.setAttribute('aria-label', `View result ${index + 1} for ${query}`);
          const image = document.createElement('img');
          image.src = item.thumbnail_url;
          image.alt = `Search result ${index + 1}`;
          image.loading = 'lazy';
          image.decoding = 'async';
          const label = document.createElement('span');
          label.textContent = String(index + 1);
          label.className = 'lp-semantic-client__rank';
          const media = document.createElement('span');
          media.className = 'lp-gallery-watermark-media';
          media.append(image);
          const watermark = section.querySelector('[data-semantic-watermark]');
          if (watermark) media.append(watermark.content.cloneNode(true));
          button.append(media, label);
          button.addEventListener('click', () => {
            lastTrigger = button;
            previewImage.src = item.thumbnail_url;
            previewImage.alt = `Result ${index + 1} for ${query}`;
            caption.textContent = `Result ${index + 1} · ${query}`;
            preview.showModal();
          });
          row.append(button);
          fragment.append(row);
        });
        results.append(fragment);
        setResultMode();
        const count = results.children.length;
        results.hidden = !count;
        status.textContent = count
          ? `${count} photo${count === 1 ? '' : 's'} for “${query}” · Closest matches first.`
          : 'No searchable photos found. Try another description, or try again after photos finish processing.';
      } catch (error) {
        if (current !== generation || error.name === 'AbortError') return;
        status.textContent = error.message === 'access'
          ? 'Search is no longer available for this gallery. Refresh to check your access.'
          : 'We couldn’t search right now. Please try again.';
      } finally {
        if (current === generation) setBusy(false);
      }
    });
  });
})();
