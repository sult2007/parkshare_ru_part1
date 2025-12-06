(function () {
  "use strict";

  var STORAGE_KEY = "ps_theme";

  function applyTheme(theme) {
    var root = document.documentElement;
    if (!root) return;
    if (theme === "dark") {
      root.classList.add("theme-dark");
    } else {
      root.classList.remove("theme-dark");
      theme = "light";
    }
    root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (_) {
      /* ignore storage errors */
    }
    updateToggle(theme);
  }

  function currentTheme() {
    var stored = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch (_) {}
    if (stored === "dark" || stored === "light") return stored;
    var prefersDark =
      window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : "light";
  }

  function updateToggle(theme) {
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    toggles.forEach(function (btn) {
      btn.setAttribute("data-theme", theme);
      btn.setAttribute("aria-pressed", theme === "dark");
    });
  }

  function initToggle() {
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    if (!toggles.length) return;
    var theme = currentTheme();
    applyTheme(theme);
    document.dispatchEvent(new CustomEvent("ps-theme-changed", { detail: { theme: theme } }));
    toggles.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var next =
          document.documentElement.getAttribute("data-theme") === "dark"
            ? "light"
            : "dark";
        applyTheme(next);
        document.dispatchEvent(
          new CustomEvent("ps-theme-changed", { detail: { theme: next } })
        );
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initToggle);
})();
