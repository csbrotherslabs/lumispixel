(() => {
  const section = document.getElementById("ai-photo-discovery");
  if (!section) return;
  const url = section.dataset.aiDiscoveryUrl;
  const semantic = document.getElementById("lp-semantic-toggle");
  const facial = document.getElementById("lp-facial-toggle");
  const save = document.getElementById("lp-ai-save");
  const status = document.getElementById("lp-ai-status");
  const reset = document.getElementById("lp-ai-reset");
  const syncLabels = () => {
    for (const toggle of [semantic, facial]) {
      const label = toggle?.closest(".lp-ai-discovery__switch")?.querySelector("small");
      if (label) label.textContent = toggle.checked ? "On" : "Off";
    }
  };
  semantic.addEventListener("change", syncLabels);
  reset?.addEventListener("click", () => {
    semantic.checked = false;
    syncLabels();
    status.textContent = "Semantic search set to Off. Save to apply the change.";
    save.disabled = false;
  });
  const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
  let available = false;
  fetch(url, {credentials:"same-origin", headers:{"Accept":"application/json"}})
    .then(r => {if(!r.ok) throw new Error("Could not load settings"); return r.json();})
    .then(data => {
      semantic.checked = Boolean(data.semantic_enabled);
      facial.checked = Boolean(data.facial_enabled);
      syncLabels();
      available = Boolean(data.semantic_available);
      semantic.disabled = !available && !semantic.checked;
      save.disabled = !available && !semantic.checked;
      status.textContent = available
        ? "Semantic search is available for this gallery. Facial search is managed separately."
        : "Semantic indexing is awaiting platform and policy approval. Facial search remains separately controlled.";
    })
    .catch(() => {status.textContent = "Settings unavailable. No changes have been made.";});
  save.addEventListener("click", async () => {
    save.disabled = true;
    status.textContent = "Saving…";
    try {
      const response = await fetch(url, {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json","X-CSRFToken":csrf || ""},
        body:JSON.stringify({semantic_enabled:semantic.checked})
      });
      if(!response.ok) throw new Error("Settings could not be saved");
      status.textContent = "Semantic search preference saved. Indexing runs only when approved.";
      syncLabels();
    } catch {
      status.textContent = "Unable to save. Refresh to check the current setting.";
    } finally {save.disabled = !available && !semantic.checked;}
  });
})();
