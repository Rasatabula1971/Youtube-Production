/* Keyboard and accessibility helpers shared by every view (UI-16, D-124).
   - Tab bars: ←/→ move between tabs, Home/End jump; the tab is activated
     (activation follows focus, like the Production Workspace tabs). Tab bars
     re-render on click, so focus is restored by the new tab's data-* key.
   - Open drawers and the phone sidebar keep Tab focus inside them. */
(function () {
  "use strict";

  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
    'textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

  function dataKey(element) {
    return Object.keys(element.dataset).map(function (name) {
      const attr = "data-" + name.replace(/[A-Z]/g, function (c) { return "-" + c.toLowerCase(); });
      return "[" + attr + '="' + CSS.escape(element.dataset[name]) + '"]';
    }).join("");
  }

  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const tab = event.target.closest && event.target.closest('[role="tab"]');
    // The Production Workspace tabs manage their own keys.
    if (!tab || tab.hasAttribute("data-pw-tab")) return;
    const list = tab.closest('[role="tablist"]');
    if (!list) return;
    const tabs = Array.from(list.querySelectorAll('[role="tab"]')).filter(function (item) {
      return !item.disabled && item.offsetParent !== null;
    });
    const index = tabs.indexOf(tab);
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next === -1 || index === -1) return;
    event.preventDefault();
    const target = tabs[next];
    const key = dataKey(target);
    const listId = list.id;
    target.click();
    const scope = (listId && document.getElementById(listId)) || document;
    const fresh = (key && scope.querySelector('[role="tab"]' + key)) || target;
    if (document.body.contains(fresh)) fresh.focus();
  });

  function openTrap() {
    const candidates = document.querySelectorAll(".job-drawer.open, .sidebar.open");
    for (let i = candidates.length - 1; i >= 0; i -= 1) {
      if (candidates[i].offsetParent !== null || getComputedStyle(candidates[i]).position === "fixed") return candidates[i];
    }
    return null;
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Tab") return;
    const trap = openTrap();
    if (!trap) return;
    const items = Array.from(trap.querySelectorAll(FOCUSABLE)).filter(function (el) {
      return el.offsetParent !== null || el === document.activeElement;
    });
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (!trap.contains(document.activeElement)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  window.YPA11y = {
    reducedMotion: function () {
      return Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }
  };
})();
