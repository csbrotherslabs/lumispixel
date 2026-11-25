document.querySelectorAll('[data-starter-preview]').forEach(button => {
  const dialog = document.getElementById(button.getAttribute('aria-controls'));
  if (!dialog || typeof dialog.showModal !== 'function') { button.hidden = true; return; }
  button.addEventListener('click', () => { dialog.showModal(); dialog.querySelector('.lp-starter-dialog-body').scrollTop = 0; });
  dialog.addEventListener('close', () => button.focus());
  dialog.addEventListener('click', event => { if (event.target !== dialog) return; const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close(); });
});
