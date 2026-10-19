(() => {
  const section = document.getElementById("ai-photo-discovery");
  if (!section) return;
  const url = section.dataset.aiDiscoveryUrl;
  const semantic = document.getElementById("lp-semantic-toggle");
  const facial = document.getElementById("lp-facial-toggle");
  const save = document.getElementById("lp-ai-save");
  const status = document.getElementById("lp-ai-status");
  const reset = document.getElementById("lp-ai-reset");
  let loaded = false;
  let busy = false;
  let available = false;
  let persisted = false;
  const sync = () => {
    for (const toggle of [semantic, facial]) {
      const label = toggle?.closest(".lp-ai-discovery__switch")?.querySelector("small");
      if (label) label.textContent = toggle.checked ? "On" : "Off";
    }
    semantic.disabled = !loaded || busy || (!available && !persisted);
    reset.disabled = !loaded || busy;
    save.disabled = !loaded || busy || semantic.checked === persisted;
  };
  semantic.addEventListener("change", sync);
  reset.addEventListener("click", () => {
    semantic.checked = false;
    sync();
    status.textContent = "Semantic search set to Off. Save to apply the change. Facial settings are unchanged.";
  });
  const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
  sync();
  fetch(url, {credentials: "same-origin", headers: {Accept: "application/json"}})
    .then(r => { if (!r.ok) throw new Error(); return r.json(); })
    .then(data => {
      persisted = Boolean(data.semantic_enabled);
      semantic.checked = persisted;
      facial.checked = Boolean(data.facial_enabled);
      available = Boolean(data.semantic_available);
      loaded = true;
      status.textContent = available ? "Choose semantic search, then Save to apply." : "Semantic search is not yet available. You can turn off an existing opt-in.";
      sync();
    })
    .catch(() => { status.textContent = "Settings unavailable. Refresh to try again."; });
  save.addEventListener("click", async () => {
    if (!loaded || busy || save.disabled) return;
    const enabled = semantic.checked;
    busy = true;
    sync();
    status.textContent = "Saving…";
    try {
      const response = await fetch(url, {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf || ""},
        body: JSON.stringify({semantic_enabled: enabled})
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      persisted = Boolean(data.semantic_enabled);
      semantic.checked = persisted;
      status.textContent = persisted ? "Saved. Photos are queued for search indexing." : "Saved. Semantic search is off; search data removal is queued.";
    } catch {
      status.textContent = "Unable to confirm the save. Refresh to check the current setting.";
    } finally {
      busy = false;
      sync();
    }
  });
})();
