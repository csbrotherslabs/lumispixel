(() => {
  const form = document.getElementById('client-access-settings');
  if (!form) return;
  const density = form.querySelector('[name=watermark_density]');
  const overlay = form.querySelector('[data-permission-watermark]');
  const output = form.querySelector('[data-density-value]');
  const labels = ['Light', 'Light–balanced', 'Balanced', 'Balanced–dense', 'Dense'];
  function refresh() {
    const none = form.querySelector('[name=watermark]:checked')?.value === 'none';
    density.disabled = none;
    overlay.hidden = none;
    overlay.dataset.watermarkDensity = density.value;
    output.textContent = none ? 'Off' : labels[Number(density.value) - 1];
    density.setAttribute('aria-valuetext', labels[Number(density.value) - 1]);
  }
  form.addEventListener('input', refresh);
  form.addEventListener('change', refresh);
  form.querySelector('[data-permissions-reset]').addEventListener('click', () => {
    const defaults = {view_gallery:true, download_images:true, download_originals:false, favorite_photos:true, comment:false, share_gallery:true, purchase_prints:false, automatic_gallery_lock:false};
    Object.entries(defaults).forEach(([name, value]) => { form.elements[name].checked = value; });
    form.elements.expiration_date.value = '';
    form.elements.download_expiration.value = '';
    form.querySelector('[name=watermark][value=preview]').checked = true;
    density.value = 3;
    refresh();
    form.querySelector('[data-permissions-status]').textContent = 'Defaults restored. Save changes to apply.';
  });
  refresh();
})();
