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

  function setMetaTheme(theme) {
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute("content", theme === "dark" ? "#050910" : "#f4f6fb");
    }
    try {
      document.documentElement.style.colorScheme = theme;
    } catch (_) {
      /* ignore */
    }
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
    if (document.documentElement.dataset.theme !== next) {
      document.documentElement.dataset.theme = next;
    }
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (_) {
      /* ignore */
    }
    updateToggle(next);
    setMetaTheme(next);
    document.dispatchEvent(new CustomEvent("ps-theme-changed", { detail: { theme: next } }));
    return next;
  }

  function toggleTheme() {
    var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    return setTheme(current === "dark" ? "light" : "dark");
  }

  function initToggle() {
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    var initial = setTheme(readInitialTheme());
    if (!toggles.length) return;
    toggles.forEach(function (btn) {
      btn.addEventListener("click", toggleTheme);
    });
  }

  window.ThemeController = {
    setTheme: setTheme,
    toggle: toggleTheme,
    current: function () {
      return document.documentElement.getAttribute("data-theme") || readInitialTheme();
    },
  };

  document.addEventListener("DOMContentLoaded", initToggle);
})();
