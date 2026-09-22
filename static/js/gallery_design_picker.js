(function () {
  'use strict';
  const picker = document.querySelector('[data-gallery-design-picker]');
  const modal = document.querySelector('[data-gallery-design-modal]');
  if (!picker || !modal) return;

  let previewCard = null;
  const title = modal.querySelector('[data-gallery-design-preview-title]');
  const demo = modal.querySelector('[data-gallery-design-demo]');
  const modalSelect = modal.querySelector('[data-gallery-design-modal-select]');

  function selectCard(card) {
    if (!card) return;
    const input = card.querySelector('input[type="radio"]');
    if (!input || input.disabled) return;
    input.checked = true;
    picker.querySelectorAll('[data-gallery-design-card]').forEach(function (item) {
      item.classList.toggle('is-selected', item === card);
    });
    input.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function openPreview(button) {
    previewCard = button.closest('[data-gallery-design-card]');
    title.textContent = button.dataset.templateName || 'Gallery Design';
    modal.hidden = false;
    document.body.classList.add('lp-gallery-design-modal-open');
    modal.querySelector('.lp-gallery-design-modal__close').focus();
  }

  function closePreview() {
    modal.hidden = true;
    document.body.classList.remove('lp-gallery-design-modal-open');
    const opener = previewCard && previewCard.querySelector('[data-gallery-design-preview]');
    if (opener) opener.focus();
  }

  picker.addEventListener('click', function (event) {
    const preview = event.target.closest('[data-gallery-design-preview]');
    if (preview) { openPreview(preview); return; }
    const select = event.target.closest('[data-gallery-design-select]');
    if (select) selectCard(select.closest('[data-gallery-design-card]'));
  });

  modal.addEventListener('click', function (event) {
    if (event.target.closest('[data-gallery-design-close]')) { closePreview(); return; }
    const device = event.target.closest('[data-gallery-preview-device]');
    if (device) {
      modal.querySelectorAll('[data-gallery-preview-device]').forEach(function (button) {
        button.classList.toggle('is-active', button === device);
      });
      demo.dataset.device = device.dataset.galleryPreviewDevice;
    }
  });

  modalSelect.addEventListener('click', function () {
    selectCard(previewCard);
    closePreview();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !modal.hidden) closePreview();
  });
})();