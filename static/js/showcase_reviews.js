(function () {
  "use strict";

  var carousel = document.querySelector("[data-review-carousel]");
  if (!carousel) return;

  var slides = Array.from(carousel.querySelectorAll("[data-review-slide]"));
  var previousButton = carousel.querySelector("[data-review-previous]");
  var nextButton = carousel.querySelector("[data-review-next]");
  var currentLabel = carousel.querySelector("[data-review-current]");
  var modal = document.querySelector("[data-review-modal]");
  var modalCopy = modal.querySelector("[data-review-modal-copy]");
  var modalClient = modal.querySelector("[data-review-modal-client]");
  var modalCloseButtons = Array.from(modal.querySelectorAll("[data-review-modal-close]"));
  var current = 0;
  var lastTrigger = null;
  var resizeTimer = null;

  function updateOverflowControls() {
    slides.forEach(function (slide) {
      var excerpt = slide.querySelector("[data-review-excerpt]");
      var moreButton = slide.querySelector("[data-review-more]");
      moreButton.hidden = excerpt.scrollHeight <= excerpt.clientHeight + 1;
    });
  }

  function openModal(button) {
    var slide = button.closest("[data-review-slide]");
    var clientName = slide.querySelector(".showcase-review-card__client strong").textContent;
    var clientDetails = slide.querySelector(".showcase-review-card__client span").textContent;
    lastTrigger = button;
    modalCopy.textContent = slide.querySelector("[data-review-excerpt]").textContent.trim();
    modalClient.textContent = clientName + " · " + clientDetails;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("showcase-review-modal-open");
    modal.querySelector(".showcase-review-modal__close").focus();
  }

  function closeModal() {
    if (modal.hidden) return;
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("showcase-review-modal-open");
    if (lastTrigger) lastTrigger.focus();
  }

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
  slides.forEach(function (slide) {
    slide.querySelector("[data-review-more]").addEventListener("click", function (event) {
      openModal(event.currentTarget);
    });
  });
  modalCloseButtons.forEach(function (button) {
    button.addEventListener("click", closeModal);
  });
  carousel.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") show(current - 1);
    if (event.key === "ArrowRight") show(current + 1);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });
  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(updateOverflowControls, 120);
  });

  show(0);
  window.requestAnimationFrame(updateOverflowControls);
  window.addEventListener("load", updateOverflowControls);
})();
