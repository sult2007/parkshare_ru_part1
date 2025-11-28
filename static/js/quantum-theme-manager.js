class QuantumThemeManager {
  constructor(options = {}) {
    this.themes = options.themes || {
      dark: {
        map: "dark",
        css: "dark",
        effects: "hologram-dark",
        emotion: "calm",
      },
      light: {
        map: "standard",
        css: "light",
        effects: "hologram-light",
        emotion: "energetic",
      },
    };
    this.currentTheme = "dark";
    this.root = options.root || document.documentElement;
  }

  async switchTheme(theme) {
    const config = this.themes[theme];
    if (!config) return;

    this.currentTheme = theme;
    const tasks = [
      this.switchCSSTheme(config.css),
      this.switchEmotionalMode(config.emotion),
      this.switchCinematicEffects(config.effects),
    ];

    await Promise.all(tasks);
    this.triggerThemeTransitionAnimation();
  }

  switchCSSTheme(css) {
    this.root.dataset.quantumTheme = css;
    document.body.dataset.quantumTheme = css;
    return Promise.resolve();
  }

  switchEmotionalMode(emotion) {
    document.body.dataset.emotion = emotion;
    return Promise.resolve();
  }

  switchCinematicEffects(effects) {
    document.body.dataset.cinematic = effects;
    return Promise.resolve();
  }

  triggerThemeTransitionAnimation() {
    const flash = document.createElement("div");
    flash.className = "quantum-pulse";
    document.body.appendChild(flash);
    setTimeout(() => flash.remove(), 800);
  }

  bindToggle(buttonId) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;

    btn.addEventListener("click", () => {
      const next = this.currentTheme === "dark" ? "light" : "dark";
      btn.dataset.theme = next;
      const label = btn.querySelector(".quantum-toggle__label");
      if (label) {
        label.textContent = next === "dark" ? "Dark Matter" : "Photon";
      }
      this.switchTheme(next);
    });
  }
}

window.initQuantumThemeManager = function initQuantumThemeManager() {
  const manager = new QuantumThemeManager();
  manager.bindToggle("themeToggle");
  manager.switchTheme("dark");
  return manager;
};
