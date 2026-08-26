"""Almacenamiento de archivos y gestión de metadatos documentales."""
import os
import re
import uuid
from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import Document


def allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _slug(value, fallback):
    """Normaliza una etiqueta para uso seguro en nombres de archivo."""
    slug = re.sub(r"[^a-z0-9_-]", "-", str(value or "").lower()).strip("-")
    return slug or fallback


def build_stored_name(entity_type, entity_id, doc_type, ext):
    """Genera la nomenclatura interna del archivo con trazabilidad.

    Estructura: {entidad}/{entity_id}/{entidad}-{entity_id}-{tipo}-{fecha}-{uuid8}.{ext}
    Ejemplo: cliente/12/cliente-12-identificacion-20260820-a1b2c3d4.png

    La subcarpeta por entidad ordena físicamente los archivos y el nombre
    permite identificar a qué cliente/entidad y tipo pertenece cada archivo.

    IMPORTANTE: el separador SIEMPRE es "/" (POSIX), nunca os.path.join.
    Werkzeug's safe_join (usado por send_from_directory) divide por "/" y
    devuelve None con "\" en Windows, lo que rompe la descarga.
    """
    ent = _slug(entity_type, "general")
    tipo = _slug(doc_type, "documento")
    fecha = datetime.now().strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:8]
    name = f"{ent}-{entity_id}-{tipo}-{fecha}-{uid}.{ext}"
    return f"{ent}/{entity_id}/{name}"


def save_file(file_storage, entity_type="general", entity_id=0, doc_type="documento"):
    """Guarda el archivo con nomenclatura trazable y devuelve (stored_name, extension, size)."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    stored_name = build_stored_name(entity_type, entity_id, doc_type, ext)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_storage.save(path)
    size = os.path.getsize(path)
    return stored_name, ext, size


def delete_file(stored_name):
    """Elimina el archivo físico. En Windows un archivo recién servido puede
    quedar brevemente bloqueado (WinError 32); se reintenta varias veces."""
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
    if not os.path.exists(path):
        return
    import time
    for attempt in range(5):
        try:
            os.remove(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.15)


def create_document(entity_type, entity_id, doc_type, file_storage, uploaded_by):
    """Crea el registro de documento a partir de un archivo subido."""
    stored_name, ext, size = save_file(
        file_storage, entity_type=entity_type, entity_id=entity_id, doc_type=doc_type
    )
    document = Document(
        entity_type=entity_type,
        entity_id=entity_id,
        doc_type=doc_type,
        original_name=file_storage.filename,
        stored_name=stored_name,
        extension=ext,
        size=size,
        uploaded_by=uploaded_by,
    )
    db.session.add(document)
    return document


def replace_file(document, file_storage):
    """Reemplaza el archivo físico de un documento conservando el registro."""
    delete_file(document.stored_name)
    stored_name, ext, size = save_file(
        file_storage,
        entity_type=document.entity_type,
        entity_id=document.entity_id,
        doc_type=document.doc_type,
    )
    document.stored_name = stored_name
    document.extension = ext
    document.size = size
    document.original_name = file_storage.filename
