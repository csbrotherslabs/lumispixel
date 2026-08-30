(function () {
  "use strict";

  var carousel = document.querySelector("[data-review-carousel]");
  if (!carousel) return;

  var slides = Array.from(carousel.querySelectorAll("[data-review-slide]"));
  var previousButton = carousel.querySelector("[data-review-previous]");
  var nextButton = carousel.querySelector("[data-review-next]");
  var currentLabel = carousel.querySelector("[data-review-current]");
  var current = 0;

  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach(function (slide, slideIndex) {
      var active = slideIndex === current;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", active ? "false" : "true");
    });
    currentLabel.textContent = String(current + 1).padStart(2, "0");
  }

  previousButton.addEventListener("click", function () { show(current - 1); });
  nextButton.addEventListener("click", function () { show(current + 1); });
  carousel.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") show(current - 1);
    if (event.key === "ArrowRight") show(current + 1);
  });

  show(0);
})();
