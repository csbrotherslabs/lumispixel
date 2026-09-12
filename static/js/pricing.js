(function () {
  "use strict";

  function updateBilling(mode) {
    document.querySelectorAll("[data-billing-option]").forEach(function (button) {
      var active = button.getAttribute("data-billing-option") === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-checked", active ? "true" : "false");
    });

    document.querySelectorAll("[data-plan-price]").forEach(function (price) {
      var value = mode === "annual"
        ? price.getAttribute("data-annual-copy")
        : price.getAttribute("data-monthly-copy");
      if (value) price.textContent = value;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-billing-option]").forEach(function (button) {
      button.addEventListener("click", function () { updateBilling(button.getAttribute("data-billing-option")); });
      button.addEventListener("keydown", function (event) {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          updateBilling(button.getAttribute("data-billing-option") === "annual" ? "monthly" : "annual");
        }
      });
    });

    document.querySelectorAll("[data-pricing-faq] button").forEach(function (button) {
      button.addEventListener("click", function () {
        var panel = document.getElementById(button.getAttribute("aria-controls"));
        var item = button.closest(".pricing-faq__item");
        var willOpen = button.getAttribute("aria-expanded") !== "true";
        document.querySelectorAll("[data-pricing-faq] button").forEach(function (other) {
          other.setAttribute("aria-expanded", "false");
          var otherItem = other.closest(".pricing-faq__item");
          var otherPanel = document.getElementById(other.getAttribute("aria-controls"));
          if (otherItem) otherItem.classList.remove("is-open");
          if (otherPanel) otherPanel.hidden = true;
        });
        button.setAttribute("aria-expanded", willOpen ? "true" : "false");
        if (item) item.classList.toggle("is-open", willOpen);
        if (panel) panel.hidden = !willOpen;
      });
    });
  });
}());
