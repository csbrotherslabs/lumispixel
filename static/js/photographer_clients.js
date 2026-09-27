(() => {
  const workspace = document.querySelector('[data-clients-workspace]');
  if (!workspace) return;

  const form = workspace.querySelector('#client-filter-form');
  if (!form) return;

  const status = workspace.querySelector('[data-clients-ajax-status]');
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
    const nextWorkspace = doc.querySelector('[data-clients-workspace]');
    if (!nextWorkspace) throw new Error('Unable to read client results.');

    const nextResult = nextWorkspace.querySelector('.lp-clients-result');
    const nextActions = nextWorkspace.querySelector('.lp-clients-filter-actions');
    const nextRegion = nextWorkspace.querySelector('[data-clients-table-region]');
    const currentResult = workspace.querySelector('.lp-clients-result');
    const currentActions = workspace.querySelector('.lp-clients-filter-actions');
    const currentRegion = workspace.querySelector('[data-clients-table-region]');

    if (!nextResult || !nextActions || !nextRegion || !currentResult || !currentActions || !currentRegion) {
      throw new Error('Unable to update client results.');
    }

    currentResult.replaceWith(nextResult);
    currentActions.replaceWith(nextActions);
    currentRegion.replaceWith(nextRegion);
    window.history.pushState({}, '', url);
  };

  const loadResults = async (url) => {
    if (activeController) activeController.abort();
    activeController = new AbortController();
    setLoading(true, 'Updating clients…');

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: activeController.signal,
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`Request failed with ${response.status}`);

      replaceFromResponse(await response.text(), url);
      setLoading(false, 'Clients updated.');
      window.setTimeout(() => {
        if (status) status.textContent = '';
      }, 1400);
    } catch (error) {
      if (error.name === 'AbortError') return;
      setLoading(false, 'We could not update the clients. Please try again.');
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
      loadResults(window.location.pathname);
      return;
    }

    const pageLink = event.target.closest('[data-clients-page]');
    if (pageLink) {
      event.preventDefault();
      loadResults(pageLink.href);
    }
  });

  window.addEventListener('popstate', () => {
    loadResults(window.location.href);
  });
})();
