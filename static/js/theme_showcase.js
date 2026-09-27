(function () {
  "use strict";
  var carousel = document.querySelector("[data-frame-carousel]");
  if (!carousel) return;

  var slides = Array.from(carousel.querySelectorAll("[data-frame-slide]"));
  var dots = Array.from(carousel.querySelectorAll("[data-frame-dot]"));
  var currentLabel = carousel.querySelector("[data-frame-current]");
  var previousButton = carousel.querySelector("[data-frame-previous]");
  var nextButton = carousel.querySelector("[data-frame-next]");
  var current = 0;
  var timer = null;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach(function (slide, slideIndex) {
      var active = slideIndex === current;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", active ? "false" : "true");
    });
    dots.forEach(function (dot, dotIndex) {
      var active = dotIndex === current;
      dot.classList.toggle("is-active", active);
      dot.setAttribute("aria-current", active ? "true" : "false");
    });
    currentLabel.textContent = String(current + 1).padStart(2, "0");
  }

  function stop() {
    if (timer) window.clearInterval(timer);
    timer = null;
  }

  function start() {
    stop();
    if (!reduceMotion) timer = window.setInterval(function () { show(current + 1); }, 6500);
  }

  previousButton.addEventListener("click", function () { show(current - 1); start(); });
  nextButton.addEventListener("click", function () { show(current + 1); start(); });
  dots.forEach(function (dot) {
    dot.addEventListener("click", function () { show(Number(dot.dataset.frameDot)); start(); });
  });
  carousel.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { show(current - 1); start(); }
    if (event.key === "ArrowRight") { show(current + 1); start(); }
  });
  carousel.addEventListener("mouseenter", stop);
  carousel.addEventListener("mouseleave", start);
  carousel.addEventListener("focusin", stop);
  carousel.addEventListener("focusout", start);
  document.addEventListener("visibilitychange", function () { document.hidden ? stop() : start(); });
  show(0);
  start();
})();
