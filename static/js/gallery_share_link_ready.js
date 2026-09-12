(function(){
  const feedback=document.querySelector('[data-copy-feedback]');
  const copyButtons=[...document.querySelectorAll('[data-copy-gallery-link]')];

  const setCopiedState=(sourceButton)=>{
    copyButtons.forEach((button)=>{
      button.classList.toggle('is-copied',button===sourceButton);
      const label=button.querySelector('[data-copy-label]');
      if(label)label.textContent=button===sourceButton?'Copied':'Copy Link';
    });
    if(feedback)feedback.textContent='Secure gallery link copied to clipboard.';
    window.setTimeout(()=>{
      copyButtons.forEach((button)=>{
        button.classList.remove('is-copied');
        const label=button.querySelector('[data-copy-label]');
        if(label)label.textContent='Copy Link';
      });
      if(feedback)feedback.textContent='';
    },2400);
  };

  const copyValue=async(button,target)=>{
    try{
      await navigator.clipboard.writeText(target.value);
      setCopiedState(button);
    }catch(error){
      target.focus();
      target.select();
      try{
        document.execCommand('copy');
        setCopiedState(button);
      }catch(copyError){
        if(feedback)feedback.textContent='Select the link and copy it manually.';
      }
    }
  };

  copyButtons.forEach((button)=>{
    const target=document.getElementById(button.dataset.copyTarget);
    if(!target)return;
    button.addEventListener('click',()=>copyValue(button,target));
  });

  document.querySelectorAll('[data-email-gallery-link]').forEach((button)=>{
    button.addEventListener('click',()=>{
      const email=button.dataset.email||'';
      const shareUrl=button.dataset.shareUrl||'';
      const galleryName=button.dataset.galleryName||'your gallery';
      const subject=`Your LumisPixel gallery: ${galleryName}`;
      const body=`Your secure LumisPixel gallery is ready.\n\nOpen gallery: ${shareUrl}\n\nPlease keep this private invitation link secure.`;
      window.location.href=`mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    });
  });
})();
