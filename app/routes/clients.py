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


def _parse_salary(val):
    if not val:
        return None
    clean = str(val).replace("$", "").replace(" ", "").strip()
    if "." in clean and "," not in clean:
        parts = clean.split(".")
        if len(parts[-1]) == 3:  # Ej: 1.800.000
            clean = clean.replace(".", "")
    elif "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        from decimal import Decimal
        return Decimal(clean)
    except Exception:
        return None


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("clients.create")
def create():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        identification_number = request.form.get("identification_number", "").strip()

        client = Client(
            code=_generate_code(),
            first_name=first_name,
            last_name=last_name,
            identification_type=request.form.get("identification_type", "CC"),
            identification_number=identification_number,
            country=request.form.get("country", "Colombia"),
            city=request.form.get("city", "").strip(),
            address=request.form.get("address", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            # Datos bancarios para desembolso
            bank_name=request.form.get("bank_name", "").strip(),
            account_type=request.form.get("account_type", "").strip(),
            account_number=request.form.get("account_number", "").strip(),
            account_holder=request.form.get("account_holder", "").strip(),
            # Datos de empleo
            employer_name=request.form.get("employer_name", "").strip(),
            employer_address=request.form.get("employer_address", "").strip(),
            employer_phone=request.form.get("employer_phone", "").strip(),
            job_title=request.form.get("job_title", "").strip(),
            salary=_parse_salary(request.form.get("salary")),
            # Datos bancarios para recaudo
            collection_bank_name=request.form.get("collection_bank_name", "").strip(),
            collection_account_type=request.form.get("collection_account_type", "").strip(),
            collection_account_number=request.form.get("collection_account_number", "").strip(),
            collection_account_holder=request.form.get("collection_account_holder", "").strip(),
        )

        if not client.first_name or not client.identification_number:
            flash("Nombre e identificación son obligatorios.", "danger")
            return render_template("clients/form.html", client=client)

        ref_names = [n.strip() for n in request.form.getlist("ref_name") if n.strip()]
        if len(ref_names) != 2:
            flash("Debe ingresar exactamente dos (2) referencias o codeudores (mínimo y máximo 2).", "danger")
            return render_template("clients/form.html", client=client)

        db.session.add(client)
        db.session.flush()
        _save_references(client)
        _save_client_documents(client)
        log_audit(current_user.id, "Crear cliente", "Cliente", client.id, client.full_name)
        db.session.commit()
        flash(f"Cliente {client.full_name} creado con éxito.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", client=None)


def _save_client_documents(client):
    """Asocia las 4 fotos clave del expediente (deudor, trabajo, fachada, cédula) al cliente."""
    uploads = [
        ("debtor_photo", "foto_deudor"),
        ("work_photo", "foto_trabajo"),
        ("facade_photo", "fachada"),
        ("address_photo", "fachada"),  # alias de compatibilidad
        ("id_document", "identificacion"),
    ]
    for field_name, doc_type in uploads:
        file = request.files.get(field_name)
        if file and file.filename and allowed(file.filename):
            create_document("cliente", client.id, doc_type, file, current_user.id)


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
            relationship=relationships[i] if i < len(relationships) else "Referencia",
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
    all_docs = Document.query.filter_by(entity_type="cliente", entity_id=client.id).order_by(Document.uploaded_at.desc()).all()

    # Clasificación específica para la Hoja de Vida
    debtor_photo = next((d for d in all_docs if d.doc_type in ("foto_deudor", "perfil")), None)
    work_photo = next((d for d in all_docs if d.doc_type in ("foto_trabajo", "trabajo")), None)
    facade_photo = next((d for d in all_docs if d.doc_type in ("fachada", "domicilio")), None)
    id_doc = next((d for d in all_docs if d.doc_type in ("identificacion", "cedula")), None)

    key_doc_ids = {d.id for d in [debtor_photo, work_photo, facade_photo, id_doc] if d}
    other_docs = [d for d in all_docs if d.id not in key_doc_ids]

    total_principal = sum(float(l.principal) for l in client.loans)
    total_balance = sum(float(l.outstanding_balance) for l in client.loans)
    total_paid = max(0.0, total_principal - total_balance)
    return render_template(
        "clients/detail.html",
        client=client,
        score=score,
        documents=all_docs,
        debtor_photo=debtor_photo,
        work_photo=work_photo,
        facade_photo=facade_photo,
        id_doc=id_doc,
        other_docs=other_docs,
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
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        identification_number = request.form.get("identification_number", "").strip()

        if not first_name or not identification_number:
            flash("Nombre e identificación son obligatorios.", "danger")
            return render_template("clients/form.html", client=client)

        ref_names = [n.strip() for n in request.form.getlist("ref_name") if n.strip()]
        if len(ref_names) != 2:
            flash("Debe ingresar exactamente dos (2) referencias o codeudores (mínimo y máximo 2).", "danger")
            return render_template("clients/form.html", client=client)

        client.first_name = first_name
        client.last_name = last_name
        client.identification_type = request.form.get("identification_type", "CC")
        client.identification_number = identification_number
        client.country = request.form.get("country", "Colombia")
        client.city = request.form.get("city", "").strip()
        client.address = request.form.get("address", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.email = request.form.get("email", "").strip()

        # Desembolso
        client.bank_name = request.form.get("bank_name", "").strip()
        client.account_type = request.form.get("account_type", "").strip()
        client.account_number = request.form.get("account_number", "").strip()
        client.account_holder = request.form.get("account_holder", "").strip()

        # Empleo
        client.employer_name = request.form.get("employer_name", "").strip()
        client.employer_address = request.form.get("employer_address", "").strip()
        client.employer_phone = request.form.get("employer_phone", "").strip()
        client.job_title = request.form.get("job_title", "").strip()
        client.salary = _parse_salary(request.form.get("salary"))

        # Recaudo
        client.collection_bank_name = request.form.get("collection_bank_name", "").strip()
        client.collection_account_type = request.form.get("collection_account_type", "").strip()
        client.collection_account_number = request.form.get("collection_account_number", "").strip()
        client.collection_account_holder = request.form.get("collection_account_holder", "").strip()

        client.references.clear()
        _save_references(client)
        _save_client_documents(client)
        log_audit(current_user.id, "Editar cliente", "Cliente", client.id, client.full_name)
        db.session.commit()
        flash("Cliente actualizado con éxito.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("clients/form.html", client=client)
