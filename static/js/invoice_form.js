(() => {
  const form = document.querySelector('[data-invoice-form]');
  if (!form) return;

  const number = value => Number.parseFloat(value || '0') || 0;
  const cash = value => new Intl.NumberFormat('en-US', {
    style: 'currency', currency: form.elements.currency.value
  }).format(value);
  const readinessRows = {
    client: form.querySelector('[data-ready-client]'),
    details: form.querySelector('[data-ready-details]'),
    items: form.querySelector('[data-ready-items]'),
    send: form.querySelector('[data-ready-send]')
  };

  function setReadiness(row, complete, current) {
    row.classList.toggle('is-complete', complete);
    row.classList.toggle('is-current', current);
    row.querySelector('i').className = complete ? 'bi bi-check-circle-fill' : 'bi bi-circle';
  }

  function updateReadiness() {
    const selectedClient = form.elements.client.selectedOptions[0];
    const hasNewClient = Boolean(form.elements.new_client_first_name.value.trim() && form.elements.new_client_email.value.trim());
    const hasClient = Boolean(form.elements.client.value || hasNewClient);
    const clientCanReceive = hasNewClient || selectedClient?.dataset.hasEmail === 'true';
    const issueDate = form.elements.issue_date.value;
    const dueDate = form.elements.due_date.value;
    const hasDetails = Boolean(issueDate && form.elements.currency.value && (!dueDate || dueDate >= issueDate));
    const hasItems = [...form.querySelectorAll('[data-line]')].some(row =>
      row.querySelector('[name="item_description[]"]').value.trim() &&
      number(row.querySelector('[name="item_quantity[]"]').value) > 0
    );
    setReadiness(readinessRows.client, hasClient, !hasClient);
    setReadiness(readinessRows.details, hasDetails, hasClient && !hasDetails);
    setReadiness(readinessRows.items, hasItems, hasClient && hasDetails && !hasItems);
    setReadiness(readinessRows.send, hasClient && clientCanReceive && hasDetails && hasItems, hasClient && hasDetails && hasItems);
  }

  function updateSchedule(total) {
    const rows = [...form.querySelectorAll('.lpw-schedule-row')];
    const balance = form.querySelector('[data-schedule-balance]');
    balance.hidden = rows.length === 0;
    if (!rows.length) return;
    const scheduled = rows.reduce((sum, row) => sum + number(row.querySelector('[name="schedule_amount[]"]').value), 0);
    const remaining = total - scheduled;
    balance.classList.toggle('is-balanced', Math.abs(remaining) < 0.005);
    balance.innerHTML = `<span>Scheduled payments <strong>${cash(scheduled)}</strong></span><span>Invoice total <strong>${cash(total)}</strong></span><span>Remaining <strong>${cash(remaining)}</strong></span>`;
  }

  function updateCurrencyPrefixes() {
    const parts = new Intl.NumberFormat('en-US', {style: 'currency', currency: form.elements.currency.value}).formatToParts(0);
    const symbol = parts.find(part => part.type === 'currency')?.value || form.elements.currency.value;
    form.querySelectorAll('[data-currency-prefix]').forEach(prefix => { prefix.textContent = symbol; });
  }

  function calculate() {
    let subtotal = 0, discount = 0, tax = 0, total = 0;
    form.querySelectorAll('[data-line]').forEach(row => {
      const quantity = number(row.querySelector('[name="item_quantity[]"]').value);
      const price = number(row.querySelector('[name="item_unit_price[]"]').value);
      const discountRate = number(row.querySelector('[name="item_discount[]"]').value);
      const taxRate = number(row.querySelector('[name="item_tax[]"]').value);
      const gross = quantity * price;
      const discountValue = gross * discountRate / 100;
      const taxValue = (gross - discountValue) * taxRate / 100;
      const line = gross - discountValue + taxValue;
      subtotal += gross; discount += discountValue; tax += taxValue; total += line;
      row.querySelector('[data-line-total]').textContent = cash(line);
    });
    form.querySelector('[data-subtotal]').textContent = cash(subtotal);
    form.querySelector('[data-discount]').textContent = `−${cash(discount)}`;
    form.querySelector('[data-tax]').textContent = cash(tax);
    form.querySelector('[data-total]').textContent = cash(total);
    form.querySelector('[data-side-total]').textContent = cash(total);
    document.querySelector('[data-preview-total]').textContent = cash(total);
    updateCurrencyPrefixes();
    updateSchedule(total);
  }

  form.addEventListener('input', () => { calculate(); updateReadiness(); });
  form.addEventListener('change', () => { calculate(); updateReadiness(); });
  form.addEventListener('click', event => {
    const remove = event.target.closest('[data-remove]');
    if (!remove) return;
    remove.closest('[data-line],.lpw-schedule-row').remove();
    calculate(); updateReadiness();
  });

  form.querySelector('[data-add-line]').addEventListener('click', () => {
    const fragment = document.querySelector('[data-line-template]').content.cloneNode(true);
    const row = fragment.querySelector('[data-line]');
    row.classList.add('is-new');
    form.querySelector('[data-items]').append(fragment);
    row.querySelector('[name="item_description[]"]').focus();
    calculate(); updateReadiness();
  });
  form.querySelector('[data-add-schedule]').addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'lpw-schedule-row is-new';
    row.innerHTML = '<input name="schedule_label[]" aria-label="Payment name" placeholder="Milestone name"><label class="money"><span aria-hidden="true" data-currency-prefix>$</span><input name="schedule_amount[]" aria-label="Payment amount" type="number" step=".01" min="0" placeholder="0.00"></label><input name="schedule_due_date[]" aria-label="Payment due date" type="date"><button class="lpw-line-remove" type="button" data-remove aria-label="Remove payment milestone" data-tooltip="Remove milestone"><i class="bi bi-trash" aria-hidden="true"></i></button>';
    form.querySelector('[data-schedules]').append(row);
    row.querySelector('[name="schedule_label[]"]').focus();
    calculate();
  });

  const client = form.querySelector('[data-client]');
  const booking = form.querySelector('[data-booking]');
  client.addEventListener('change', () => {
    [...booking.options].forEach(option => { option.hidden = option.dataset.client && option.dataset.client !== client.value; });
    if (booking.selectedOptions[0]?.hidden) booking.value = '';
  });

  const dialog = document.querySelector('[data-preview-dialog]');
  form.querySelector('[data-preview]').addEventListener('click', () => { calculate(); dialog.showModal(); });
  dialog.querySelector('[data-close-preview]').addEventListener('click', () => dialog.close());
  form.addEventListener('submit', event => {
    if (form.classList.contains('is-saving')) { event.preventDefault(); return; }
    form.classList.add('is-saving');
    const submitter = event.submitter;
    if (submitter) {
      submitter.dataset.label = submitter.innerHTML;
      submitter.innerHTML = `<span class="lpw-button-spinner" aria-hidden="true"></span>${submitter.value === 'send' ? 'Sending…' : 'Saving…'}`;
    }
    form.querySelectorAll('button[type="submit"],button:not([type])').forEach(button => { button.disabled = true; });
  });

  calculate(); updateReadiness();
})();
