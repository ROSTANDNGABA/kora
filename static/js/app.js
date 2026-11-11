// Scripts globaux de Kora : icônes Lucide, CSRF pour HTMX, toasts, animations au scroll, compteurs.
(function () {
  function renderIcons(root) {
    if (window.lucide) {
      window.lucide.createIcons({ attrs: { "stroke-width": 2 }, nameAttr: "data-lucide" });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderIcons();
  });
  // Après chaque échange HTMX, on redessine les icônes du fragment inséré.
  document.addEventListener("htmx:afterSwap", renderIcons);

  // Jeton CSRF sur toutes les requêtes HTMX.
  document.addEventListener("htmx:configRequest", function (event) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) {
      event.detail.headers["X-CSRFToken"] = meta.getAttribute("content");
    }
  });

  // Filtres de recherche : on retire les paramètres vides pour garder des URL propres et partageables.
  document.addEventListener("htmx:configRequest", function (event) {
    var elt = event.detail.elt;
    if (!elt || elt.id !== "filters") return;
    var params = event.detail.parameters;
    Object.keys(params).forEach(function (key) {
      if (params[key] === "" || (key === "tri" && params[key] === "pertinence")) delete params[key];
    });
  });

  // Toast déclenché côté serveur : header HX-Trigger: {"toast": {"type": "success", "text": "..."}}
  document.addEventListener("toast", function (event) {
    window.dispatchEvent(new CustomEvent("kora-toast", { detail: event.detail }));
  });
})();

// Apparition au scroll et compteurs animés (IntersectionObserver). Sans JS, tout reste visible.
(function () {
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function animateCounter(el) {
    var target = parseInt(el.getAttribute("data-counter"), 10);
    if (isNaN(target)) return;
    if (reduceMotion || target < 2) { el.textContent = target.toLocaleString("fr-FR"); return; }
    var start = null, duration = 1400;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString("fr-FR");
      if (p < 1) requestAnimationFrame(step);
    }
    el.textContent = "0";
    requestAnimationFrame(step);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var reveals = document.querySelectorAll("[data-reveal]");
    var counters = document.querySelectorAll("[data-counter]");
    if (!("IntersectionObserver" in window)) {
      reveals.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        if (entry.target.hasAttribute("data-counter")) animateCounter(entry.target);
        io.unobserve(entry.target);
      });
    }, { threshold: 0.15 });
    reveals.forEach(function (el) { io.observe(el); });
    counters.forEach(function (el) { io.observe(el); });
  });
})();
