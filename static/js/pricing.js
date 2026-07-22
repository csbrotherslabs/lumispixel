(function () {
  "use strict";

  var priceData = {
    monthly: { pro: { price: "$29", billing: "Billed monthly" }, studio: { price: "$59", billing: "Billed monthly" } },
    annual: { pro: { price: "$23", billing: "Billed annually at $276" }, studio: { price: "$47", billing: "Billed annually at $564" } }
  };

  function updateBilling(mode) {
    document.querySelectorAll("[data-billing-option]").forEach(function (button) {
      var active = button.getAttribute("data-billing-option") === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-checked", active ? "true" : "false");
    });
    ["pro", "studio"].forEach(function (plan) {
      var price = document.querySelector('[data-plan-price="' + plan + '"]');
      var billing = document.querySelector('[data-plan-billing="' + plan + '"]');
      if (price) price.textContent = priceData[mode][plan].price;
      if (billing) billing.textContent = priceData[mode][plan].billing;
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
