(function () {
  'use strict';
  document.querySelectorAll('.rn-faq button').forEach(function (button) {
    button.addEventListener('click', function () {
      var item = button.closest('article');
      var open = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', String(!open));
      item.classList.toggle('is-open', !open);
      var icon = button.querySelector('i');
      if (icon) icon.className = open ? 'bi bi-plus' : 'bi bi-dash';
    });
  });
  var form = document.getElementById('update-filter');
  if (form) form.addEventListener('reset', function () {
    window.setTimeout(function () { document.getElementById('update-results').textContent = 'Filters cleared. Showing 12 clearly labeled illustrative and planned updates.'; }, 0);
  });
}());
