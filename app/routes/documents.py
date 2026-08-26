from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, Document, Loan, Payment
from ..services.decorators import permission_required
from ..services.documents import allowed, create_document, delete_file, replace_file
from ..services.financial import log_audit

bp = Blueprint("documents", __name__, url_prefix="/documentos")

DOC_TYPES = [
    "identificacion", "contrato", "pagaré", "comprobante", "fotografia",
    "extracto", "otro",
]


def _slug_entity(value):
    value = (value or "").strip().lower()
    aliases = {
        "clientes": "cliente",
        "cliente": "cliente",
        "prestamos": "prestamo",
        "prestamo": "prestamo",
        "prestamos_": "prestamo",
        "pagos": "pago",
        "pago": "pago",
        "otro": "otro",
    }
    return aliases.get(value, "otro")


def _allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


@bp.route("/")
@login_required
@permission_required("documents.view")
def list_documents():
    clients = Client.query.order_by(Client.first_name).all()
    docs = Document.query.order_by(Document.uploaded_at.desc()).all()

    docs_by_client = {c.id: [] for c in clients}
    other_docs = []

    for d in docs:
        if d.entity_type == "cliente" and d.entity_id in docs_by_client:
            docs_by_client[d.entity_id].append(d)
        else:
            other_docs.append(d)

    clients_with_docs = [
        {"client": c, "documents": docs_by_client.get(c.id, [])}
        for c in clients
    ]

    return render_template(
        "documents/list.html",
        clients_with_docs=clients_with_docs,
        other_docs=other_docs,
        total_docs=len(docs),
    )


@bp.route("/subir", methods=["GET", "POST"])
@login_required
@permission_required("documents.upload")
def upload():
    clients = Client.query.order_by(Client.first_name).all()
    loans = Loan.query.order_by(Loan.created_at.desc()).all()
    if request.method == "POST":
        entity_type = request.form.get("entity_type")
        entity_id = request.form.get("entity_id", type=int)
        doc_type = request.form.get("doc_type")
        file = request.files.get("file")

        if not file or not file.filename:
            flash("Debe seleccionar un archivo.", "danger")
            return redirect(url_for("documents.upload"))
        if not _allowed(file.filename):
            flash("Formato de archivo no permitido.", "danger")
            return redirect(url_for("documents.upload"))

        entity_type = _slug_entity(entity_type)
        if entity_type not in ("cliente", "prestamo", "pago", "otro"):
            flash("Tipo de entidad no válido.", "danger")
            return redirect(url_for("documents.upload"))

        document = create_document(
            entity_type, entity_id or 0, doc_type or "otro", file, current_user.id
        )
        db.session.flush()  # asignar document.id para el log
        log_audit(current_user.id, "Cargar documento", "Documento", document.id, file.filename)
        db.session.commit()
        flash("Documento cargado correctamente.", "success")
        return redirect(url_for("documents.list_documents"))

    return render_template(
        "documents/upload.html", clients=clients, loans=loans, doc_types=DOC_TYPES
    )


@bp.route("/<int:document_id>/descargar")
@login_required
@permission_required("documents.view")
def download(document_id):
    document = Document.query.get_or_404(document_id)
    # Leer en memoria y servir desde BytesIO: evita dejar el handle abierto
    # (WinError 32 al reemplazar/eliminar en Windows) y es compatible con
    # stored_name con subcarpetas. Máximo 15 MB por configuración.
    import io
    from flask import send_file
    with open(document.path, "rb") as fh:
        data = fh.read()
    return send_file(
        io.BytesIO(data),
        as_attachment=True,
        download_name=document.original_name,
    )


@bp.route("/<int:document_id>/ocr", methods=["GET", "POST"])
@login_required
@permission_required("documents.view")
def ocr(document_id):
    from ..models import OCRResult
    document = Document.query.get_or_404(document_id)
    result = OCRResult.query.filter_by(document_id=document.id).order_by(OCRResult.created_at.desc()).first()

    if request.method == "POST":
        text = request.form.get("extracted_text", "")
        result = OCRResult(document_id=document.id, extracted_text=text, fields_json="{}")
        db.session.add(result)
        log_audit(current_user.id, "Confirmar OCR", "Documento", document.id, document.original_name)
        db.session.commit()
        flash("Resultado OCR guardado.", "success")
        return redirect(url_for("documents.list_documents"))

    if result is None:
        extracted = _run_ocr(document)
        result = OCRResult(document_id=document.id, extracted_text=extracted, fields_json="{}")
        db.session.add(result)
        db.session.commit()

    return render_template("documents/ocr.html", document=document, result=result)


def _run_ocr(document):
    """Extrae texto del documento (PDF o imagen) con el servicio OCR unificado."""
    from ..services.ocr import extract_text_from_path
    try:
        text = extract_text_from_path(document.path, document.original_name)
        if text and text.strip():
            return text
        ext = (document.extension or "").lower()
        if ext == "pdf":
            return "(El PDF no contiene texto reconocible; probablemente es un escaneo sin OCR. Edite el texto manualmente.)"
        return "(No se reconoció texto en la imagen. Edite el texto manualmente.)"
    except Exception as exc:  # noqa: BLE001
        return f"(OCR no disponible: {exc}). Edite el texto manualmente."


@bp.route("/<int:document_id>/editar", methods=["POST"])
@login_required
@permission_required("documents.upload")
def edit(document_id):
    document = Document.query.get_or_404(document_id)
    document.doc_type = request.form.get("doc_type", document.doc_type)
    document.entity_type = request.form.get("entity_type", document.entity_type)
    document.entity_id = request.form.get("entity_id", type=int) or document.entity_id
    log_audit(current_user.id, "Editar documento", "Documento", document.id, document.original_name)
    db.session.commit()
    flash("Metadatos del documento actualizados.", "success")
    return redirect(request.referrer or url_for("documents.list_documents"))


@bp.route("/<int:document_id>/reemplazar", methods=["POST"])
@login_required
@permission_required("documents.upload")
def replace(document_id):
    document = Document.query.get_or_404(document_id)
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Debe seleccionar un archivo.", "danger")
    elif not allowed(file.filename):
        flash("Formato de archivo no permitido.", "danger")
    else:
        replace_file(document, file)
        # Al reemplazar, invalidar resultados OCR previos
        for r in document.ocr_results:
            db.session.delete(r)
        log_audit(current_user.id, "Reemplazar documento", "Documento", document.id, file.filename)
        db.session.commit()
        flash("Archivo reemplazado.", "success")
    return redirect(request.referrer or url_for("documents.list_documents"))


@bp.route("/<int:document_id>/eliminar", methods=["POST"])
@login_required
@permission_required("documents.upload")
def delete(document_id):
    document = Document.query.get_or_404(document_id)
    delete_file(document.stored_name)
    log_audit(current_user.id, "Eliminar documento", "Documento", document.id, document.original_name)
    db.session.delete(document)
    db.session.commit()
    flash("Documento eliminado.", "success")
    return redirect(request.referrer or url_for("documents.list_documents"))
