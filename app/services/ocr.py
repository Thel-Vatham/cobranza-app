"""Extracción de texto y campos para autocompletado de documentos.

Estrategia:
- PDF: texto incrustado mediante PyMuPDF (fitz); si el PDF es escaneado,
  se renderiza la página a imagen y se aplica OCR.
- Imagen: OCR vía EasyOCR (Deep Learning); en caso contrario texto vacío.

Los campos se infieren con expresiones regulares heurísticas sobre el texto.
"""
import os
import re

from flask import current_app

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:  # noqa: BLE001
    HAS_FITZ = False

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False

# Dimensiones objetivo del lado mayor de la imagen antes del OCR.
# - Si es mucho más grande: se reduce para evitar agotar la memoria (OOM)
#   y acelerar EasyOCR notablemente en CPU.
# - Si es muy pequeña (texto diminuto): se amplía para que EasyOCR lea mejor.
_MIN_OCR_DIMENSION = 1200
_MAX_OCR_DIMENSION = 1600

_reader = None


def _log(level, msg, exc=None):
    try:
        logger = current_app.logger
    except Exception:  # noqa: BLE001
        return
    getattr(logger, level, logger.info)(msg, exc_info=exc)


def _get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
            # gpu=False puede ser necesario si no hay CUDA, pero easyocr lo detecta automáticamente.
            _reader = easyocr.Reader(['es'])
        except Exception as exc:  # noqa: BLE001
            _log("warning", f"EasyOCR no disponible: {exc}", exc)
    return _reader


def _prepare_image(data):
    """Normaliza bytes de imagen para mejorar el OCR:
    decodifica, respeta la rotación EXIF, redimensiona al rango objetivo
    y realza el contraste (crítico en fotos de cédulas con filigrana de fondo).
    Devuelve bytes PNG o None si no se puede leer."""
    if not HAS_PIL:
        return data
    try:
        import io
        src = io.BytesIO(data) if isinstance(data, bytes) else data
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)  # respeta rotación de fotos de celular
        img = img.convert("RGB")
        w, h = img.size
        largest = max(w, h)
        if largest > _MAX_OCR_DIMENSION:
            scale = _MAX_OCR_DIMENSION / largest
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        elif largest < _MIN_OCR_DIMENSION:
            scale = _MIN_OCR_DIMENSION / largest
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        # Realza el contraste: texto oscuro sobre fondo con filigrana se vuelve legible
        img = ImageOps.autocontrast(img, cutoff=1)
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        _log("warning", f"No se pudo decodificar la imagen: {exc}")
        return None


def extract_text(file_storage, filename=""):
    """Extrae texto de un archivo subido (PDF o imagen)."""
    ext = (filename or file_storage.filename or "").rsplit(".", 1)[-1].lower()
    data = file_storage.read()

    if ext == "pdf":
        return _pdf_text(data)

    if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"):
        return _image_text(data)

    return ""


def extract_text_from_path(path, filename=""):
    """Extrae texto desde una ruta de archivo en disco (PDF o imagen)."""
    ext = (filename or os.path.basename(path)).rsplit(".", 1)[-1].lower()
    with open(path, "rb") as fh:
        data = fh.read()

    if ext == "pdf":
        return _pdf_text(data)

    if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"):
        return _image_text(data)

    return ""


def _pdf_text(data):
    if not HAS_FITZ:
        _log("warning", "PyMuPDF (fitz) no está instalado; no se extraerá texto de PDFs")
        return ""
    text_parts = []
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text().strip()
                # Si el PDF es un documento escaneado (sin capa de texto real), get_text() devolverá muy poco o nada.
                # En ese caso, renderizamos la página a imagen y le aplicamos EasyOCR.
                if len(page_text) < 50:
                    pix = page.get_pixmap(dpi=150) # Render a imagen (150 dpi suele ser suficiente para OCR)
                    img_bytes = pix.tobytes("png")
                    reader = _get_reader()
                    if reader:
                        try:
                            result = reader.readtext(_prepare_image(img_bytes) or img_bytes, detail=0)
                            page_text = "\n".join(result)
                        except BaseException:  # noqa: BLE001 - MemoryError incluido
                            _log("error", "EasyOCR falló sobre página PDF", exc_info=True)
                text_parts.append(page_text)
    except Exception as exc:  # noqa: BLE001
        _log("error", f"Error leyendo PDF: {exc}", exc)
    return "\n".join(text_parts)


def _image_text(data):
    try:
        reader = _get_reader()
        if not reader:
            _log("warning", "EasyOCR no está disponible; no se pudo analizar la imagen")
            return ""
        prepared = _prepare_image(data)
        if prepared is None:
            return ""
        import io
        import numpy as np
        from PIL import Image

        # Convertimos la imagen preprocesada (bytes PNG) a numpy array RGB
        image = Image.open(io.BytesIO(prepared)).convert("RGB")
        img_np = np.array(image)

        result = reader.readtext(img_np, detail=0)
        return "\n".join(result)
    except BaseException as e:  # noqa: BLE001 - MemoryError/SystemExit incluidos
        _log("error", f"Error OCR Imagen: {e}", exc_info=True)
        return ""


def extract_client_fields(text):
    """Devuelve un diccionario con campos sugeridos para el formulario de cliente."""
    text = text or ""
    result = {
        "first_name": "",
        "last_name": "",
        "identification_number": "",
        "phone": "",
        "address": "",
        "email": "",
    }

    if not text.strip():
        return result

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Limpiar caracteres raros en la lectura de números.
    # EasyOCR confunde 0 con O/o y 1 con l/I en imágenes reales.
    def norm_digits(s):
        s = s.replace("O", "0").replace("o", "0")
        s = s.replace("l", "1").replace("I", "1")
        return re.sub(r"[^\d]", "", s)

    # Cédula explícita (ej. "NUMERO 1.057.014.054", "NO 1057014054")
    id_index = -1
    for i, line in enumerate(lines):
        line_upper = line.upper()

        if re.search(r"(?i)(N[UÚ]MERO|C[EÉ]DULA|C\.C\.|N[°ºO]?\.?|DOCUMENTO|IDENTIFICACI[OÓ]N)", line_upper) and not result["identification_number"]:
            # Quitar la etiqueta y lo anterior, para que la "O" de "NUMERO" no contamine el número
            after = re.sub(r"(?i).*?(?:N[UÚ]MERO|C[EÉ]DULA|C\.C\.|N[°ºO]?\.?|DOCUMENTO|IDENTIFICACI[OÓ]N)", "", line)
            # El token debe empezar con un dígito real (tolerando O/l/I dentro)
            m = re.search(r"\d[\d.,\sOoIlS]{5,17}", after)
            if m and 6 <= len(norm_digits(m.group(0))) <= 11:
                result["identification_number"] = norm_digits(m.group(0))
                id_index = i
            elif i + 1 < len(lines):
                m2 = re.search(r"\d[\d.,\sOoIlS]{5,17}", lines[i + 1])
                if m2 and 6 <= len(norm_digits(m2.group(0))) <= 11:
                    result["identification_number"] = norm_digits(m2.group(0))
                    id_index = i + 1

        # En la Cédula Nueva Colombiana, los valores están ANTES de las etiquetas
        if "APELLIDO" in line_upper and not result["last_name"]:
            # Quitar la etiqueta de la línea ("APELLIDOS: X" o "APELLIDOS X")
            value = re.sub(r"(?i)^\s*APELLIDOS?\s*(?:[:\-]\s*)?", "", line).strip()
            if value and value != line.strip():
                result["last_name"] = value
            elif i > 0:  # El apellido está en la línea anterior
                # Evitar tomar la etiqueta "NUMERO" o la cédula
                if not re.search(r"\d{6}", lines[i - 1]) and "NUMERO" not in lines[i - 1].upper():
                    result["last_name"] = lines[i - 1]

        if "NOMBRE" in line_upper and not result["first_name"]:
            value = re.sub(r"(?i)^\s*NOMBRES?\s*(?:[:\-]\s*)?", "", line).strip()
            if value and value != line.strip():
                result["first_name"] = value
            elif i > 0:  # El nombre está en la línea anterior
                if not re.search(r"(?i)APELLIDO", lines[i - 1]):
                    result["first_name"] = lines[i - 1]

    # Si no encontró cédula explícita, buscar en la cédula vieja colombiana (una línea que es puro número)
    if not result["identification_number"]:
        for i, line in enumerate(lines):
            # Línea que parece una cédula formateada "14,.572.367" o "1.O57.O14.O54"
            if re.match(r"^[\d.,\sOoIlS]{6,18}$", line):
                clean = norm_digits(line)
                if 6 <= len(clean) <= 11 and not clean.startswith("3"):
                    result["identification_number"] = clean
                    id_index = i
                    break

    # Si encontró la cédula vieja y no tiene nombres (no había etiquetas "APELLIDOS")
    if result["identification_number"] and not result["last_name"] and not result["first_name"]:
        # En la cédula vieja, las siguientes dos líneas son Apellidos y Nombres
        if id_index != -1 and id_index + 2 < len(lines):
            # Asignamos las siguientes líneas asumiendo que son los nombres
            result["last_name"] = lines[id_index + 1]
            result["first_name"] = lines[id_index + 2]

    # 2. Búsqueda con Regex global para lo que falte
    joined = " ".join(lines)

    if not result["email"]:
        result["email"] = _first_match(joined, r"[\w.+-]+@[\w-]+\.[\w.-]+")

    if not result["phone"]:
        # Normalizar O->0, l/I->1 para tolerar errores de OCR en números
        phone_text = joined.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1")
        result["phone"] = _first_match(phone_text, r"(?:\+57\s*)?(?:3\d{2}[\s.-]?\d{3}[\s.-]?\d{4})")

    if not result["identification_number"]:
        # Cualquier token que parezca cédula: 7-11 dígitos (ignorando celulares 3xx)
        for token in re.findall(r"(?<![\d.])(?:[\d][\d.,\sOoIlS]{5,19})", joined):
            clean = norm_digits(token)
            if 7 <= len(clean) <= 11:
                if len(clean) == 10 and clean.startswith("3"):
                    continue
                result["identification_number"] = clean
                break

    if not result["address"]:
        result["address"] = _first_match(joined, r"(?i)(?:direcci[oó]n|dir\.?|address)\s*[:#-]?\s*(.{3,80})")

    # Limpieza final de ruidos de OCR
    for k in ["first_name", "last_name"]:
        if result[k]:
            result[k] = re.sub(r"[^a-zA-ZÁÉÍÓÚÑáéíóúñ\s]", "", result[k]).strip()

    return result


def _first_match(text, pattern):
    m = re.search(pattern, text)
    if not m:
        return ""
    groups = [g for g in m.groups() if g]
    if not groups:
        return m.group(0).strip()
    value = groups[0].strip()
    return re.sub(r"\s{2,}", " ", value)
