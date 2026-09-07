/**
 * SPA navigation — HTMX hx-boost bilan React uslubidagi navigatsiya.
 * Sidebar va topbar qoladi, faqat #spa-root ichidagi kontent almashtiriladi.
 */
(function () {
  "use strict";

  /**
   * app-shell dagi hx-select="#spa-root" qisman HTMX so‘rovlariga meros bo‘lib o‘tmasin.
   * Aks holda availability / modal / walk-in javobida #spa-root topilmaydi va sahifa
   * bo‘shaydi yoki to‘liq yangilanadi.
   */
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var elt = evt.detail && evt.detail.elt;
    if (!elt || !elt.getAttribute) return;
    var target = elt.getAttribute("hx-target") || "";
    if (target && target !== "#spa-root") {
      elt.setAttribute("hx-select", "unset");
    }
  });

  var shell = document.getElementById("app-shell");
  var spaRoot = document.getElementById("spa-root");
  if (!shell || !spaRoot || !window.htmx) return;

  var progress = document.getElementById("spa-progress");

  var NAV_RULES = [
    { key: "dashboard", test: function (p) { return /^\/reports\/dashboard\/?$/.test(p); } },
    { key: "board", test: function (p) { return /^\/bookings\/board\/?$/.test(p); } },
    { key: "calendar", test: function (p) { return /^\/bookings\/calendar\/?$/.test(p); } },
    { key: "list", test: function (p) {
      return /^\/bookings\/?$/.test(p) ||
        /^\/bookings\/\d+(\/|$)/.test(p) ||
        /^\/bookings\/new\/?$/.test(p);
    } },
    { key: "inquiries", test: function (p) { return /\/bookings\/inquiries/.test(p); } },
    { key: "walk_in", test: function (p) { return /\/bookings\/walk-in/.test(p); } },
    { key: "group", test: function (p) { return /\/bookings\/groups/.test(p); } },
    { key: "guests", test: function (p) { return /^\/guests\//.test(p); } },
    { key: "properties", test: function (p) { return /^\/properties\//.test(p); } },
    { key: "housekeeping", test: function (p) { return /^\/housekeeping\//.test(p); } },
    { key: "services", test: function (p) { return /^\/services\//.test(p); } },
    { key: "inventory", test: function (p) {
      return /^\/inventory\//.test(p) && !/\/minibar\/quick/.test(p);
    } },
    { key: "minibar_quick", test: function (p) { return /\/inventory\/minibar\/quick/.test(p); } },
    { key: "maintenance", test: function (p) { return /^\/maintenance\//.test(p); } },
    { key: "cash_shift", test: function (p) { return /\/folio\/cash-shift/.test(p); } },
    { key: "city_ledger", test: function (p) {
      return /\/folio\/(city-ledger|invoices)/.test(p);
    } },
    { key: "finance", test: function (p) { return /^\/finance\//.test(p); } },
    { key: "hr", test: function (p) { return /^\/hr\//.test(p); } },
    { key: "pnl", test: function (p) { return /\/reports\/pnl/.test(p); } },
    { key: "flash", test: function (p) { return /\/reports\/flash/.test(p); } },
    { key: "audit_log", test: function (p) { return /\/reports\/audit/.test(p); } },
    { key: "staff", test: function (p) { return /^\/tenants\/staff/.test(p); } },
    { key: "profile", test: function (p) { return /\/accounts\/profile/.test(p); } },
    { key: "folio", test: function (p) { return /^\/folio\//.test(p); } },
  ];

  function activeNavKey(path) {
    for (var i = 0; i < NAV_RULES.length; i++) {
      if (NAV_RULES[i].test(path)) return NAV_RULES[i].key;
    }
    return null;
  }

  function updateNavActive() {
    var key = activeNavKey(window.location.pathname);
    shell.querySelectorAll(".sidebar nav a[data-nav]").forEach(function (a) {
      a.classList.toggle("is-active", a.getAttribute("data-nav") === key);
    });
  }

  function updateTitle(xhr) {
    if (!xhr || !xhr.responseText) return;
    try {
      var doc = new DOMParser().parseFromString(xhr.responseText, "text/html");
      var title = doc.querySelector("title");
      if (title && title.textContent) {
        document.title = title.textContent;
      }
    } catch (e) { /* ignore */ }
  }

  function showProgress() {
    if (progress) progress.hidden = false;
    spaRoot.classList.add("spa-loading");
  }

  function hideProgress() {
    if (progress) progress.hidden = true;
    spaRoot.classList.remove("spa-loading");
  }

  function isSpaNavigation(evt) {
    var detail = evt.detail;
    if (!detail || !detail.target) return false;
    return detail.target.id === "spa-root";
  }

  function refreshPartial(id, url) {
    var node = document.getElementById(id);
    if (!node || !window.htmx) return;
    htmx.ajax("GET", url || window.location.href, { target: "#" + id, swap: "outerHTML" });
  }

  document.body.addEventListener("boardRefresh", function () {
    refreshPartial("board-page");
  });

  document.body.addEventListener("calendarRefresh", function () {
    refreshPartial("calendar-page");
  });

  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    if (!isSpaNavigation(evt)) return;
    showProgress();
  });

  document.body.addEventListener("htmx:afterRequest", function (evt) {
    if (!isSpaNavigation(evt)) return;
    updateTitle(evt.detail.xhr);
  });

  document.body.addEventListener("htmx:afterSettle", function (evt) {
    if (!isSpaNavigation(evt)) return;
    hideProgress();
    updateNavActive();
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
    document.dispatchEvent(new CustomEvent("spa:navigated", { detail: { path: window.location.pathname } }));

    var walkinForm = document.getElementById("walkin-form");
    if (walkinForm && typeof walkinForm._walkinSync === "function") {
      walkinForm._walkinSync();
    }
  });

  document.body.addEventListener("htmx:historyRestore", function () {
    updateNavActive();
  });

  document.body.addEventListener("htmx:responseError", function (evt) {
    if (isSpaNavigation(evt)) hideProgress();
  });

  /* Mobile menyu — navigatsiyadan keyin yopish */
  document.body.addEventListener("htmx:afterSettle", function (evt) {
    if (!isSpaNavigation(evt)) return;
    if (window.matchMedia("(max-width: 980px)").matches && shell.classList.contains("nav-open")) {
      shell.classList.remove("nav-open");
      var toggle = document.getElementById("nav-toggle");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
      var backdrop = document.getElementById("nav-backdrop");
      if (backdrop) backdrop.hidden = true;
      document.body.classList.remove("nav-lock");
    }
  });

  updateNavActive();
})();
