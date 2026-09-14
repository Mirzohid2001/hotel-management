(function () {
  function extraSlots(root) {
    var extraA = root.getAttribute("data-extra-adults");
    var extraC = root.getAttribute("data-extra-children");
    if (extraA !== null || extraC !== null) {
      var a = parseInt(extraA || "0", 10);
      var c = parseInt(extraC || "0", 10);
      return {
        extraAdults: isNaN(a) ? 0 : Math.max(0, a),
        extraChildren: isNaN(c) ? 0 : Math.max(0, c),
      };
    }
    var form = root.closest("form") || document;
    var adultsEl = form.querySelector('[name="adults"]');
    var childrenEl = form.querySelector('[name="children"]');
    var adults = adultsEl
      ? parseInt(adultsEl.value, 10)
      : parseInt(root.getAttribute("data-adults") || "1", 10);
    var children = childrenEl
      ? parseInt(childrenEl.value, 10)
      : parseInt(root.getAttribute("data-children") || "0", 10);
    if (isNaN(adults) || adults < 1) adults = 1;
    if (isNaN(children) || children < 0) children = 0;
    return { extraAdults: Math.max(0, adults - 1), extraChildren: children };
  }

  function rowFilled(row) {
    var guest = row.querySelector('[name$="-guest"]');
    var first = row.querySelector('[name$="-first_name"]');
    var doc = row.querySelector('[name$="-doc_number"]');
    return (
      (guest && guest.value) ||
      (first && first.value.trim()) ||
      (doc && doc.value.trim())
    );
  }

  function sync(root) {
    var slots = extraSlots(root);
    var rows = root.querySelectorAll("[data-occupant-row]");
    var visible = 0;
    rows.forEach(function (row, i) {
      var kind = row.querySelector('[name$="-kind"]');
      var show = false;
      if (i < slots.extraAdults) {
        show = true;
        if (kind && !rowFilled(row)) kind.value = "adult";
      } else if (i < slots.extraAdults + slots.extraChildren) {
        show = true;
        if (kind && !rowFilled(row)) kind.value = "child";
      }
      if (rowFilled(row)) show = true;
      row.hidden = !show;
      row.classList.toggle("is-visible", show);
      if (show) visible += 1;
    });
    var empty = root.querySelector("[data-occupant-empty]");
    if (empty) empty.hidden = visible > 0;
  }

  function bind(root) {
    if (!root) return;
    var form = root.closest("form");
    function run() {
      sync(root);
    }
    if (form) {
      ["adults", "children"].forEach(function (name) {
        var el = form.querySelector('[name="' + name + '"]');
        if (el && !el._occupantCountBound) {
          el._occupantCountBound = true;
          el.addEventListener("change", run);
          el.addEventListener("input", run);
        }
      });
    }
    run();
  }

  function bindAll(scope) {
    (scope || document).querySelectorAll("[data-occupant-root]").forEach(bind);
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindAll(document);
  });
  document.addEventListener("htmx:afterSwap", function () {
    bindAll(document);
  });
  document.addEventListener("htmx:afterSettle", function () {
    bindAll(document);
  });
})();
