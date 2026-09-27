(function () {
  'use strict';

  const picker = document.querySelector('[data-gallery-design-picker]');
  if (!picker) return;

  const modal = document.querySelector('[data-gallery-design-modal]');
  let previewCard = null;
  const title = modal ? modal.querySelector('[data-gallery-design-preview-title]') : null;
  const demo = modal ? modal.querySelector('[data-gallery-design-demo]') : null;
  const modalSelect = modal ? modal.querySelector('[data-gallery-design-modal-select]') : null;

  function syncSelectedState(selectedCard) {
    picker.querySelectorAll('[data-gallery-design-card]').forEach(function (item) {
      const isSelected = item === selectedCard;
      item.classList.toggle('is-selected', isSelected);
      item.setAttribute('aria-checked', isSelected ? 'true' : 'false');

      const badgeHost = item.querySelector('.lp-gallery-design-card__copy');
      let badge = item.querySelector('[data-gallery-design-selected]');
      if (isSelected && !badge && badgeHost) {
        badge = document.createElement('span');
        badge.className = 'lp-gallery-design-card__selected';
        badge.dataset.galleryDesignSelected = '';
        badge.innerHTML = '<i class="bi bi-check2" aria-hidden="true"></i> Selected';
        badgeHost.appendChild(badge);
      } else if (!isSelected && badge) {
        badge.remove();
      }

      const button = item.querySelector('[data-gallery-design-select]');
      if (button) {
        button.classList.toggle('is-selected', isSelected);
        button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
        button.textContent = isSelected ? 'Selected' : 'Select Design';
      }
    });
  }

  function selectCard(card) {
    if (!card) return;
    const input = card.querySelector('input[type="radio"]');
    if (!input || input.disabled) return;
    input.checked = true;
    syncSelectedState(card);
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  picker.addEventListener('click', function (event) {
    const select = event.target.closest('[data-gallery-design-select]');
    if (!select) return;
    event.preventDefault();
    event.stopPropagation();
    selectCard(select.closest('[data-gallery-design-card]'));
  });

  picker.addEventListener('change', function (event) {
    if (event.target.matches('input[type="radio"]')) {
      syncSelectedState(event.target.closest('[data-gallery-design-card]'));
    }
  });

  const initiallyChecked = picker.querySelector('input[type="radio"]:checked');
  if (initiallyChecked) syncSelectedState(initiallyChecked.closest('[data-gallery-design-card]'));

  // Legacy modal-preview support remains optional. Current design cards use
  // dedicated preview pages, so selection must never depend on this modal.
  if (!modal) return;

  function closePreview() {
    modal.hidden = true;
    document.body.classList.remove('lp-gallery-design-modal-open');
    const opener = previewCard && previewCard.querySelector('[data-gallery-design-preview]');
    if (opener) opener.focus();
  }

  modal.addEventListener('click', function (event) {
    if (event.target.closest('[data-gallery-design-close]')) {
      closePreview();
      return;
    }
    const device = event.target.closest('[data-gallery-preview-device]');
    if (device && demo) {
      modal.querySelectorAll('[data-gallery-preview-device]').forEach(function (button) {
        button.classList.toggle('is-active', button === device);
      });
      demo.dataset.device = device.dataset.galleryPreviewDevice;
    }
  });

  if (modalSelect) {
    modalSelect.addEventListener('click', function () {
      selectCard(previewCard);
      closePreview();
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !modal.hidden) closePreview();
  });
})();