(function () {
  "use strict";

  const editor = document.querySelector("[data-contract-template-editor]");
  if (!editor) return;

  const content = editor.querySelector("#id_content");
  const count = editor.querySelector("[data-content-count]");
  const feedback = editor.querySelector("[data-copy-feedback]");
  const search = editor.querySelector("[data-merge-search]");

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

  editor.addEventListener("click", async function (event) {
    const insertButton = event.target.closest("[data-merge-insert]");
    const copyButton = event.target.closest("[data-merge-copy]");
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

    if (copyButton) {
      try {
        await navigator.clipboard.writeText(copyButton.dataset.mergeCopy);
        announce("Copied to clipboard.");
      } catch (_error) {
        announce("Copy unavailable. Select the token to copy it.");
      }
    }
  });

  if (content) content.addEventListener("input", updateCount);
  if (search) search.addEventListener("input", filterMergeFields);
  updateCount();
}());
