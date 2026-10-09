(() => {
  document.querySelectorAll('[data-lp-flow]').forEach((section) => {
    const tabs = Array.from(section.querySelectorAll('[data-flow-tab]'));
    const panels = Array.from(section.querySelectorAll('[role="tabpanel"]'));
    const activate = (tab, focus = false) => {
      tabs.forEach((item) => {
        const selected = item === tab;
        item.setAttribute('aria-selected', String(selected));
        item.tabIndex = selected ? 0 : -1;
      });
      panels.forEach((panel) => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
      if (focus) tab.focus();
      if (section.querySelector('.lp-flow__steps').scrollWidth > section.querySelector('.lp-flow__steps').clientWidth) {
        tab.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' });
      }
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab));
      tab.addEventListener('keydown', (event) => {
        let target;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') target = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') target = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') target = 0;
        if (event.key === 'End') target = tabs.length - 1;
        if (target !== undefined) { event.preventDefault(); activate(tabs[target], true); }
      });
    });
  });
})();
