(() => {
  const section = document.querySelector('[data-onboarding-key]');
  if (!section) return;
  const button = section.querySelector('[data-onboarding-dismiss]');
  if (!button) return;
  const key = section.dataset.onboardingKey;
  try {
    if (sessionStorage.getItem(key) === '1') section.hidden = true;
    button.hidden = false;
  } catch (_) { return; }
  button.addEventListener('click', () => {
    try { sessionStorage.setItem(key, '1'); } catch (_) { return; }
    const next = document.querySelector('#quick-title');
    if (next) {
      next.setAttribute('tabindex', '-1');
      next.focus();
    }
    section.hidden = true;
  });
})();
