/**
 * CARTERA — Smart Camera & File Uploader
 * Proporciona soporte nativo para toma de fotografías mediante cámara en dispositivos móviles y
 * cámaras web en escritorio, así como selección de archivos existentes (screenshots, fotos de galería y PDFs).
 */

(function () {
  'use strict';

  // 1. Detección de dispositivo móvil
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
    ('ontouchstart' in window && window.innerWidth <= 1024);

  // 2. Modal HTML5 de cámara web para desktop / tablets
  let cameraModal = null;
  let activeStream = null;
  let currentTargetInput = null;
  let currentFacingMode = 'environment';

  function createCameraModal() {
    if (cameraModal) return cameraModal;

    const modal = document.createElement('div');
    modal.id = 'webcam-capture-modal';
    modal.style.cssText = `
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(4px);
      z-index: 10000;
      align-items: center;
      justify-content: center;
      padding: 16px;
    `;

    modal.innerHTML = `
      <div style="background: #ffffff; border-radius: 14px; max-width: 560px; width: 100%; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.3); border: 1px solid #e2e8f0;">
        <div style="padding: 14px 18px; background: #0f172a; color: #ffffff; display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            <strong style="font-size: 0.95rem;">Captura Fotográfica</strong>
          </div>
          <button type="button" id="webcam-close-btn" style="background: none; border: none; color: #94a3b8; font-size: 1.4rem; cursor: pointer; line-height: 1; padding: 0 4px;">&times;</button>
        </div>

        <div style="position: relative; background: #000000; display: flex; align-items: center; justify-content: center; min-height: 320px; max-height: 420px; overflow: hidden;">
          <video id="webcam-video" autoplay playsinline muted style="width: 100%; max-height: 400px; object-fit: contain;"></video>
          <canvas id="webcam-canvas" style="display: none;"></canvas>

          <div id="webcam-flash" style="display: none; position: absolute; inset: 0; background: #ffffff; z-index: 2;"></div>

          <div style="position: absolute; top: 12px; right: 12px; display: flex; gap: 8px;">
            <button type="button" id="webcam-switch-btn" title="Alternar cámara frontal/trasera"
                    style="display: none; background: rgba(15,23,42,0.65); border: 1px solid rgba(255,255,255,0.25); color: #ffffff; border-radius: 8px; padding: 6px 10px; font-size: 0.8rem; cursor: pointer; backdrop-filter: blur(4px);">
              🔄 Girar Cámara
            </button>
          </div>
        </div>

        <div style="padding: 16px 20px; background: #f8fafc; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
          <button type="button" id="webcam-cancel-btn" style="padding: 9px 18px; font-size: 0.88rem; font-weight: 600; color: #64748b; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; cursor: pointer;">
            Cancelar
          </button>
          <button type="button" id="webcam-capture-btn" style="padding: 10px 24px; font-size: 0.92rem; font-weight: 700; color: #ffffff; background: #2563eb; border: none; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">
            <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #ffffff;"></span>
            Capturar Foto
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Eventos del modal
    modal.querySelector('#webcam-close-btn').addEventListener('click', stopAndCloseCamera);
    modal.querySelector('#webcam-cancel-btn').addEventListener('click', stopAndCloseCamera);
    modal.querySelector('#webcam-switch-btn').addEventListener('click', function () {
      currentFacingMode = currentFacingMode === 'environment' ? 'user' : 'environment';
      startCamera(currentTargetInput, currentFacingMode);
    });

    modal.querySelector('#webcam-capture-btn').addEventListener('click', capturePhotoFromVideo);

    cameraModal = modal;
    return modal;
  }

  function startCamera(targetInput, facingMode = 'environment') {
    currentTargetInput = targetInput;
    currentFacingMode = facingMode;
    const modal = createCameraModal();
    const video = modal.querySelector('#webcam-video');
    const switchBtn = modal.querySelector('#webcam-switch-btn');

    modal.style.display = 'flex';

    if (activeStream) {
      activeStream.getTracks().forEach(track => track.stop());
    }

    const constraints = {
      video: {
        facingMode: { ideal: facingMode },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      },
      audio: false
    };

    navigator.mediaDevices.getUserMedia(constraints)
      .then(stream => {
        activeStream = stream;
        video.srcObject = stream;

        // Comprobar si hay múltiples cámaras para mostrar botón de switch
        if (navigator.mediaDevices.enumerateDevices) {
          navigator.mediaDevices.enumerateDevices().then(devices => {
            const videoDevices = devices.filter(d => d.kind === 'videoinput');
            if (videoDevices.length > 1) {
              switchBtn.style.display = 'inline-block';
            }
          });
        }
      })
      .catch(err => {
        console.warn('No se pudo acceder a la cámara web:', err);
        stopAndCloseCamera();
        // Fallback: disparar el selector de archivos normal
        if (currentTargetInput) {
          currentTargetInput.click();
        }
      });
  }

  function stopAndCloseCamera() {
    if (activeStream) {
      activeStream.getTracks().forEach(track => track.stop());
      activeStream = null;
    }
    if (cameraModal) {
      cameraModal.style.display = 'none';
      const video = cameraModal.querySelector('#webcam-video');
      if (video) video.srcObject = null;
    }
  }

  function capturePhotoFromVideo() {
    if (!activeStream || !currentTargetInput) return;

    const modal = cameraModal;
    const video = modal.querySelector('#webcam-video');
    const canvas = modal.querySelector('#webcam-canvas');
    const flash = modal.querySelector('#webcam-flash');

    // Efecto de flash
    flash.style.display = 'block';
    setTimeout(() => { flash.style.display = 'none'; }, 120);

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(blob => {
      if (!blob) return;

      const filename = `foto_${Date.now()}.jpg`;
      const file = new File([blob], filename, { type: 'image/jpeg' });

      // Asignar al input destino usando DataTransfer
      assignFileToInput(currentTargetInput, file);
      stopAndCloseCamera();
    }, 'image/jpeg', 0.92);
  }

  /**
   * Asigna un File a un input type="file" y dispara sus eventos de cambio y vista previa
   */
  function assignFileToInput(inputElement, file) {
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      inputElement.files = dt.files;
    } catch (e) {
      console.error('DataTransfer no soportado en este navegador:', e);
    }

    // Disparar evento change para activar OCR y previsualizaciones
    inputElement.dispatchEvent(new Event('change', { bubbles: true }));

    // Actualizar indicador visual si existe
    updateFileIndicator(inputElement, file);
  }

  /**
   * Actualiza el indicador visual de archivo seleccionado / foto tomada
   */
  function updateFileIndicator(inputElement, file) {
    const parentContainer = inputElement.closest('.camera-uploader-group, .upload-tile, label, div');
    if (!parentContainer) return;

    let indicator = parentContainer.querySelector('.camera-file-badge');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'camera-file-badge';
      indicator.style.cssText = `
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.76rem;
        font-weight: 600;
        color: #059669;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        border-radius: 6px;
        padding: 4px 8px;
        margin-top: 6px;
      `;
      parentContainer.appendChild(indicator);
    }

    const isImage = file.type.startsWith('image/');
    const iconSvg = isImage
      ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>`
      : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

    const sizeKb = Math.round(file.size / 1024);
    indicator.innerHTML = `
      ${iconSvg}
      <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px;">${file.name}</span>
      <span style="color: #6ee7b7;">·</span>
      <span style="color: #047857;">${sizeKb} KB</span>
    `;
    indicator.style.display = 'inline-flex';
  }

  /**
   * Configura un botón de "Tomar Foto" enlazado a un input de archivo
   */
  window.triggerCameraCapture = function (targetInputId, preferFacingMode = 'environment') {
    const input = document.getElementById(targetInputId);
    if (!input) return;

    if (isMobile) {
      // En móvil: Usamos un input temporal con capture para invocar la app de la cámara directamente
      let mobileCamInput = document.getElementById(targetInputId + '_mobile_cam');
      if (!mobileCamInput) {
        mobileCamInput = document.createElement('input');
        mobileCamInput.type = 'file';
        mobileCamInput.id = targetInputId + '_mobile_cam';
        mobileCamInput.accept = 'image/*';
        mobileCamInput.capture = preferFacingMode;
        mobileCamInput.style.display = 'none';
        document.body.appendChild(mobileCamInput);

        mobileCamInput.addEventListener('change', function () {
          if (this.files && this.files[0]) {
            assignFileToInput(input, this.files[0]);
          }
        });
      }
      mobileCamInput.click();
    } else {
      // En escritorio: Si hay getUserMedia, abrimos el visor interactivo de webcam
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        startCamera(input, preferFacingMode);
      } else {
        // Fallback: abrir selector de archivo
        input.click();
      }
    }
  };

  /**
   * Dispara la selección de archivo / galería / screenshot
   */
  window.triggerFileGallery = function (targetInputId) {
    const input = document.getElementById(targetInputId);
    if (input) {
      input.click();
    }
  };

  // Inicialización automática para inputs de previsualización existentes
  document.addEventListener('DOMContentLoaded', function () {
    // Escuchar cambios en cualquier input tipo file de la app para actualizar badges
    document.querySelectorAll('input[type="file"]').forEach(input => {
      input.addEventListener('change', function () {
        if (this.files && this.files[0]) {
          updateFileIndicator(this, this.files[0]);
        }
      });
    });
  });

})();
