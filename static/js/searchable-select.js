/**
 * Searchable <select> — type to filter guests alphabetically.
 * Keeps the native select for form submit + HTMX OOB swaps.
 */
(function () {
  "use strict";

  var OPEN_CLASS = "is-open";

  function selectedLabel(select) {
    var opt = select.options[select.selectedIndex];
    if (!opt || !opt.value) return "";
    return opt.text;
  }

  function buildMenu(wrap, select, query) {
    var menu = wrap.querySelector(".searchable-select-menu");
    if (!menu) return;
    menu.innerHTML = "";
    var q = (query || "").trim().toLowerCase();
    var count = 0;
    Array.prototype.forEach.call(select.options, function (opt) {
      if (!opt.value) return;
      var text = opt.text || "";
      if (q && text.toLowerCase().indexOf(q) === -1) return;
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      li.className = "searchable-select-option";
      if (opt.selected) li.classList.add("is-selected");
      li.dataset.value = opt.value;
      li.textContent = text;
      menu.appendChild(li);
      count += 1;
    });
    if (!count) {
      var empty = document.createElement("li");
      empty.className = "searchable-select-empty";
      empty.setAttribute("aria-disabled", "true");
      empty.textContent = "Topilmadi";
      menu.appendChild(empty);
    }
  }

  function openMenu(wrap) {
    var select = wrap.querySelector("select");
    var input = wrap.querySelector(".searchable-select-query");
    var menu = wrap.querySelector(".searchable-select-menu");
    if (!select || !input || !menu) return;
    buildMenu(wrap, select, input.dataset.filtering === "1" ? input.value : "");
    menu.hidden = false;
    wrap.classList.add(OPEN_CLASS);
  }

  function closeMenu(wrap, restoreLabel) {
    var menu = wrap.querySelector(".searchable-select-menu");
    var input = wrap.querySelector(".searchable-select-query");
    var select = wrap.querySelector("select");
    if (menu) menu.hidden = true;
    wrap.classList.remove(OPEN_CLASS);
    if (input) {
      input.dataset.filtering = "0";
      if (restoreLabel && select) input.value = selectedLabel(select);
    }
  }

  function pick(wrap, value) {
    var select = wrap.querySelector("select");
    var input = wrap.querySelector(".searchable-select-query");
    if (!select) return;
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    if (input) input.value = selectedLabel(select);
    closeMenu(wrap, false);
  }

  function bindWrap(wrap) {
    if (wrap.dataset.ssBound === "1") return;
    wrap.dataset.ssBound = "1";
    var input = wrap.querySelector(".searchable-select-query");
    var select = wrap.querySelector("select");
    if (!input || !select) return;

    input.value = selectedLabel(select);

    input.addEventListener("focus", function () {
      input.dataset.filtering = "1";
      input.select();
      openMenu(wrap);
    });

    input.addEventListener("input", function () {
      input.dataset.filtering = "1";
      openMenu(wrap);
    });

    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape") {
        closeMenu(wrap, true);
        input.blur();
      } else if (evt.key === "Enter") {
        var menu = wrap.querySelector(".searchable-select-menu");
        var first = menu && menu.querySelector(".searchable-select-option");
        if (first) {
          evt.preventDefault();
          pick(wrap, first.dataset.value);
        }
      }
    });

    wrap.addEventListener("mousedown", function (evt) {
      var opt = evt.target.closest(".searchable-select-option");
      if (!opt || !wrap.contains(opt)) return;
      evt.preventDefault();
      pick(wrap, opt.dataset.value);
    });

    select.addEventListener("change", function () {
      if (input.dataset.filtering !== "1") {
        input.value = selectedLabel(select);
      }
    });
  }

  function init(root) {
    (root || document).querySelectorAll("[data-searchable-select]").forEach(bindWrap);
  }

  document.addEventListener("click", function (evt) {
    document.querySelectorAll("[data-searchable-select]." + OPEN_CLASS).forEach(function (wrap) {
      if (!wrap.contains(evt.target)) closeMenu(wrap, true);
    });
  });

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });

  document.body.addEventListener("htmx:afterSettle", function () {
    init(document);
  });

  document.body.addEventListener("htmx:oobAfterSwap", function () {
    init(document);
    document.querySelectorAll("[data-searchable-select]").forEach(function (wrap) {
      var select = wrap.querySelector("select");
      var input = wrap.querySelector(".searchable-select-query");
      if (select && input && input.dataset.filtering !== "1") {
        input.value = selectedLabel(select);
      }
    });
  });

  document.body.addEventListener("modalClosed", function () {
    init(document);
    document.querySelectorAll("[data-searchable-select]").forEach(function (wrap) {
      var select = wrap.querySelector("select");
      var input = wrap.querySelector(".searchable-select-query");
      if (select && input) input.value = selectedLabel(select);
    });
  });

  window.initSearchableSelects = init;
})();
