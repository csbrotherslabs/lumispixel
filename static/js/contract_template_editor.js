(function () {
  "use strict";

  const editor = document.querySelector("[data-contract-template-editor]");
  if (!editor) return;

  const content = editor.querySelector("#id_content");
  const count = editor.querySelector("[data-content-count]");
  const feedback = editor.querySelector("[data-merge-feedback]");
  const search = editor.querySelector("[data-merge-search]");
  const previewButton = editor.querySelector("[data-template-preview]");
  const previewDialog = editor.querySelector("[data-preview-dialog]");

  function updateCount() {
    if (content && count) count.textContent = `${content.value.length} characters`;
  }

  function filterMergeFields() {
    const query = search.value.trim().toLocaleLowerCase();
    const fields = Array.from(editor.querySelectorAll("[data-merge-field]"));
    fields.forEach(function (field) {
      field.hidden = !field.dataset.mergeSearchText.toLocaleLowerCase().includes(query);
    });
    editor.querySelectorAll("[data-merge-group]").forEach(function (heading) {
      if (heading.matches("[data-merge-field]")) return;
      heading.hidden = !fields.some(function (field) {
        return field.dataset.mergeGroup === heading.dataset.mergeGroup && !field.hidden;
      });
    });
    const empty = editor.querySelector("[data-merge-empty]");
    if (empty) empty.hidden = fields.some(function (field) { return !field.hidden; });
  }

  function announce(message) {
    if (!feedback) return;
    feedback.textContent = message;
    window.setTimeout(function () {
      if (feedback.textContent === message) feedback.textContent = "";
    }, 1800);
  }

  editor.addEventListener("click", function (event) {
    const insertButton = event.target.closest("[data-merge-insert]");
    const editorCommand = event.target.closest("[data-editor-command]");

    if (editorCommand && content) {
      content.focus();
      document.execCommand(editorCommand.dataset.editorCommand);
      updateCount();
    }

    if (insertButton && content) {
      const token = insertButton.dataset.mergeInsert;
      const start = content.selectionStart;
      const end = content.selectionEnd;
      content.setRangeText(token, start, end, "end");
      content.focus();
      content.dispatchEvent(new Event("input", { bubbles: true }));
      announce("Merge field inserted.");
    }

  });

  if (content) content.addEventListener("input", updateCount);
  if (search) search.addEventListener("input", filterMergeFields);
  if (previewButton && previewDialog) {
    previewButton.addEventListener("click", function () {
      const title = editor.querySelector("#id_title");
      const previewContent = previewDialog.querySelector("[data-preview-content]");
      previewDialog.querySelector("[data-preview-title]").textContent = title.value.trim() || "Untitled contract";
      if (content.value.trim()) {
        previewContent.textContent = content.value;
      } else {
        const empty = document.createElement("p");
        empty.className = "lp-contract-preview__empty";
        empty.textContent = "Add contract content to see its preview here.";
        previewContent.replaceChildren(empty);
      }
      previewDialog.showModal();
    });
    previewDialog.querySelector("[data-preview-close]").addEventListener("click", function () { previewDialog.close(); });
    previewDialog.addEventListener("click", function (event) { if (event.target === previewDialog) previewDialog.close(); });
  }
  updateCount();
}());
