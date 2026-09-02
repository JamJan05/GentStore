// The only script on the page: the copy button next to every command.
//
// Without it the commands are still selectable — `user-select: all` on the text
// makes one click select the whole line — so the button is added to the markup
// already rendered rather than replacing anything.

"use strict";

(function () {
  var RESET_AFTER_MS = 1600;

  function announce(button, done) {
    button.textContent = done ? button.dataset.done : button.dataset.label;
    button.dataset.state = done ? "done" : "";
  }

  async function copy(button) {
    var text = button.dataset.copy;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        // http://localhost has no clipboard API in every browser; fall back to
        // a selection the user can confirm with Ctrl+C.
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      announce(button, true);
      window.setTimeout(function () {
        announce(button, false);
      }, RESET_AFTER_MS);
    } catch (error) {
      // Nothing to recover: leave the label alone and let the user select it.
    }
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".copy");
    if (button) {
      copy(button);
    }
  });
})();
