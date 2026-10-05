(() => {
  const drawer = document.querySelector('[data-notification-drawer]');
  if (!drawer) return;
  const list = drawer.querySelector('[data-notification-list]');
  const triggers = document.querySelectorAll('[data-notification-open]');
  let controller;
  drawer.querySelector('[data-notification-close]').addEventListener('click', () => drawer.close());
  drawer.addEventListener('click', (event) => { if (event.target === drawer) { const r = drawer.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) drawer.close(); } });
  drawer.addEventListener('close', () => { controller?.abort(); triggers.forEach(t => t.setAttribute('aria-expanded', 'false')); });
  triggers.forEach(trigger => trigger.addEventListener('click', async event => {
    event.preventDefault();
    if (drawer.open) return;
    drawer.showModal();
    trigger.setAttribute('aria-expanded', 'true');
    list.textContent = 'Loading notifications…';
    list.setAttribute('aria-busy', 'true');
    controller = new AbortController();
    try {
      const response = await fetch(drawer.dataset.previewUrl, {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok || response.redirected) throw new Error('Notifications unavailable');
      list.innerHTML = await response.text();
    } catch (error) {
      if (error.name !== 'AbortError') list.textContent = 'Notifications could not be loaded. Close and reopen to retry, or select See all notifications.';
    } finally { list.removeAttribute('aria-busy'); }
  }));
})();
