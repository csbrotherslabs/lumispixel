(() => {
  const initializeLocationSelects = () => {
    const country = document.querySelector("[data-location-country]");
    const region = document.querySelector("[data-location-region]");
    if (!country || !region) return;

    // Run after the theme's ready handler has enhanced all selects, then undo
    // that enhancement for long, dependent location lists. Native selects
    // provide reliable wheel/touch scrolling and mobile pickers.
    if (window.jQuery?.fn?.niceSelect) {
      window.jQuery(country).niceSelect("destroy");
      window.jQuery(region).niceSelect("destroy");
    }

    const emptyLabel = "Select a state, province, or region";

    const replaceOptions = (regions, message = emptyLabel) => {
      region.replaceChildren(new Option(message, ""));
      regions.forEach(({ id, name }) => region.add(new Option(name, id)));
      region.required = regions.length > 0;
      region.disabled = regions.length === 0;
    };

    country.addEventListener("change", async () => {
      const countryId = country.value;
      if (!countryId) {
        replaceOptions([]);
        return;
      }

      region.disabled = true;
      region.replaceChildren(new Option("Loading regions…", ""));
      try {
        const url = new URL(country.dataset.regionsUrl, window.location.origin);
        url.searchParams.set("country", countryId);
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("Region request failed");
        const payload = await response.json();
        replaceOptions(payload.regions, payload.regions.length ? emptyLabel : "No region selection required");
      } catch (_error) {
        replaceOptions([], "Regions could not be loaded. Try again.");
        region.disabled = false;
      }
    });
  };

  if (window.jQuery) {
    window.jQuery(() => window.setTimeout(initializeLocationSelects, 0));
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeLocationSelects, { once: true });
  } else {
    initializeLocationSelects();
  }
})();
