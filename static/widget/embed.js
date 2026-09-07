(function () {
  "use strict";
  var script = document.currentScript;
  if (!script) return;
  var hotel = script.getAttribute("data-hotel");
  var branch = script.getAttribute("data-branch") || "";
  var base = (script.getAttribute("data-base") || "").replace(/\/$/, "");
  if (!hotel || !base) return;

  var path = branch
    ? base + "/widget/" + hotel + "/" + branch + "/"
    : base + "/widget/" + hotel + "/";
  var iframe = document.createElement("iframe");
  iframe.src = path;
  iframe.title = "Onlayn bron";
  iframe.loading = "lazy";
  iframe.setAttribute(
    "style",
    "width:100%;min-height:720px;border:0;border-radius:12px;background:#faf8f5"
  );

  var mount = script.getAttribute("data-mount");
  var parent = mount ? document.querySelector(mount) : script.parentNode;
  if (parent) {
    if (mount) {
      parent.appendChild(iframe);
    } else {
      parent.insertBefore(iframe, script);
    }
  }
})();
