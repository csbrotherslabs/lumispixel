/* Accessible, dependency-free behavior for shared Workspace overlays. */
(function () {
  'use strict';

  var tooltip;
  var tooltipOwner;

  document.querySelectorAll('[data-lp-bar-height]').forEach(function (bar) {
    var height = Number(bar.getAttribute('data-lp-bar-height'));
    bar.style.setProperty('--lp-data-height', Math.max(0, Math.min(100, height)) + '%');
  });

  function hideTooltip() {
    if (tooltip) tooltip.remove();
    if (tooltipOwner) tooltipOwner.removeAttribute('aria-describedby');
    tooltip = null;
    tooltipOwner = null;
  }

  function showTooltip(owner) {
    var text = owner.getAttribute('data-tooltip');
    if (!text || owner.disabled) return;
    hideTooltip();
    tooltipOwner = owner;
    tooltip = document.createElement('div');
    tooltip.className = 'lp-tooltip';
    tooltip.id = 'lp-tooltip-' + Date.now();
    tooltip.setAttribute('role', 'tooltip');
    tooltip.textContent = text;
    document.body.appendChild(tooltip);
    owner.setAttribute('aria-describedby', tooltip.id);
    var ownerBox = owner.getBoundingClientRect();
    var tipBox = tooltip.getBoundingClientRect();
    var left = Math.min(window.innerWidth - tipBox.width - 8, Math.max(8, ownerBox.left + (ownerBox.width - tipBox.width) / 2));
    var top = ownerBox.top - tipBox.height - 8;
    if (top < 8) top = ownerBox.bottom + 8;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }

  function closeMenu(menu, restoreFocus) {
    var trigger = menu.querySelector('[data-lp-menu-trigger]');
    var panel = menu.querySelector('[data-lp-menu-panel]');
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger.focus();
  }

  document.addEventListener('mouseover', function (event) {
    var owner = event.target.closest('[data-tooltip]');
    if (owner) showTooltip(owner);
  });
  document.addEventListener('mouseout', function (event) {
    if (event.target.closest('[data-tooltip]')) hideTooltip();
  });
  document.addEventListener('focusin', function (event) {
    var owner = event.target.closest('[data-tooltip]');
    if (owner) showTooltip(owner);
  });
  document.addEventListener('focusout', hideTooltip);

  document.addEventListener('click', function (event) {
    document.querySelectorAll('[data-lp-menu]').forEach(function (menu) {
      var trigger = menu.querySelector('[data-lp-menu-trigger]');
      var panel = menu.querySelector('[data-lp-menu-panel]');
      if (trigger.contains(event.target)) {
        var opening = panel.hidden;
        document.querySelectorAll('[data-lp-menu]').forEach(function (other) { if (other !== menu) closeMenu(other); });
        panel.hidden = !opening;
        trigger.setAttribute('aria-expanded', String(opening));
        if (opening) {
          var first = panel.querySelector('[role="menuitem"], a, button:not(:disabled)');
          if (first) first.focus();
        }
      } else if (!menu.contains(event.target)) closeMenu(menu);
    });
  });

  document.addEventListener('keydown', function (event) {
    var menu = event.target.closest('[data-lp-menu]');
    if (!menu) return;
    var panel = menu.querySelector('[data-lp-menu-panel]');
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      closeMenu(menu, true);
      return;
    }
    if (panel.hidden || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    var items = Array.from(panel.querySelectorAll('[role="menuitem"], a, button:not(:disabled)'));
    if (!items.length) return;
    event.preventDefault();
    var index = items.indexOf(document.activeElement);
    if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = items.length - 1;
    else if (event.key === 'ArrowDown') index = (index + 1) % items.length;
    else index = (index - 1 + items.length) % items.length;
    items[index].focus();
  });

  window.addEventListener('scroll', hideTooltip, true);
  window.addEventListener('resize', hideTooltip);
}());
