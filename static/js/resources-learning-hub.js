(function () {
  'use strict';
  var triggers = Array.prototype.slice.call(document.querySelectorAll('.learning-hub-page .lh-faq-item button'));
  triggers.forEach(function (trigger, index) {
    trigger.addEventListener('click', function () {
      var panel = document.getElementById(trigger.getAttribute('aria-controls'));
      var open = trigger.getAttribute('aria-expanded') === 'true';
      trigger.setAttribute('aria-expanded', String(!open));
      panel.hidden = open;
    });
    trigger.addEventListener('keydown', function (event) {
      var next;
      if (event.key === 'ArrowDown') next = (index + 1) % triggers.length;
      if (event.key === 'ArrowUp') next = (index - 1 + triggers.length) % triggers.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = triggers.length - 1;
      if (next !== undefined) { event.preventDefault(); triggers[next].focus(); }
    });
  });
}());
