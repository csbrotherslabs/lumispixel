(function () {
  var page = document.querySelector('.webinars-events-page');
  if (!page) return;
  page.classList.add('js-ready');
  page.querySelectorAll('.we-faq-item button').forEach(function (button, index) {
    var panel = document.getElementById(button.getAttribute('aria-controls'));
    var expanded = index === 0;
    button.setAttribute('aria-expanded', String(expanded));
    panel.hidden = !expanded;
    button.addEventListener('click', function () {
      var next = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(next));
      panel.hidden = !next;
    });
  });
}());
