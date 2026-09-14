(() => {
  'use strict';

  const form = document.querySelector('[data-gallery-create-form]');
  if (!form) return;

  const client = form.querySelector('#gallery-client');
  const booking = form.querySelector('[data-gallery-booking-select]');
  if (!client || !booking) return;

  function filterBookings() {
    const clientId = client.value;
    let selectedStillValid = !booking.value;

    Array.from(booking.options).forEach((option, index) => {
      if (index === 0 || !option.value) {
        option.hidden = false;
        option.disabled = false;
        return;
      }

      const matches = Boolean(clientId) && option.dataset.clientId === clientId;
      option.hidden = !matches;
      option.disabled = !matches;
      if (matches && option.selected) selectedStillValid = true;
    });

    if (!selectedStillValid) booking.value = '';
    booking.disabled = !clientId;
  }

  client.addEventListener('change', filterBookings);
  filterBookings();
})();
