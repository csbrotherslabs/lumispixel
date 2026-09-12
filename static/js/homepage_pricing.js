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
        var features = plan.features.map(function (feature) {
            return "<li>" + escapeHtml(feature) + "</li>";
        }).join("");
        var cta = pricingUrl
            ? '<a class="lumis-pricing-card__cta' + primaryClass + '" href="' + escapeHtml(pricingUrl) + '">' + escapeHtml(plan.cta) + "</a>"
            : "";

        return '<article class="lumis-pricing-card' + featuredClass + '" data-home-plan="' + escapeHtml(plan.code) + '">' +
            '<div class="lumis-pricing-card__badge-row"' + badgeHidden + ">" + badge + "</div>" +
            '<div class="lumis-pricing-card__header"><h3>' + escapeHtml(plan.name) + "</h3><p>" + escapeHtml(plan.audience) + "</p></div>" +
            '<p class="lumis-pricing-card__price" data-monthly-price="' + escapeHtml(plan.monthly) + '" data-annual-price="' + escapeHtml(plan.annual) + '">' + escapeHtml(plan.monthly) + "</p>" +
            '<ul class="lumis-pricing-card__features">' + features + "</ul>" + cta +
            (plan.available ? "" : '<p class="lumis-pricing-card__disclaimer">Upgrade availability coming after AI launch readiness.</p>') +
            "</article>";
    }

    function initHomepagePricing() {
        var section = document.querySelector(".page-home [data-lumis-pricing]");
        if (!section) return;

        var plansContainer = section.querySelector(".lumis-pricing-plans");
        if (!plansContainer) return;

        var existingCards = plansContainer.querySelectorAll(".lumis-pricing-card");
        var pricingLink = existingCards.length > 1 ? existingCards[1].querySelector(".lumis-pricing-card__cta") : null;
        var pricingUrl = pricingLink ? pricingLink.getAttribute("href") : window.location.pathname;

        var plans = [
            {
                code: "free",
                name: "Free",
                audience: "Build the foundation.",
                monthly: "$0",
                annual: "$0",
                features: ["3 active galleries", "5 GB storage", "Core client tools", "1 team member", "100 AI image actions"],
                cta: "View Free",
                available: true
            },
            {
                code: "pro",
                name: "Pro",
                audience: "Run the whole business.",
                monthly: "$29 / month",
                annual: "$23 / month · billed annually at $276",
                features: ["Unlimited galleries", "250 GB storage", "CRM, bookings + payments", "AI tools + automation", "2,000 AI image actions"],
                cta: "View Pro",
                badge: "Most Popular",
                featured: true,
                available: false
            },
            {
                code: "studio",
                name: "Studio",
                audience: "Scale with a team.",
                monthly: "$59 / month",
                annual: "$47 / month · billed annually at $564",
                features: ["Everything in Pro", "1 TB storage", "3 team members", "Advanced automation", "7,500 AI image actions"],
                cta: "View Studio",
                available: false
            },
            {
                code: "enterprise",
                name: "Enterprise",
                audience: "Shape it around your operation.",
                monthly: "Custom",
                annual: "Custom",
                features: ["Custom storage + AI", "Custom team limits", "Multiple brands", "API + integrations", "Onboarding + SLA"],
                cta: "View Enterprise",
                available: false
            }
        ];

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
