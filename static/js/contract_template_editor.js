(function () {
  "use strict";

  const editor = document.querySelector("[data-contract-template-editor]");
  if (!editor) return;

  const content = editor.querySelector("#id_content");
  const count = editor.querySelector("[data-content-count]");
  const feedback = editor.querySelector("[data-copy-feedback]");

  function resizeContent() {
    if (!content) return;
    content.style.height = "auto";
    content.style.height = `${Math.min(content.scrollHeight, 880)}px`;
  }

  function updateCount() {
    if (content && count) count.textContent = `${content.value.length} characters`;
    resizeContent();
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
  updateCount();
}());
