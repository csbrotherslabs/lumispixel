(() => {
  const section = document.querySelector('[data-onboarding-key]');
  if (!section) return;
  const steps = section.querySelector('.lp-onboarding-steps');
  const current = steps?.querySelector('.is-current');
  if (steps && current) {
    const mobile = window.matchMedia('(max-width: 620px)');
    const revealCurrent = () => {
      if (!mobile.matches || section.hidden) return;
      // Scroll only the checklist, never the page or its header.
      steps.scrollLeft += current.getBoundingClientRect().left - steps.getBoundingClientRect().left - 4;
    };
    requestAnimationFrame(revealCurrent);
    mobile.addEventListener('change', revealCurrent);
  }
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
