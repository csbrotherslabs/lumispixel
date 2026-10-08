(() => {
  const drawer = document.querySelector('[data-notification-drawer]');
  if (!drawer) return;
  const list = drawer.querySelector('[data-notification-list]');
  const triggers = document.querySelectorAll('[data-notification-open]');
  const filters = drawer.querySelectorAll('[data-notification-filter]');
  const form = drawer.querySelector('[data-notification-read-all]');
  const readButton = form.querySelector('button');
  const countBadge = drawer.querySelector('[data-notification-count]');
  const feedback = drawer.querySelector('[data-notification-feedback]');
  let controller, status = 'all', version = 0, saving = false, opener;
  function updateCount(count) {
    count = Math.max(0, Number(count) || 0);
    countBadge.hidden = !count;
    countBadge.textContent = count + ' new';
    readButton.disabled = saving || !count;
    triggers.forEach(trigger => {
      trigger.setAttribute('aria-label', count ? 'Notifications, ' + count + ' unread' : 'Notifications');
      let badge = trigger.querySelector('.lp-notification-count, span');
      if (!count) { badge?.remove(); return; }
      if (!badge) { badge = document.createElement('span'); badge.className = 'lp-notification-count'; badge.setAttribute('aria-hidden', 'true'); trigger.append(badge); }
      badge.textContent = count > 10 ? '10+' : String(count);
    });
  }
  async function refresh() {
    controller?.abort();
    const ticket = ++version;
    controller = new AbortController();
    list.textContent = 'Loading notifications…';
    list.setAttribute('aria-busy', 'true');
    const url = new URL(drawer.dataset.previewUrl, window.location.origin);
    url.searchParams.set('status', status);
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok || response.redirected) throw new Error('Unavailable');
      const html = await response.text();
      if (ticket !== version) return;
      list.innerHTML = html;
      list.scrollTop = 0;
      updateCount(response.headers.get('X-Unread-Count'));
    } catch (error) {
      if (error.name !== 'AbortError' && ticket === version) list.textContent = 'Notifications could not be loaded. Select a filter to retry, or see all notifications.';
    } finally { if (ticket === version) list.removeAttribute('aria-busy'); }
  }
  drawer.querySelector('[data-notification-close]').addEventListener('click', () => drawer.close());
  drawer.addEventListener('click', event => {
    if (event.target !== drawer) return;
    const r = drawer.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) drawer.close();
  });
  drawer.addEventListener('close', () => {
    controller?.abort(); ++version; list.removeAttribute('aria-busy');
    triggers.forEach(t => t.setAttribute('aria-expanded', 'false'));
    opener?.focus();
  });
  filters.forEach(button => button.addEventListener('click', () => {
    status = button.dataset.notificationFilter;
    filters.forEach(tab => tab.setAttribute('aria-pressed', String(tab === button)));
    refresh();
  }));
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving || readButton.disabled) return;
    saving = true; readButton.disabled = true; feedback.textContent = '';
    try {
      const response = await fetch(form.action, {method: 'POST', credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}, body: new FormData(form)});
      if (!response.ok || response.redirected) throw new Error('Unavailable');
      const result = await response.json();
      updateCount(result.unread_count);
      feedback.textContent = 'All notifications marked as read.';
      if (drawer.open) await refresh();
    } catch (error) { feedback.textContent = 'Could not mark notifications as read. Please try again.'; }
    finally { saving = false; readButton.disabled = countBadge.hidden; }
  });
  triggers.forEach(trigger => trigger.addEventListener('click', event => {
    event.preventDefault();
    if (drawer.open) return;
    opener = trigger;
    drawer.showModal();
    trigger.setAttribute('aria-expanded', 'true');
    feedback.textContent = '';
    refresh();
  }));
})();
