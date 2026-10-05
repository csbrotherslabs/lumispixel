(() => {
  const scheduled = new WeakSet();
  const selector = '[data-app-alert], .emp-message';
  function schedule(root) {
    const alerts = [...root.querySelectorAll(selector)];
    if (root.matches?.(selector)) alerts.push(root);
    alerts.forEach((alert) => {
      if (scheduled.has(alert)) return;
      scheduled.add(alert);
      window.setTimeout(() => alert.remove(), 10000);
    });
  }
  schedule(document);
  new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach((node) => {
      if (node.nodeType === 1) schedule(node);
    }));
  }).observe(document.body, { childList: true, subtree: true });
})();
