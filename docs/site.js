(() => {
  const STORAGE_KEY = "lumanova-site-lang";

  const normalizeLang = (value) => (value === "zh" || value === "en" ? value : null);

  const applyLanguage = (lang) => {
    const next = normalizeLang(lang);
    const html = document.documentElement;
    html.setAttribute("data-ui-lang", next);
    html.lang = next === "zh" ? "zh-CN" : "en";
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (_error) {
      // Ignore storage failures in private or restricted contexts.
    }

    document.querySelectorAll("[data-lang]").forEach((node) => {
      node.hidden = node.getAttribute("data-lang") !== next;
    });

    document.querySelectorAll("[data-set-lang]").forEach((button) => {
      const active = button.getAttribute("data-set-lang") === next;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.classList.toggle("is-active", active);
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    const urlLang = normalizeLang(new URLSearchParams(window.location.search).get("lang"));
    let savedLang = null;
    try {
      savedLang = normalizeLang(window.localStorage.getItem(STORAGE_KEY));
    } catch (_error) {
      savedLang = null;
    }
    applyLanguage(urlLang || savedLang || "en");

    document.querySelectorAll("[data-set-lang]").forEach((button) => {
      button.addEventListener("click", () => applyLanguage(button.getAttribute("data-set-lang")));
    });
  });
})();
