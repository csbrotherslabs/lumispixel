(() => {
  const script = document.currentScript;
  const page = document.querySelector('.lpw-transactions-page');

  if (page && script) {
    const stylesheetHref = script.src.replace('/js/financial_transactions.js', '/css/photographer_transactions_refresh.css');
    if (!document.querySelector(`link[href="${stylesheetHref}"]`)) {
      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = stylesheetHref;
      document.head.append(stylesheet);
    }

    const actions = page.querySelector('.lpw-transactions-actions');
    const menu = actions?.querySelector('.lpw-financial-menu');
    const menuPanel = menu?.querySelector(':scope > div');
    const createInvoice = actions?.querySelector(':scope > a.lp-button');
    const recordPayment = actions?.querySelector(':scope > button[data-financial-open="payment"]');

    if (menu && menuPanel) {
      const summary = menu.querySelector(':scope > summary');
      summary?.classList.add('lpw-transactions-more-trigger');
      menuPanel.setAttribute('role', 'menu');

      if (recordPayment) {
        recordPayment.className = '';
        recordPayment.setAttribute('role', 'menuitem');
        recordPayment.innerHTML = '<i class="bi bi-cash-coin" aria-hidden="true"></i><span><strong>Record Payment</strong><small>Add a received client payment</small></span>';
        menuPanel.prepend(recordPayment);
      }

      if (createInvoice) {
        createInvoice.className = '';
        createInvoice.setAttribute('role', 'menuitem');
        createInvoice.innerHTML = '<i class="bi bi-plus-lg" aria-hidden="true"></i><span><strong>Create Invoice</strong><small>Start a new client invoice</small></span>';
        menuPanel.prepend(createInvoice);
      }

      menuPanel.querySelectorAll(':scope > a, :scope > button').forEach(item => item.setAttribute('role', 'menuitem'));
    }
  }

  const toolbar = document.querySelector('[data-bulk-toolbar]');
  if (!toolbar) return;

  const boxes = [...document.querySelectorAll('[data-record-select]')];
  const all = document.querySelector('[data-select-all]');
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  const selected = () => [...new Set(boxes.filter(box => box.checked).map(box => box.value))];
  const post = async (action, values, note = '') => {
    const data = new FormData();
    data.append('action', action);
    values.forEach(value => data.append('records', value));
    if (note) data.append('note', note);
    const response = await fetch(script.dataset.bulkEndpoint, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: data});
    if (!response.ok) throw new Error((await response.json()).error || 'The financial action could not be completed.');
    return response;
  };
  const update = async () => {
    const values = selected();
    toolbar.hidden = !values.length;
    toolbar.querySelector('[data-selected-count]').textContent = values.length;
    all.checked = boxes.length > 0 && boxes.every(box => box.checked);
    all.indeterminate = values.length > 0 && !all.checked;
    toolbar.querySelectorAll('[data-bulk-action]').forEach(button => { button.hidden = true; });
    if (!values.length) return;
    try {
      const actions = (await (await post('capabilities', values)).json()).actions;
      actions.forEach(action => {
        const button = toolbar.querySelector(`[data-bulk-action="${action}"]`);
        if (button) button.hidden = false;
      });
      toolbar.querySelector('[data-bulk-guidance]').textContent = actions.length > 2 ? 'Only actions safe for every selected record are shown.' : 'This mixed selection is limited to universally safe actions.';
    } catch (error) {
      toolbar.querySelector('[data-bulk-guidance]').textContent = error.message;
    }
  };
  boxes.forEach(box => box.addEventListener('change', () => {
    boxes.filter(item => item.value === box.value).forEach(item => { item.checked = box.checked; });
    update();
  }));
  all?.addEventListener('change', () => {
    boxes.forEach(box => { box.checked = all.checked; });
    update();
  });
  toolbar.querySelector('[data-clear-selection]').addEventListener('click', () => {
    boxes.forEach(box => { box.checked = false; });
    update();
    boxes[0]?.focus();
  });
  toolbar.addEventListener('click', async event => {
    const button = event.target.closest('[data-bulk-action]');
    if (!button) return;
    const action = button.dataset.bulkAction;
    const values = selected();
    if (action === 'export') {
      const form = document.createElement('form');
      form.method = 'post';
      form.action = script.dataset.exportEndpoint;
      form.innerHTML = `<input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">`;
      values.forEach(value => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'records';
        input.value = value;
        form.append(input);
      });
      document.body.append(form);
      form.submit();
      form.remove();
      return;
    }
    let note = '';
    if (action === 'note') {
      note = window.prompt('Internal note (visible only to your studio):', '') || '';
      if (!note.trim()) return;
    }
    if (action === 'void' && !window.confirm('Void the selected draft invoices? This cannot be undone.')) return;
    button.disabled = true;
    try {
      const response = await post(action, values, note);
      if (action === 'download') {
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'lumispixel-invoices.zip';
        link.click();
        URL.revokeObjectURL(link.href);
        button.disabled = false;
      } else {
        window.location.reload();
      }
    } catch (error) {
      toolbar.querySelector('[data-bulk-guidance]').textContent = error.message;
      button.disabled = false;
    }
  });
})();
