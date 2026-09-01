// CARTERA — Utilidades de interfaz y WhatsApp Engine
// Menú desplegable, Drawer móvil, 1-Tap WhatsApp, Envío Masivo y Tipificación.

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

  // Colapso del sidebar en Desktop (rail de iconos)
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

  // ──────────────── DRAWER MÓVIL (OFF-CANVAS) ────────────────
  var mobileMenuBtn = document.getElementById("mobileMenuBtn");
  var sidebarBackdrop = document.getElementById("sidebarBackdrop");
  var sidebarCloseBtn = document.getElementById("sidebarCloseBtn");

  function openMobileDrawer() {
    document.body.classList.add("sidebar-open");
  }

  function closeMobileDrawer() {
    document.body.classList.remove("sidebar-open");
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", openMobileDrawer);
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", closeMobileDrawer);
  }
  if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener("click", closeMobileDrawer);
  }

  // Cerrar drawer al hacer clic en un enlace del nav en móvil
  document.querySelectorAll(".sidebar .nav a").forEach(function (link) {
    link.addEventListener("click", function () {
      if (window.innerWidth <= 768) {
        closeMobileDrawer();
      }
    });
  });

  // ──────────────── MOTOR WHATSAPP 1-TAP (EDITABLE) ────────────────
  var waModalBackdrop = document.getElementById("waModalBackdrop");
  var waModalCloseBtn = document.getElementById("waModalCloseBtn");
  var waClientName = document.getElementById("waClientName");
  var waClientPhone = document.getElementById("waClientPhone");
  var waMessageText = document.getElementById("waMessageText");
  var waCharCount = document.getElementById("waCharCount");
  var waCopyBtn = document.getElementById("waCopyBtn");
  var waSendBtn = document.getElementById("waSendBtn");
  var waTemplateTabs = document.querySelectorAll(".wa-tab");

  var currentWAData = {
    name: "",
    phone: "",
    loan: "",
    installment: "",
    amount: "",
    dueDate: "",
    balance: "",
    template: "mora"
  };

  var WA_TEMPLATES = {
    mora: function (d) {
      return "Hola " + d.name + ", le recordamos que su cuota #" + (d.installment || "1") + " del préstamo " + (d.loan || "") + " por valor de " + (d.amount || "") + " venció el " + (d.dueDate || "") + ". Saldo pendiente: " + (d.balance || d.amount || "") + ". Por favor confirme su comprobante de pago por este medio.";
    },
    recordatorio: function (d) {
      return "Hola " + d.name + ", le recordamos cordialmente que su próxima cuota #" + (d.installment || "1") + " del préstamo " + (d.loan || "") + " por valor de " + (d.amount || "") + " vence el " + (d.dueDate || "") + ". Saldo total: " + (d.balance || "") + ". Evite recargos realizando su pago a tiempo.";
    },
    acuerdo: function (d) {
      return "Hola " + d.name + ", confirmamos su acuerdo de pago para el " + (d.dueDate || "próximo día hábil") + " por valor de " + (d.amount || "") + ". Agradecemos su compromiso y quedamos atentos a su soporte.";
    },
    libre: function (d) {
      return "Hola " + d.name + ", nos comunicamos de Cartera respecto a su crédito " + (d.loan || "") + ".";
    }
  };

  function updateWAMessage() {
    if (!waMessageText) return;
    var generator = WA_TEMPLATES[currentWAData.template] || WA_TEMPLATES.mora;
    waMessageText.value = generator(currentWAData);
    updateCharCounter();
  }

  function updateCharCounter() {
    if (!waMessageText || !waCharCount) return;
    var len = waMessageText.value.length;
    waCharCount.textContent = len + " caracteres";
  }

  if (waMessageText) {
    waMessageText.addEventListener("input", updateCharCounter);
  }

  // Cambio de pestañas de plantilla
  waTemplateTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      waTemplateTabs.forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      currentWAData.template = tab.getAttribute("data-template");
      updateWAMessage();
    });
  });

  // Abrir modal desde botones de WhatsApp
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-wa-trigger]");
    if (!trigger) return;
    e.preventDefault();

    currentWAData = {
      name: trigger.getAttribute("data-name") || "Cliente",
      phone: trigger.getAttribute("data-phone") || "",
      loan: trigger.getAttribute("data-loan-code") || "",
      installment: trigger.getAttribute("data-installment") || "1",
      amount: trigger.getAttribute("data-amount") || "",
      dueDate: trigger.getAttribute("data-due-date") || "",
      balance: trigger.getAttribute("data-balance") || "",
      template: trigger.getAttribute("data-default-template") || "mora"
    };

    if (waClientName) waClientName.value = currentWAData.name;
    if (waClientPhone) waClientPhone.value = currentWAData.phone;

    // Activar pestaña de plantilla correspondiente
    waTemplateTabs.forEach(function (t) {
      if (t.getAttribute("data-template") === currentWAData.template) {
        t.classList.add("active");
      } else {
        t.classList.remove("active");
      }
    });

    updateWAMessage();

    if (waModalBackdrop) {
      waModalBackdrop.style.display = "flex";
    }
  });

  // Cerrar modal WhatsApp
  if (waModalCloseBtn) {
    waModalCloseBtn.addEventListener("click", function () {
      if (waModalBackdrop) waModalBackdrop.style.display = "none";
    });
  }
  if (waModalBackdrop) {
    waModalBackdrop.addEventListener("click", function (e) {
      if (e.target === waModalBackdrop) {
        waModalBackdrop.style.display = "none";
      }
    });
  }

  // Copiar texto
  if (waCopyBtn) {
    waCopyBtn.addEventListener("click", function () {
      if (!waMessageText) return;
      navigator.clipboard.writeText(waMessageText.value).then(function () {
        var origText = waCopyBtn.innerHTML;
        waCopyBtn.innerHTML = "Texto copiado";
        setTimeout(function () { waCopyBtn.innerHTML = origText; }, 2000);
      });
    });
  }

  // Formatear teléfono y abrir WhatsApp
  function formatWAPhone(raw) {
    var digits = (raw || "").replace(/\D/g, "");
    if (!digits) return "";
    if (digits.length === 10 && digits.startsWith("3")) {
      return "57" + digits; // Colombia
    }
    return digits;
  }

  if (waSendBtn) {
    waSendBtn.addEventListener("click", function () {
      var phone = waClientPhone ? waClientPhone.value : currentWAData.phone;
      var cleanPhone = formatWAPhone(phone);
      if (!cleanPhone) {
        alert("Por favor ingrese un número de teléfono válido.");
        return;
      }
      var text = waMessageText ? waMessageText.value : "";
      var url = "https://wa.me/" + cleanPhone + "?text=" + encodeURIComponent(text);
      window.open(url, "_blank");
      if (waModalBackdrop) waModalBackdrop.style.display = "none";
    });
  }

  // ──────────────── DESPACHO MASIVO ASISTIDO ────────────────
  var waBulkModalBackdrop = document.getElementById("waBulkModalBackdrop");
  var waBulkCloseBtn = document.getElementById("waBulkCloseBtn");
  var waBulkCounter = document.getElementById("waBulkCounter");
  var waBulkProgressText = document.getElementById("waBulkProgressText");
  var waBulkProgressPct = document.getElementById("waBulkProgressPct");
  var waBulkProgressBar = document.getElementById("waBulkProgressBar");
  var waBulkCurrentName = document.getElementById("waBulkCurrentName");
  var waBulkCurrentDetails = document.getElementById("waBulkCurrentDetails");
  var waBulkCurrentPhone = document.getElementById("waBulkCurrentPhone");
  var waBulkMessageText = document.getElementById("waBulkMessageText");
  var waBulkSendNextBtn = document.getElementById("waBulkSendNextBtn");
  var waBulkSkipBtn = document.getElementById("waBulkSkipBtn");

  var bulkQueue = [];
  var bulkCurrentIndex = 0;

  window.startWhatsAppBulk = function (items) {
    if (!items || items.length === 0) {
      alert("No hay clientes seleccionados para envío masivo.");
      return;
    }
    bulkQueue = items;
    bulkCurrentIndex = 0;
    renderBulkItem();
    if (waBulkModalBackdrop) waBulkModalBackdrop.style.display = "flex";
  };

  function renderBulkItem() {
    if (bulkCurrentIndex >= bulkQueue.length) {
      if (waBulkModalBackdrop) waBulkModalBackdrop.style.display = "none";
      alert("Todos los mensajes de la cola masiva fueron procesados con éxito.");
      return;
    }

    var item = bulkQueue[bulkCurrentIndex];
    var total = bulkQueue.length;
    var currentNum = bulkCurrentIndex + 1;
    var pct = Math.round((currentNum / total) * 100);

    if (waBulkCounter) waBulkCounter.textContent = "Mensaje " + currentNum + " de " + total;
    if (waBulkProgressText) waBulkProgressText.textContent = "Progreso: " + currentNum + " de " + total + " (" + item.name + ")";
    if (waBulkProgressPct) waBulkProgressPct.textContent = pct + "%";
    if (waBulkProgressBar) waBulkProgressBar.style.width = pct + "%";

    if (waBulkCurrentName) waBulkCurrentName.textContent = item.name;
    if (waBulkCurrentDetails) waBulkCurrentDetails.textContent = "Préstamo " + item.loan + " · Cuota #" + item.installment + " (venció " + item.dueDate + ")";
    if (waBulkCurrentPhone) waBulkCurrentPhone.textContent = item.phone || "Sin teléfono";

    if (waBulkMessageText) {
      var templateGen = WA_TEMPLATES[item.template || "mora"] || WA_TEMPLATES.mora;
      waBulkMessageText.value = templateGen(item);
    }
  }

  function advanceBulk(sendWhatsApp) {
    if (bulkCurrentIndex >= bulkQueue.length) return;
    var item = bulkQueue[bulkCurrentIndex];

    if (sendWhatsApp && item.phone) {
      var phone = formatWAPhone(item.phone);
      var text = waBulkMessageText ? waBulkMessageText.value : "";
      var url = "https://wa.me/" + phone + "?text=" + encodeURIComponent(text);
      window.open(url, "_blank");
    }

    bulkCurrentIndex++;
    renderBulkItem();
  }

  if (waBulkSendNextBtn) {
    waBulkSendNextBtn.addEventListener("click", function () {
      advanceBulk(true);
    });
  }

  if (waBulkSkipBtn) {
    waBulkSkipBtn.addEventListener("click", function () {
      advanceBulk(false);
    });
  }

  if (waBulkCloseBtn) {
    waBulkCloseBtn.addEventListener("click", function () {
      if (waBulkModalBackdrop) waBulkModalBackdrop.style.display = "none";
    });
  }

  // ──────────────── TIPIFICACIÓN DE CONTACTO ────────────────
  document.querySelectorAll(".typification-card").forEach(function (card) {
    card.addEventListener("click", function () {
      document.querySelectorAll(".typification-card").forEach(function (c) { c.classList.remove("selected"); });
      card.classList.add("selected");
      var radio = card.querySelector("input[type='radio']");
      if (radio) {
        radio.checked = true;
        var isAcuerdo = radio.value === "Acuerdo de pago";
        var nextDateInput = document.querySelector("input[name='next_date']");
        if (isAcuerdo && nextDateInput) {
          nextDateInput.focus();
        }
      }
    });
  });
});

