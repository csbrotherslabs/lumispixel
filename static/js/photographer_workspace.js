(function () {
  const sidebar = document.querySelector('[data-workspace-sidebar]');
  const openButton = document.querySelector('[data-workspace-open]');
  const closeButton = document.querySelector('[data-workspace-close]');
  const collapseButton = document.querySelector('[data-workspace-collapse]');
  const scrim = document.querySelector('[data-workspace-scrim]');

  if (sidebar) sidebar.id = 'workspace-sidebar';

  function openDrawer() {
    sidebar.classList.add('is-open');
    scrim.hidden = false;
    closeButton.focus();
  }

  function closeDrawer(restoreFocus) {
    sidebar.classList.remove('is-open');
    scrim.hidden = true;
    if (restoreFocus) openButton.focus();
  }

  if (sidebar && openButton && closeButton && scrim) {
    openButton.addEventListener('click', openDrawer);
    closeButton.addEventListener('click', function () { closeDrawer(true); });
    scrim.addEventListener('click', function () { closeDrawer(true); });
  }

  if (sidebar && collapseButton) {
    const collapsed = window.localStorage.getItem('lpw-sidebar-collapsed') === 'true';
    sidebar.classList.toggle('is-collapsed', collapsed);
    collapseButton.setAttribute('aria-expanded', String(!collapsed));
    collapseButton.addEventListener('click', function () {
      const next = !sidebar.classList.contains('is-collapsed');
      sidebar.classList.toggle('is-collapsed', next);
      collapseButton.setAttribute('aria-expanded', String(!next));
      collapseButton.setAttribute('aria-label', next ? 'Expand navigation' : 'Collapse navigation');
      window.localStorage.setItem('lpw-sidebar-collapsed', String(next));
    });
  }

  document.querySelectorAll('[data-nav-group-toggle]').forEach(function (toggle) {
    toggle.addEventListener('click', function () {
      const items = document.getElementById(toggle.getAttribute('aria-controls'));
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      items.hidden = expanded;
    });
  });

  const profileMenu = document.querySelector('[data-profile-menu]');
  const profileToggle = document.querySelector('[data-profile-toggle]');
  const profileDropdown = document.querySelector('[data-profile-dropdown]');
  function closeProfile() {
    if (!profileToggle || !profileDropdown) return;
    profileToggle.setAttribute('aria-expanded', 'false');
    profileDropdown.hidden = true;
  }
  if (profileMenu && profileToggle && profileDropdown) {
    profileToggle.addEventListener('click', function () {
      const open = profileToggle.getAttribute('aria-expanded') === 'true';
      profileToggle.setAttribute('aria-expanded', String(!open));
      profileDropdown.hidden = open;
    });
    document.addEventListener('click', function (event) {
      if (!profileMenu.contains(event.target)) closeProfile();
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    if (sidebar && sidebar.classList.contains('is-open')) closeDrawer(true);
    closeProfile();
  });
})();
