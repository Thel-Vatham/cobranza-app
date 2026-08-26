// (Archivo heredado — la lógica activa de la interfaz vive en main.js)

document.addEventListener("DOMContentLoaded", function () {
  // Auto-cierre de mensajes flash
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach(function (f) {
    setTimeout(function () {
      f.style.transition = "opacity 0.4s";
      f.style.opacity = "0";
      setTimeout(function () { f.remove(); }, 400);
    }, 5000);
  });
});
