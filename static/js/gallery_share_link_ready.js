(function(){
  const feedback=document.querySelector('[data-copy-feedback]');
  const copyButtons=[...document.querySelectorAll('[data-copy-gallery-link]')];

  const announce=(message)=>{if(feedback)feedback.textContent=message;};

  const setCopiedState=(sourceButton)=>{
    copyButtons.forEach((button)=>{
      button.classList.toggle('is-copied',button===sourceButton);
      const label=button.querySelector('[data-copy-label]');
      if(label)label.textContent=button===sourceButton?'Copied':'Copy Link';
    });
    announce('Secure gallery link copied to clipboard.');
    window.setTimeout(()=>{
      copyButtons.forEach((button)=>{
        button.classList.remove('is-copied');
        const label=button.querySelector('[data-copy-label]');
        if(label)label.textContent='Copy Link';
      });
      announce('');
    },2400);
  };

  const copyText=async(value)=>{
    if(navigator.clipboard&&navigator.clipboard.writeText){await navigator.clipboard.writeText(value);return;}
    const temporary=document.createElement('textarea');
    temporary.value=value;
    temporary.setAttribute('readonly','');
    temporary.style.position='fixed';
    temporary.style.opacity='0';
    document.body.appendChild(temporary);
    temporary.select();
    const copied=document.execCommand('copy');
    temporary.remove();
    if(!copied)throw new Error('copy failed');
  };

  const copyValue=async(button,target)=>{
    try{
      await copyText(target.value);
      setCopiedState(button);
    }catch(error){
      target.focus();
      target.select();
      announce('Select the link and copy it manually.');
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

  document.querySelectorAll('[data-share-gallery-link]').forEach((button)=>{
    button.addEventListener('click',async()=>{
      const shareUrl=button.dataset.shareUrl||'';
      const galleryName=button.dataset.galleryName||'Gallery';
      if(!shareUrl)return;
      try{
        if(navigator.share){
          await navigator.share({title:`${galleryName} | LumisPixel`,text:'Open this secure LumisPixel gallery.',url:shareUrl});
          announce('Gallery share dialog opened.');
        }else{
          await copyText(shareUrl);
          announce('Sharing is not available in this browser, so the secure gallery link was copied instead.');
        }
      }catch(error){
        if(error&&error.name==='AbortError')return;
        try{
          await copyText(shareUrl);
          announce('The secure gallery link was copied instead.');
        }catch(copyError){
          announce('Copy the secure gallery link above to share it manually.');
        }
      }
    });
  });

  document.querySelectorAll('[data-print-gallery-qr]').forEach((button)=>{
    button.addEventListener('click',()=>{
      const qr=document.getElementById('client-gallery-qr');
      const galleryName=document.querySelector('[data-share-gallery-link]')?.dataset.galleryName||'LumisPixel Gallery';
      if(!qr||!qr.src)return;
      const printWindow=window.open('','_blank','noopener,noreferrer');
      if(!printWindow){announce('Allow pop-ups to print the gallery QR code.');return;}
      printWindow.document.write(`<!doctype html><html><head><title>${galleryName.replace(/[<>&"']/g,'')} QR Code</title><style>body{font-family:Arial,sans-serif;text-align:center;padding:40px;color:#111}img{width:min(72vw,560px);height:auto}h1{font-size:24px;margin-bottom:20px}p{font-size:14px;color:#444}</style></head><body><h1>${galleryName.replace(/[<>&"']/g,'')}</h1><img src="${qr.src}" alt="Gallery QR code"><p>Scan to open the secure LumisPixel gallery.</p><script>window.onload=()=>{window.print();};<\/script></body></html>`);
      printWindow.document.close();
    });
  });
})();
