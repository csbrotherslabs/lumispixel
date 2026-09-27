(function () {
  "use strict";

  var calendar = document.querySelector("[data-availability-calendar]");
  if (calendar) {
    var months = Array.from(calendar.querySelectorAll("[data-availability-month]"));
    var label = calendar.querySelector("[data-availability-label]");
    var previous = calendar.querySelector("[data-availability-previous]");
    var next = calendar.querySelector("[data-availability-next]");
    var current = 0;
    function showMonth(index) {
      current = Math.max(0, Math.min(index, months.length - 1));
      months.forEach(function (month, monthIndex) {
        var active = monthIndex === current;
        month.classList.toggle("is-active", active);
        month.setAttribute("aria-hidden", active ? "false" : "true");
      });
      label.textContent = months[current].dataset.label;
      previous.disabled = current === 0;
      next.disabled = current === months.length - 1;
    }
    previous.addEventListener("click", function () { showMonth(current - 1); });
    next.addEventListener("click", function () { showMonth(current + 1); });
    showMonth(0);
  }

  var equipment = document.querySelector("[data-equipment-carousel]");
  if (equipment) {
    var viewport = equipment.querySelector("[data-equipment-viewport]");
    var previousEquipment = equipment.querySelector("[data-equipment-previous]");
    var nextEquipment = equipment.querySelector("[data-equipment-next]");
    function move(direction) {
      viewport.scrollBy({left: direction * Math.max(280, viewport.clientWidth * .72), behavior: "smooth"});
    }
    previousEquipment.addEventListener("click", function () { move(-1); });
    nextEquipment.addEventListener("click", function () { move(1); });
  }
})();
