(function () {
  "use strict";
  const page = document.querySelector(".business-guides-page");
  if (!page) return;

  const search = page.querySelector("#guide-search");
  const cards = Array.from(page.querySelectorAll("[data-guide-card]"));
  const count = page.querySelector("#guide-result-count");
  const selects = Array.from(page.querySelectorAll("[data-guide-filter]"));
  function filterCards() {
    const query = search.value.trim().toLowerCase();
    const selected = selects.map((select) => select.value.toLowerCase()).filter((value) => !value.startsWith("all "));
    let visible = 0;
    cards.forEach((card) => {
      const content = card.dataset.search || "";
      const show = (!query || content.includes(query)) && selected.every((value) => content.includes(value));
      card.hidden = !show;
      if (show) visible += 1;
    });
    count.textContent = visible;
  }
  search.addEventListener("input", filterCards);
  selects.forEach((select) => select.addEventListener("change", filterCards));
  page.querySelector("#clear-guide-filters").addEventListener("click", function () {
    window.setTimeout(filterCards, 0);
  });

  page.querySelectorAll(".bg-faq-item button").forEach((button) => {
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    panel.hidden = true;
    button.addEventListener("click", function () {
      const open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!open));
      panel.hidden = open;
    });
  });
})();
