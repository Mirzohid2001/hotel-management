(function () {
  function digitsOnly(value) {
    return String(value || "").replace(/\D/g, "").slice(0, 8);
  }

  function formatDmy(value) {
    var d = digitsOnly(value);
    var out = d.slice(0, 2);
    if (d.length > 2) out += "." + d.slice(2, 4);
    if (d.length > 4) out += "." + d.slice(4, 8);
    return out;
  }

  function isoToDmy(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "").trim());
    if (!m) return "";
    return m[3] + "." + m[2] + "." + m[1];
  }

  function dmyToIso(value) {
    var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value || "").trim());
    if (!m) return "";
    var day = +m[1];
    var month = +m[2];
    var year = +m[3];
    if (year < 1900 || year > 2100) return "";
    var dt = new Date(year, month - 1, day);
    if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day) {
      return "";
    }
    return (
      String(year) +
      "-" +
      String(month).padStart(2, "0") +
      "-" +
      String(day).padStart(2, "0")
    );
  }

  function digitIndexAt(value, caret) {
    return (String(value || "").slice(0, caret || 0).match(/\d/g) || []).length;
  }

  function caretForDigitIndex(formatted, digitIndex) {
    if (digitIndex <= 0) return 0;
    var seen = 0;
    for (var i = 0; i < formatted.length; i += 1) {
      if (/\d/.test(formatted[i])) {
        seen += 1;
        if (seen === digitIndex) return i + 1;
      }
    }
    return formatted.length;
  }

  function normalizeDisplay(input) {
    var raw = (input.value || "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      input.value = isoToDmy(raw);
      return;
    }
    input.value = formatDmy(raw);
  }

  function markValidity(input, ok) {
    input.classList.toggle("is-invalid", !ok);
    input.setAttribute("aria-invalid", ok ? "false" : "true");
  }

  function fieldIso(input) {
    var digits = digitsOnly(input.value);
    if (!digits) return "";
    return dmyToIso(formatDmy(digits));
  }

  function bindInput(input) {
    if (!input || input._dmyBound) return;
    input._dmyBound = true;
    normalizeDisplay(input);
    input.addEventListener("input", function () {
      var idx = digitIndexAt(input.value, input.selectionStart);
      var formatted = formatDmy(input.value);
      input.value = formatted;
      var pos = caretForDigitIndex(formatted, idx);
      try {
        input.setSelectionRange(pos, pos);
      } catch (err) {}
      markValidity(input, true);
    });
    input.addEventListener("blur", function () {
      normalizeDisplay(input);
      var digits = digitsOnly(input.value);
      if (!digits) {
        input.value = "";
        markValidity(input, true);
        return;
      }
      var iso = dmyToIso(input.value);
      markValidity(input, !!iso);
    });
    input.addEventListener("paste", function (evt) {
      var text = ((evt.clipboardData || window.clipboardData).getData("text") || "").trim();
      var asIso = dmyToIso(isoToDmy(text)) ? isoToDmy(text) : "";
      var asDmy = dmyToIso(formatDmy(text)) ? formatDmy(text) : "";
      var next = asIso || asDmy;
      if (!next) return;
      evt.preventDefault();
      input.value = next;
      markValidity(input, true);
    });
  }

  function bindForm(form) {
    var inputs = form.querySelectorAll("[data-date-dmy]");
    if (!inputs.length) return;
    inputs.forEach(bindInput);
    if (form._dmySubmitBound) return;
    form._dmySubmitBound = true;
    form.addEventListener(
      "submit",
      function (evt) {
        var ok = true;
        var values = [];
        inputs = form.querySelectorAll("[data-date-dmy]");
        inputs.forEach(function (input) {
          normalizeDisplay(input);
          var digits = digitsOnly(input.value);
          var iso = fieldIso(input);
          if (digits && !iso) {
            ok = false;
            markValidity(input, false);
          } else if (input.required && !iso) {
            ok = false;
            markValidity(input, false);
          } else {
            markValidity(input, true);
          }
          values.push(iso);
        });
        if (!ok) {
          evt.preventDefault();
          evt.stopPropagation();
          return;
        }
        if (values.length >= 2 && values[0] && values[1] && values[1] < values[0]) {
          var tmp = inputs[0].value;
          inputs[0].value = inputs[1].value;
          inputs[1].value = tmp;
        }
      },
      true
    );
  }

  function bindAll(scope) {
    (scope || document).querySelectorAll("form").forEach(bindForm);
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
