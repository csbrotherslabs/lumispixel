(function(){
  const root=document.querySelector('.lp-access-modern');
  if(!root||root.dataset.inviteActionsReady==='true')return;
  root.dataset.inviteActionsReady='true';

  const modal=document.getElementById('lp-invite-confirm-modal');
  const modalDialog=modal?.querySelector('.lp-invite-confirm-modal__dialog');
  const confirmForm=document.getElementById('lp-invite-confirm-form');
  const idInput=document.getElementById('lp-invite-confirm-id');
  const actionInput=document.getElementById('lp-invite-confirm-action');
  const title=document.getElementById('lp-invite-confirm-title');
  const copy=document.getElementById('lp-invite-confirm-copy');
  const submit=document.getElementById('lp-invite-confirm-submit');
  const defaultConfirmAction=`${window.location.pathname}${window.location.search}`;
  let lastTrigger=null;

  const galleryMatch=window.location.pathname.match(/\/photographer\/workspace\/galleries\/(\d+)\//);
  const galleryId=galleryMatch?.[1];
  const csrf=confirmForm?.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
  if(galleryId&&csrf){
    root.querySelectorAll('[data-invite-confirm][data-invitation-id]').forEach((button)=>{
      const panel=button.closest('.lp-invite-action-buttons');
      const invitationId=button.dataset.invitationId;
      if(!panel||!invitationId||panel.querySelector('[data-gallery-share-link]'))return;
      const form=document.createElement('form');
      form.method='post';
      form.action=`/galleries/share-link/${galleryId}/${invitationId}/`;
      form.dataset.galleryShareLink='true';
      form.style.display='inline-flex';
      const token=document.createElement('input');
      token.type='hidden';token.name='csrfmiddlewaretoken';token.value=csrf;
      const share=document.createElement('button');
      share.type='submit';share.className='lpw-btn lpw-btn-primary';share.textContent='Create secure link';
      form.append(token,share);
      panel.prepend(form);
    });
  }

  const closeExpandedRows=(exceptId)=>{
    root.querySelectorAll('[data-invite-actions-toggle]').forEach((toggle)=>{
      const rowId=toggle.dataset.inviteActionsToggle;
      if(rowId===exceptId)return;
      const row=document.getElementById(rowId);
      toggle.setAttribute('aria-expanded','false');
      if(row)row.hidden=true;
    });
  };

  root.addEventListener('click',(event)=>{
    const toggle=event.target.closest('[data-invite-actions-toggle]');
    if(toggle){
      const rowId=toggle.dataset.inviteActionsToggle;
      const row=document.getElementById(rowId);
      const willOpen=toggle.getAttribute('aria-expanded')!=='true';
      closeExpandedRows(willOpen?rowId:null);
      toggle.setAttribute('aria-expanded',String(willOpen));
      if(row)row.hidden=!willOpen;
      return;
    }

    const actionButton=event.target.closest('[data-invite-confirm]');
    if(!actionButton||!modal||!confirmForm)return;
    lastTrigger=actionButton;
    const action=actionButton.dataset.action;
    const actionLabel=actionButton.dataset.actionLabel||'Confirm action';
    const clientName=actionButton.dataset.clientName||'this client';
    const invitationId=actionButton.dataset.invitationId;

    confirmForm.action=action==='resend'&&actionButton.dataset.resendUrl?actionButton.dataset.resendUrl:defaultConfirmAction;
    idInput.value=invitationId||'';
    actionInput.value=action||'';
    title.textContent=actionLabel;
    copy.textContent=`Are you sure you want to ${actionLabel.toLowerCase()} for ${clientName}?`;
    submit.textContent=action==='remove'?'Remove':action==='disable'?'Disable':'Resend';
    modal.classList.toggle('is-danger',action==='remove');
    modal.hidden=false;
    document.body.classList.add('lp-invite-modal-open');
    requestAnimationFrame(()=>modalDialog?.focus());
  });

  const closeModal=()=>{
    if(!modal||modal.hidden)return;
    modal.hidden=true;
    modal.classList.remove('is-danger');
    document.body.classList.remove('lp-invite-modal-open');
    lastTrigger?.focus();
  };

  modal?.addEventListener('click',(event)=>{
    if(event.target.closest('[data-invite-modal-close]'))closeModal();
  });

  document.addEventListener('keydown',(event)=>{
    if(event.key==='Escape'&&modal&&!modal.hidden){
      event.preventDefault();
      closeModal();
      return;
    }
    if(event.key!=='Tab'||!modal||modal.hidden||!modalDialog)return;
    const focusable=[...modalDialog.querySelectorAll('button:not([disabled]),[href],input:not([type="hidden"]),select,textarea,[tabindex]:not([tabindex="-1"])')];
    if(!focusable.length)return;
    const first=focusable[0];
    const last=focusable[focusable.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
})();
