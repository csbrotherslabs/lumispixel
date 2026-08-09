(() => {
  const form = document.querySelector('[data-invoice-form]'); if (!form) return;
  const number = value => Number.parseFloat(value || '0') || 0;
  const cash = value => new Intl.NumberFormat('en-US',{style:'currency',currency:form.elements.currency.value}).format(value);
  const readinessRows = {
    client: form.querySelector('[data-ready-client]'),
    details: form.querySelector('[data-ready-details]'),
    items: form.querySelector('[data-ready-items]'),
    send: form.querySelector('[data-ready-send]')
  };
  function setReadiness(row, complete, current){
    row.classList.toggle('is-complete',complete);row.classList.toggle('is-current',current);
    const icon=row.querySelector('i');icon.className=complete?'bi bi-check-circle-fill':'bi bi-circle';
  }
  function updateReadiness(){
    const selectedClient=form.elements.client.selectedOptions[0];
    const hasNewClient=Boolean(form.elements.new_client_first_name.value.trim()&&form.elements.new_client_email.value.trim());
    const hasClient=Boolean(form.elements.client.value||hasNewClient);
    const clientCanReceive=hasNewClient||selectedClient?.dataset.hasEmail==='true';
    const issueDate=form.elements.issue_date.value,dueDate=form.elements.due_date.value;
    const hasDetails=Boolean(issueDate&&form.elements.currency.value&&(!dueDate||dueDate>=issueDate));
    const hasItems=[...form.querySelectorAll('[data-line]')].some(row=>row.querySelector('[name="item_description[]"]').value.trim()&&number(row.querySelector('[name="item_quantity[]"]').value)>0);
    setReadiness(readinessRows.client,hasClient,!hasClient);
    setReadiness(readinessRows.details,hasDetails,hasClient&&!hasDetails);
    setReadiness(readinessRows.items,hasItems,hasClient&&hasDetails&&!hasItems);
    setReadiness(readinessRows.send,hasClient&&clientCanReceive&&hasDetails&&hasItems,hasClient&&hasDetails&&hasItems);
  }
  function calculate(){let subtotal=0,discount=0,tax=0,total=0;form.querySelectorAll('[data-line]').forEach(row=>{const q=number(row.querySelector('[name="item_quantity[]"]').value),price=number(row.querySelector('[name="item_unit_price[]"]').value),d=number(row.querySelector('[name="item_discount[]"]').value),t=number(row.querySelector('[name="item_tax[]"]').value),gross=q*price,off=gross*d/100,taxValue=(gross-off)*t/100,line=gross-off+taxValue;subtotal+=gross;discount+=off;tax+=taxValue;total+=line;row.querySelector('[data-line-total]').textContent=cash(line)});form.querySelector('[data-subtotal]').textContent=cash(subtotal);form.querySelector('[data-discount]').textContent='−'+cash(discount);form.querySelector('[data-tax]').textContent=cash(tax);form.querySelector('[data-total]').textContent=cash(total);form.querySelector('[data-side-total]').textContent=cash(total);document.querySelector('[data-preview-total]').textContent=cash(total)}
  form.addEventListener('input',()=>{calculate();updateReadiness()});form.addEventListener('change',updateReadiness);form.addEventListener('click',event=>{const remove=event.target.closest('[data-remove]');if(remove){remove.closest('[data-line],.lpw-schedule-row').remove();calculate();updateReadiness()}});
  form.querySelector('[data-add-line]').addEventListener('click',()=>{form.querySelector('[data-items]').append(document.querySelector('[data-line-template]').content.cloneNode(true));calculate()});
  form.querySelector('[data-add-schedule]').addEventListener('click',()=>{const row=document.createElement('div');row.className='lpw-schedule-row';row.innerHTML='<input name="schedule_label[]" placeholder="Payment name"><input name="schedule_amount[]" type="number" step=".01" min="0" placeholder="Amount"><input name="schedule_due_date[]" type="date"><button type="button" data-remove aria-label="Remove"><i class="bi bi-trash"></i></button>';form.querySelector('[data-schedules]').append(row)});
  const client=form.querySelector('[data-client]'),booking=form.querySelector('[data-booking]');client.addEventListener('change',()=>{[...booking.options].forEach(option=>option.hidden=option.dataset.client&&option.dataset.client!==client.value);if(booking.selectedOptions[0]?.hidden)booking.value=''});
  const dialog=document.querySelector('[data-preview-dialog]');form.querySelector('[data-preview]').addEventListener('click',()=>{calculate();dialog.showModal()});dialog.querySelector('[data-close-preview]').addEventListener('click',()=>dialog.close());
  form.addEventListener('submit',()=>{form.classList.add('is-saving');form.querySelectorAll('button[type="submit"],button:not([type])').forEach(button=>button.disabled=true)});calculate();updateReadiness();
})();
