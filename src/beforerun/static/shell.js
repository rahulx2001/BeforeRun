// Presentation only: theme, navigation, and static illustrated-screen selection.
// No repository retrieval, investigation state, model calls, or generated findings.
(() => {
  const root = document.documentElement;
  const themeButton = document.getElementById("theme-toggle");
  const themeLabel = themeButton?.querySelector("[data-theme-label]");
  const storageKey = "beforerun:theme";
  let preference = null;
  try {
    preference = window.localStorage.getItem(storageKey);
  } catch {
    // Preference storage is optional.
  }
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  let dark = preference === "dark" || (preference !== "light" && systemDark);
  function renderTheme() {
    root.dataset.theme = dark ? "dark" : "light";
    if (themeLabel) themeLabel.textContent = dark ? "Light mode" : "Dark mode";
    themeButton?.setAttribute("aria-pressed", String(dark));
  }
  themeButton?.addEventListener("click", () => {
    dark = !dark;
    renderTheme();
    try {
      window.localStorage.setItem(storageKey, dark ? "dark" : "light");
    } catch {
      // Presentation still works when storage is unavailable.
    }
  });
  renderTheme();
  const menuButton = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  function closeMenu() {
    document.body.dataset.menuOpen = "false";
    menuButton?.setAttribute("aria-expanded", "false");
    menuButton?.setAttribute("aria-label", "Open navigation");
  }
  menuButton?.addEventListener("click", () => {
    const open = document.body.dataset.menuOpen !== "true";
    document.body.dataset.menuOpen = String(open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    if (open) sidebar?.querySelector("a")?.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.dataset.menuOpen === "true") {
      closeMenu();
      menuButton?.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (document.body.dataset.menuOpen !== "true") return;
    if (!sidebar?.contains(event.target) && !menuButton?.contains(event.target)) closeMenu();
  });
  const tabs = Array.from(document.querySelectorAll("[data-preview-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-preview-panel]"));
  function selectPreview(id, focus = false) {
    const selected = tabs.find((tab) => tab.dataset.previewTab === id);
    if (!selected) return;
    tabs.forEach((tab) => {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => { panel.hidden = panel.id !== id; });
    if (focus) selected.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      selectPreview(tab.dataset.previewTab);
      window.history.replaceState(null, "", "#" + tab.dataset.previewTab);
    });
    tab.addEventListener("keydown", (event) => {
      let next = index;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = tabs.length - 1;
      else return;
      event.preventDefault();
      selectPreview(tabs[next].dataset.previewTab, true);
      window.history.replaceState(null, "", "#" + tabs[next].dataset.previewTab);
    });
  });
  if (tabs.length) {
    selectPreview(window.location.hash.slice(1) || "needs-review");
    window.addEventListener("hashchange", () => selectPreview(window.location.hash.slice(1)));
  }
})();
