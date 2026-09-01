from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, Document, Reference
from ..services.decorators import permission_required
from ..services.documents import allowed, create_document
from ..services.financial import log_audit
from ..services.ocr import extract_client_fields, extract_text
from ..services.scoring import compute_score

bp = Blueprint("clients", __name__, url_prefix="/clientes")


def _generate_code():
    count = Client.query.count() + 1
    return f"CL-{count:05d}"


@bp.route("/")
@login_required
@permission_required("clients.view")
def list_clients():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Client.first_name.ilike(like))
            | (Client.last_name.ilike(like))
            | (Client.identification_number.ilike(like))
            | (Client.code.ilike(like))
        )
    clients = query.order_by(Client.created_at.desc()).all()
    return render_template("clients/list.html", clients=clients, q=q)


@bp.route("/ocr", methods=["POST"])
@login_required
@permission_required("clients.create")
def ocr():
    """Autocompletado: recibe un documento y devuelve campos sugeridos en JSON."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "message": "No se recibió archivo."}), 400
    if not allowed(file.filename):
        return jsonify({"ok": False, "message": "Formato no permitido."}), 400
    try:
        text = extract_text(file, file.filename)
        fields = extract_client_fields(text)
        current_app.logger.info(
            "OCR (%s): texto=%r campos=%r", file.filename, text[:300], fields
        )
        return jsonify({"ok": True, "fields": fields, "text": text})
    except Exception as exc:  # noqa: BLE001 - nunca dejar escapar un 500 HTML
        current_app.logger.error(f"OCR falló: {exc}", exc_info=True)
        return jsonify({"ok": False, "message": "No se pudo analizar el documento. Inténtelo con un archivo más pequeño o en otro formato."}), 500


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("clients.create")
def create():
    if request.method == "POST":
        client = Client(
            code=_generate_code(),
            first_name=request.form.get("first_name", "").strip(),
            last_name=request.form.get("last_name", "").strip(),
            identification_type=request.form.get("identification_type", "CC"),
            identification_number=request.form.get("identification_number", "").strip(),
            country=request.form.get("country", "Colombia"),
            city=request.form.get("city", "").strip(),
            address=request.form.get("address", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            bank_name=request.form.get("bank_name", "").strip(),
            account_type=request.form.get("account_type", "").strip(),
            account_number=request.form.get("account_number", "").strip(),
            account_holder=request.form.get("account_holder", "").strip(),
        )
        if not client.first_name or not client.identification_number:
            flash("Nombre e identificación son obligatorios.", "danger")
            return render_template("clients/form.html", client=client)
        db.session.add(client)
        db.session.flush()
        _save_references(client)
        _save_client_documents(client)
        log_audit(current_user.id, "Crear cliente", "Cliente", client.id, client.full_name)
        db.session.commit()
        flash(f"Cliente {client.full_name} creado.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", client=None)


def _save_client_documents(client):
    """Asocia documentos de identidad y fachada subidos al cliente."""
    id_file = request.files.get("id_document")
    if id_file and id_file.filename and allowed(id_file.filename):
        create_document("cliente", client.id, "identificacion", id_file, current_user.id)

    address_file = request.files.get("address_photo")
    if address_file and address_file.filename and allowed(address_file.filename):
        create_document("cliente", client.id, "fachada", address_file, current_user.id)


@bp.route("/<int:client_id>/documentos", methods=["POST"])
@login_required
@permission_required("clients.edit")
def add_document(client_id):
    client = Client.query.get_or_404(client_id)
    doc_type = request.form.get("doc_type", "otro")
    file = request.files.get("file")

    if not file or not file.filename:
        flash("Debe seleccionar un archivo.", "danger")
    elif not allowed(file.filename):
        flash("Formato de archivo no permitido.", "danger")
    else:
        create_document("cliente", client.id, doc_type, file, current_user.id)
        log_audit(current_user.id, "Cargar documento de cliente", "Documento", None, f"Cliente {client.full_name}: {file.filename}")
        db.session.commit()
        flash("Documento asociado al cliente.", "success")

    return redirect(url_for("clients.detail", client_id=client.id))


def _save_references(client):
    names = request.form.getlist("ref_name")
    relationships = request.form.getlist("ref_relationship")
    identifications = request.form.getlist("ref_identification")
    phones = request.form.getlist("ref_phone")
    addresses = request.form.getlist("ref_address")
    for i, name in enumerate(names):
        name = name.strip()
        if not name:
            continue
        client.references.append(Reference(
            full_name=name,
            relationship=relationships[i] if i < len(relationships) else "",
            identification_number=identifications[i] if i < len(identifications) else "",
            phone=phones[i] if i < len(phones) else "",
            address=addresses[i] if i < len(addresses) else "",
        ))


@bp.route("/<int:client_id>")
@login_required
@permission_required("clients.view")
def detail(client_id):
    client = Client.query.get_or_404(client_id)
    score = compute_score(client)
    documents = Document.query.filter_by(entity_type="cliente", entity_id=client.id).order_by(Document.uploaded_at.desc()).all()
    total_principal = sum(float(l.principal) for l in client.loans)
    total_balance = sum(float(l.outstanding_balance) for l in client.loans)
    total_paid = max(0.0, total_principal - total_balance)
    return render_template(
        "clients/detail.html",
        client=client,
        score=score,
        documents=documents,
        total_principal=total_principal,
        total_balance=total_balance,
        total_paid=total_paid,
    )


@bp.route("/<int:client_id>/editar", methods=["GET", "POST"])
@login_required
@permission_required("clients.edit")
def edit(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == "POST":
        client.first_name = request.form.get("first_name", "").strip()
        client.last_name = request.form.get("last_name", "").strip()
        client.identification_type = request.form.get("identification_type", "CC")
        client.identification_number = request.form.get("identification_number", "").strip()
        client.country = request.form.get("country", "Colombia")
        client.city = request.form.get("city", "").strip()
        client.address = request.form.get("address", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.email = request.form.get("email", "").strip()
        client.bank_name = request.form.get("bank_name", "").strip()
        client.account_type = request.form.get("account_type", "").strip()
        client.account_number = request.form.get("account_number", "").strip()
        client.account_holder = request.form.get("account_holder", "").strip()
        client.references.clear()
        _save_references(client)
        _save_client_documents(client)
        log_audit(current_user.id, "Editar cliente", "Cliente", client.id, client.full_name)
        db.session.commit()
        flash("Cliente actualizado.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", client=client)
