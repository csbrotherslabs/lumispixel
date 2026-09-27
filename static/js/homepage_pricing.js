(function () {
    "use strict";

    function escapeHtml(value) {
        return String(value).replace(/[&<>'"]/g, function (character) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                "'": "&#39;",
                '"': "&quot;"
            }[character];
        });
    }

    function pricingCard(plan, pricingUrl) {
        var featuredClass = plan.featured ? " lumis-pricing-card--featured" : "";
        var primaryClass = plan.featured ? " lumis-pricing-card__cta--primary" : "";
        var badge = plan.badge ? '<div class="lumis-pricing-card__badge">' + escapeHtml(plan.badge) + "</div>" : "";
        var badgeHidden = plan.badge ? "" : ' aria-hidden="true"';
        var features = (plan.features || []).map(function (feature) {
            return "<li>" + escapeHtml(feature) + "</li>";
        }).join("");
        var ctaLabel = plan.available ? (plan.code === "free" ? "Start Free" : "Choose " + plan.name) : "View " + plan.name;
        var cta = pricingUrl
            ? '<a class="lumis-pricing-card__cta' + primaryClass + '" href="' + escapeHtml(pricingUrl) + '">' + escapeHtml(ctaLabel) + "</a>"
            : "";

        return '<article class="lumis-pricing-card' + featuredClass + '" data-home-plan="' + escapeHtml(plan.code) + '">' +
            '<div class="lumis-pricing-card__badge-row"' + badgeHidden + ">" + badge + "</div>" +
            '<div class="lumis-pricing-card__header"><h3>' + escapeHtml(plan.name) + "</h3><p>" + escapeHtml(plan.audience || "") + "</p></div>" +
            '<p class="lumis-pricing-card__price" data-monthly-price="' + escapeHtml(plan.monthly) + '" data-annual-price="' + escapeHtml(plan.annual) + '">' + escapeHtml(plan.monthly) + "</p>" +
            '<ul class="lumis-pricing-card__features">' + features + "</ul>" + cta +
            (plan.available ? "" : '<p class="lumis-pricing-card__disclaimer">Upgrade availability coming after AI launch readiness.</p>') +
            "</article>";
    }

    function readCatalog() {
        var source = document.getElementById("marketing-pricing-data");
        if (!source) return [];
        try {
            var data = JSON.parse(source.textContent || "[]");
            return Array.isArray(data) ? data : [];
        } catch (error) {
            return [];
        }
    }

    function initHomepagePricing() {
        var section = document.querySelector(".page-home [data-lumis-pricing]");
        if (!section) return;

        var plansContainer = section.querySelector(".lumis-pricing-plans");
        if (!plansContainer) return;

        var plans = readCatalog();
        if (!plans.length) return;

        var existingCards = plansContainer.querySelectorAll(".lumis-pricing-card");
        var pricingLink = existingCards.length > 1 ? existingCards[1].querySelector(".lumis-pricing-card__cta") : null;
        var pricingUrl = pricingLink ? pricingLink.getAttribute("href") : "/pricing/";

        plansContainer.innerHTML = plans.map(function (plan) {
            return pricingCard(plan, pricingUrl);
        }).join("");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHomepagePricing);
    } else {
        initHomepagePricing();
    }
})();
