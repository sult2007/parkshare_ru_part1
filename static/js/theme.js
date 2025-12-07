(function () {
  "use strict";

  var STORAGE_KEY = "ps-theme";

  function readInitialTheme() {
    var preset = document.documentElement.getAttribute("data-theme");
    if (preset === "dark" || preset === "light") return preset;
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "dark" || stored === "light") return stored;
    } catch (_) {
      /* ignore storage errors */
    }
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

  function setTheme(theme) {
    var next = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {
      /* ignore */
    }
    updateToggle(next);
    document.dispatchEvent(new CustomEvent("ps-theme-changed", { detail: { theme: next } }));
  }

  function initToggle() {
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    var initial = readInitialTheme();
    setTheme(initial);
    if (!toggles.length) return;
    toggles.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
        setTheme(current === "dark" ? "light" : "dark");
      });
    });
  }

  window.ThemeController = {
    setTheme: setTheme,
    current: function () {
      return document.documentElement.getAttribute("data-theme") || readInitialTheme();
    },
  };

  document.addEventListener("DOMContentLoaded", initToggle);
})();
