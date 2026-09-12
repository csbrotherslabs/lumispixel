(function(){
  const button=document.querySelector('[data-copy-gallery-link]');
  if(!button)return;
  const target=document.getElementById(button.dataset.copyTarget);
  const label=button.querySelector('[data-copy-label]');
  const feedback=document.querySelector('[data-copy-feedback]');
  if(!target)return;

  const copied=()=>{
    button.classList.add('is-copied');
    if(label)label.textContent='Copied';
    if(feedback)feedback.textContent='Secure gallery link copied to clipboard.';
    window.setTimeout(()=>{
      button.classList.remove('is-copied');
      if(label)label.textContent='Copy link';
      if(feedback)feedback.textContent='';
    },2400);
  };

  button.addEventListener('click',async()=>{
    try{
      await navigator.clipboard.writeText(target.value);
      copied();
    }catch(error){
      target.focus();
      target.select();
      try{
        document.execCommand('copy');
        copied();
      }catch(copyError){
        if(feedback)feedback.textContent='Select the link and copy it manually.';
      }
    }
  });
})();
