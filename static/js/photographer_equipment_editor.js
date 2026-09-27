(function () {
  "use strict";

  var editor = document.querySelector("[data-equipment-editor]");
  if (!editor) return;

  var items = editor.querySelector("[data-equipment-items]");
  var template = editor.querySelector("[data-equipment-template]");
  var indicesInput = editor.querySelector("[data-equipment-indices]");
  var nextIndex = Number(editor.dataset.nextIndex || 1);

  function visibleItems() {
    return Array.from(items.querySelectorAll("[data-equipment-item]")).filter(function (item) {
      return !item.classList.contains("is-removed");
    });
  }

  function sync() {
    var allItems = Array.from(items.querySelectorAll("[data-equipment-item]"));
    indicesInput.value = allItems.map(function (item) { return item.dataset.equipmentIndex; }).join(",");
    visibleItems().forEach(function (item, index) {
      item.querySelector("[data-equipment-number]").textContent = "Equipment " + (index + 1);
    });
  }

  function addItem() {
    var markup = template.innerHTML.replaceAll("__index__", String(nextIndex));
    items.insertAdjacentHTML("beforeend", markup);
    nextIndex += 1;
    editor.dataset.nextIndex = String(nextIndex);
    sync();
    var added = items.lastElementChild;
    added.querySelector('input[type="text"]').focus();
  }

  function removeItem(item) {
    if (item.hasAttribute("data-equipment-saved")) {
      var removed = !item.classList.contains("is-removed");
      item.classList.toggle("is-removed", removed);
      item.querySelector("[data-equipment-remove]").value = removed ? "1" : "";
      item.querySelector("[data-equipment-remove-button]").innerHTML = removed ? '<i class="bi bi-arrow-counterclockwise"></i> Undo Removal' : '<i class="bi bi-trash3"></i> Remove Equipment';
    } else {
      item.remove();
    }
    sync();
  }

  editor.querySelector("[data-equipment-add]").addEventListener("click", addItem);
  items.addEventListener("click", function (event) {
    var button = event.target.closest("[data-equipment-remove-button]");
    if (button) removeItem(button.closest("[data-equipment-item]"));
  });
  sync();
})();
