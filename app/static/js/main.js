// CARTERA — Utilidades de interfaz
// Menú desplegable (acordeón), colapso de sidebar y auto-cierre de mensajes.

document.addEventListener("DOMContentLoaded", function () {
  // Inyectar CSRF automáticamente a los formularios POST
  document.addEventListener("submit", function (e) {
    if (e.target.tagName === "FORM" && e.target.method.toUpperCase() === "POST") {
      if (!e.target.querySelector('input[name="csrf_token"]')) {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = "csrf_token";
          input.value = meta.content;
          e.target.appendChild(input);
        }
      }
    }
  });

  // Auto-cierre de mensajes flash
  document.querySelectorAll(".flash").forEach(function (f) {
    setTimeout(function () {
      f.style.transition = "opacity 0.4s";
      f.style.opacity = "0";
      setTimeout(function () { f.remove(); }, 400);
    }, 5000);
  });

  // Menú desplegable por secciones (acordeón)
  document.querySelectorAll(".nav-section").forEach(function (section, index) {
    var btn = section.querySelector(".nav-section-btn");
    var body = section.querySelector(".nav-section-body");
    if (!btn || !body) return;

    var key = "cartera.section." + index;
    var saved = localStorage.getItem(key);

    if (saved === "closed") {
      section.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    } else {
      section.classList.add("open");
      btn.setAttribute("aria-expanded", "true");
    }

    btn.addEventListener("click", function () {
      var isOpen = section.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(isOpen));
      localStorage.setItem(key, isOpen ? "open" : "closed");
    });
  });

  // Colapso del sidebar (rail de iconos)
  var toggle = document.getElementById("sidebarToggle");
  if (toggle) {
    var savedSidebar = localStorage.getItem("cartera.sidebar");
    if (savedSidebar === "collapsed") {
      document.body.classList.add("sidebar-collapsed");
      toggle.setAttribute("aria-expanded", "false");
    } else {
      toggle.setAttribute("aria-expanded", "true");
    }

    toggle.addEventListener("click", function () {
      var collapsed = document.body.classList.toggle("sidebar-collapsed");
      toggle.setAttribute("aria-expanded", String(!collapsed));
      localStorage.setItem("cartera.sidebar", collapsed ? "collapsed" : "expanded");
    });
  }
});
