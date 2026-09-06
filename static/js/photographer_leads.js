(() => {
  const workspace = document.querySelector('[data-leads-workspace]');
  if (!workspace) return;

  const form = workspace.querySelector('#lead-filter-form');
  if (!form) return;

  const status = workspace.querySelector('[data-leads-ajax-status]');
  let activeController = null;

  const setLoading = (isLoading, message = '') => {
    workspace.classList.toggle('is-loading', isLoading);
    workspace.setAttribute('aria-busy', isLoading ? 'true' : 'false');
    if (status) status.textContent = message;
    const applyButton = workspace.querySelector('[data-apply-filters]');
    if (applyButton) applyButton.disabled = isLoading;
  };

  const replaceFromResponse = (html, url) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const nextResult = doc.querySelector('[data-leads-workspace] .lp-leads-result');
    const nextActions = doc.querySelector('[data-leads-workspace] .lp-leads-filter-actions');
    const nextRegion = doc.querySelector('[data-leads-workspace] [data-leads-table-region]');

    const currentResult = workspace.querySelector('.lp-leads-result');
    const currentActions = workspace.querySelector('.lp-leads-filter-actions');
    const currentRegion = workspace.querySelector('[data-leads-table-region]');

    if (!nextResult || !nextActions || !nextRegion || !currentResult || !currentActions || !currentRegion) {
      throw new Error('Unable to update lead results.');
    }

    currentResult.replaceWith(nextResult);
    currentActions.replaceWith(nextActions);
    currentRegion.replaceWith(nextRegion);
    window.history.pushState({}, '', url);
  };

  const loadResults = async (url) => {
    if (activeController) activeController.abort();
    activeController = new AbortController();
    setLoading(true, 'Updating leads…');

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: activeController.signal,
        credentials: 'same-origin',
      });

      if (!response.ok) throw new Error(`Request failed with ${response.status}`);
      const html = await response.text();
      replaceFromResponse(html, url);
      setLoading(false, 'Leads updated.');
      window.setTimeout(() => {
        if (status) status.textContent = '';
      }, 1400);
    } catch (error) {
      if (error.name === 'AbortError') return;
      setLoading(false, 'We could not update the leads. Please try again.');
    }
  };

  const buildFilterUrl = () => {
    const params = new URLSearchParams(new FormData(form));
    for (const [key, value] of [...params.entries()]) {
      if (!String(value).trim()) params.delete(key);
    }
    const query = params.toString();
    return `${window.location.pathname}${query ? `?${query}` : ''}`;
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    loadResults(buildFilterUrl());
  });

  workspace.addEventListener('click', (event) => {
    const clear = event.target.closest('[data-clear-filters]');
    if (clear) {
      event.preventDefault();
      form.reset();
      const terminal = form.querySelector('input[name="terminal"]');
      if (terminal) terminal.value = '';
      loadResults(window.location.pathname);
      return;
    }

    const pageLink = event.target.closest('[data-leads-page]');
    if (pageLink) {
      event.preventDefault();
      loadResults(pageLink.href);
    }
  });

  window.addEventListener('popstate', () => {
    loadResults(window.location.href);
  });
})();
