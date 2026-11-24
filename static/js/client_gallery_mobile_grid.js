(() => {
  const buttons = [...document.querySelectorAll('[data-mobile-columns]')];
  const grid = document.querySelector('.sf-photo-grid,.story-grid,.ms-grid,.cp-photo-grid');
  if (!grid || !buttons.length) return;
  buttons.forEach(button => button.addEventListener('click', () => {
    const columns = button.dataset.mobileColumns;
    if (columns !== '2' && columns !== '3') return;
    grid.style.setProperty('--lp-mobile-columns', columns);
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));
})();