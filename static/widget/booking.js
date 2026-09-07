(function () {
  "use strict";

  var cfg = window.WIDGET_CONFIG || {};
  var slug = cfg.slug;
  var apiBase = (cfg.apiBase || "").replace(/\/$/, "");

  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  function fmtMoney(amount, currency) {
    try {
      return new Intl.NumberFormat("uz-UZ").format(Number(amount)) + " " + (currency || "");
    } catch (e) {
      return amount + " " + (currency || "");
    }
  }

  function showStep(n) {
    qsa(".widget-step").forEach(function (el) {
      el.classList.toggle("hidden", Number(el.getAttribute("data-step")) !== n);
    });
  }

  function showError(msg) {
    var box = qs("#widget-error");
    if (!box) return;
    box.textContent = msg || "";
    box.classList.toggle("hidden", !msg);
  }

  function apiUrl(path) {
    var branch = cfg.branch || "";
    if (branch) {
      return apiBase + "/widget/api/" + slug + "/" + branch + "/" + path;
    }
    return apiBase + "/widget/api/" + slug + "/" + path;
  }

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  var checkIn = qs('input[name="check_in"]');
  var checkOut = qs('input[name="check_out"]');
  if (checkIn && !checkIn.value) {
    checkIn.min = todayIso();
    checkIn.value = todayIso();
  }
  if (checkOut && !checkOut.value) {
    var d = new Date();
    d.setDate(d.getDate() + 1);
    checkOut.min = todayIso();
    checkOut.value = d.toISOString().slice(0, 10);
  }

  qs("#btn-search").addEventListener("click", function () {
    showError("");
    var cin = checkIn.value;
    var cout = checkOut.value;
    var adults = qs('input[name="adults"]').value || "2";
    if (!cin || !cout) {
      showError("Sanalarni tanlang.");
      return;
    }
    var btn = qs("#btn-search");
    btn.disabled = true;
    btn.textContent = "Qidirilmoqda…";

    fetch(apiUrl("availability/") + "?check_in=" + encodeURIComponent(cin) +
      "&check_out=" + encodeURIComponent(cout) +
      "&adults=" + encodeURIComponent(adults))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        btn.disabled = false;
        btn.textContent = "Xonalarni ko‘rish";
        if (!data.ok) {
          showError(data.error || "Xatolik");
          return;
        }
        renderRoomTypes(data.room_types || [], data.currency);
        showStep(2);
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Xonalarni ko‘rish";
        showError("Server bilan bog‘lanib bo‘lmadi.");
      });
  });

  function renderRoomTypes(rows, currency) {
    var wrap = qs("#room-types");
    var empty = qs("#no-rooms");
    wrap.innerHTML = "";
    var any = false;
    rows.forEach(function (row) {
      if (row.available) any = true;
      var card = document.createElement("div");
      card.className = "room-card" + (row.available ? "" : " disabled");
      card.innerHTML =
        '<div class="room-card-head">' +
        "<strong>" + escapeHtml(row.name) + "</strong>" +
        '<span class="price">' + fmtMoney(row.price_total, currency) + "</span>" +
        "</div>" +
        '<div class="meta">' +
        (row.available
          ? '<span class="badge-free">' + row.available_count + " ta bo‘sh</span>"
          : '<span class="badge-busy">Band (zaynit)</span>') +
        " · " + row.nights + " tun · " + row.capacity_adults + " kishi" +
        (row.description ? "<br>" + escapeHtml(row.description) : "") +
        "</div>";
      if (row.available) {
        card.addEventListener("click", function () {
          qsa(".room-card").forEach(function (c) { c.classList.remove("selected"); });
          card.classList.add("selected");
          qs("#room_type_id").value = row.id;
          showStep(3);
        });
      }
      wrap.appendChild(card);
    });
    empty.classList.toggle("hidden", any);
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  qs("#widget-form").addEventListener("submit", function (e) {
    e.preventDefault();
    showError("");
    var fd = new FormData(e.target);
    var payload = {
      check_in: fd.get("check_in"),
      check_out: fd.get("check_out"),
      adults: fd.get("adults"),
      room_type_id: fd.get("room_type_id"),
      first_name: fd.get("first_name"),
      last_name: fd.get("last_name"),
      phone: fd.get("phone"),
      email: fd.get("email"),
      notes: fd.get("notes")
    };
    if (!payload.room_type_id) {
      showError("Xona turini tanlang.");
      return;
    }
    var submitBtn = e.target.querySelector('[type="submit"]');
    submitBtn.disabled = true;

    fetch(apiUrl("book/"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        submitBtn.disabled = false;
        if (!res.body.ok) {
          showError(res.body.error || "Bron qilinmadi.");
          return;
        }
        e.target.classList.add("hidden");
        qs("#widget-success").classList.remove("hidden");
        qs("#success-text").textContent = res.body.message || ("Kod: " + res.body.code);
      })
      .catch(function () {
        submitBtn.disabled = false;
        showError("Server bilan bog‘lanib bo‘lmadi.");
      });
  });
})();
