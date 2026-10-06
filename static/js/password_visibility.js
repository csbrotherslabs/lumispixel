(() => {
  document.querySelectorAll('[data-password-visibility] input[type="password"]').forEach((input) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'lumis-password-control';
    input.before(wrapper);
    wrapper.append(input);
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'lumis-password-toggle';
    toggle.setAttribute('aria-pressed', 'false');
    toggle.setAttribute('aria-controls', input.id);
    const label = Array.from(input.labels || []).map((item) => item.textContent.trim()).join(' ') || 'password';
    toggle.setAttribute('aria-label', `Show ${label}`);
    const icon = document.createElement('i');
    icon.className = 'bi bi-eye';
    icon.setAttribute('aria-hidden', 'true');
    toggle.append(icon);
    wrapper.append(toggle);
    toggle.addEventListener('click', () => {
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', String(visible));
      toggle.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} ${label}`);
      icon.className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
    input.form?.addEventListener('submit', () => { input.type = 'password'; });
  });
})();
