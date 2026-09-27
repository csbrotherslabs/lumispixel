(() => {
  const clientDetailMatch = window.location.pathname.match(/\/crm\/clients\/(\d+)\/?$/);
  if (clientDetailMatch) {
    const clientId = clientDetailMatch[1];
    document.querySelectorAll('a[href*="/galleries/create/"]').forEach((link) => {
      const url = new URL(link.href, window.location.origin);
      url.searchParams.set('client', clientId);
      link.href = `${url.pathname}${url.search}${url.hash}`;
    });
  }

  const galleryForm = document.querySelector('[data-gallery-create-form]');
  if (!galleryForm) return;

  const requestedClient = new URLSearchParams(window.location.search).get('client');
  if (!requestedClient) return;

  const clientSelect = galleryForm.querySelector('select[name="client"]');
  if (!clientSelect) return;

  const matchingOption = Array.from(clientSelect.options).find(
    (option) => option.value === requestedClient,
  );
  if (!matchingOption) return;

  clientSelect.value = requestedClient;
  clientSelect.dispatchEvent(new Event('change', { bubbles: true }));
})();
