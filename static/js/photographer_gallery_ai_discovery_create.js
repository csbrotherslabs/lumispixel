(() => {
  const section=document.querySelector(".lp-gallery-create-modern .lp-ai-discovery");
  if(!section) return;
  const toggle=section.querySelector("#lp-semantic-toggle");
  const label=toggle?.closest(".lp-ai-discovery__switch")?.querySelector("small");
  const reset=section.querySelector("#lp-ai-reset");
  const status=section.querySelector("#lp-ai-status");
  const sync=()=>{if(label)label.textContent=toggle.checked?"On":"Off";};
  toggle?.addEventListener("change",sync);
  reset?.addEventListener("click",()=>{toggle.checked=false;sync();status.textContent="Both AI discovery features will start off.";});
  sync();
})();