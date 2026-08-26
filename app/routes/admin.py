import csv
import io
import zipfile
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, send_file, Response
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (Audit, Client, CollectionManagement, Document,
                       Loan, Obligation, Parameter, Payment,
                       PaymentApplication, Permission, Role, User)
from ..services.decorators import permission_required
from ..services.financial import log_audit

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------- Usuarios ----------
@bp.route("/usuarios")
@login_required
@permission_required("admin.users")
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    roles = Role.query.all()
    return render_template("admin/users.html", users=users, roles=roles)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("admin.users")
def user_create():
    roles = Role.query.all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if User.query.filter_by(username=username).first():
            flash("El nombre de usuario ya existe.", "danger")
            return render_template("admin/user_form.html", roles=roles, user=None)
        user = User(
            username=username,
            email=request.form.get("email", "").strip(),
            full_name=request.form.get("full_name", "").strip(),
            role_id=request.form.get("role_id", type=int),
            active=request.form.get("active") == "on",
        )
        user.set_password(password)
        db.session.add(user)
        log_audit(current_user.id, "Crear usuario", "Usuario", user.id, username)
        db.session.commit()
        flash(f"Usuario {username} creado.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", roles=roles, user=None)


@bp.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@login_required
@permission_required("admin.users")
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()
    if request.method == "POST":
        user.username = request.form.get("username", "").strip()
        user.email = request.form.get("email", "").strip()
        user.full_name = request.form.get("full_name", "").strip()
        user.role_id = request.form.get("role_id", type=int)
        user.active = request.form.get("active") == "on"
        if request.form.get("password"):
            user.set_password(request.form.get("password"))
        log_audit(current_user.id, "Editar usuario", "Usuario", user.id, user.username)
        db.session.commit()
        flash("Usuario actualizado.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", roles=roles, user=user)


# ---------- Roles y permisos ----------
@bp.route("/roles")
@login_required
@permission_required("admin.roles")
def roles():
    roles = Role.query.all()
    permissions = Permission.query.order_by(Permission.name).all()
    return render_template("admin/roles.html", roles=roles, permissions=permissions)


@bp.route("/roles/<int:role_id>", methods=["POST"])
@login_required
@permission_required("admin.roles")
def role_update(role_id):
    role = Role.query.get_or_404(role_id)
    selected = request.form.getlist("permissions", type=int)
    role.permissions = Permission.query.filter(Permission.id.in_(selected)).all() if selected else []
    log_audit(current_user.id, "Editar rol", "Rol", role.id, role.name)
    db.session.commit()
    flash(f"Permisos del rol '{role.name}' actualizados.", "success")
    return redirect(url_for("admin.roles"))


# ---------- Parámetros ----------
PARAM_CATEGORIES = {
    "financieros": "Financieros",
    "cobranza": "Cobranza",
    "scoring": "Score de comportamiento",
    "generales": "Generales",
}


@bp.route("/parametros", methods=["GET", "POST"])
@login_required
@permission_required("admin.parameters")
def parameters():
    if request.method == "POST":
        # Actualizar valores existentes
        for param in Parameter.query.all():
            new_value = request.form.get(f"param_{param.id}")
            if new_value is not None and new_value != param.value:
                param.value = new_value
        log_audit(current_user.id, "Editar parámetros", "Parámetro")
        db.session.commit()
        flash("Parámetros actualizados.", "success")
        return redirect(url_for("admin.parameters"))
    params = Parameter.query.order_by(Parameter.category, Parameter.key).all()
    return render_template("admin/parameters.html", params=params, categories=PARAM_CATEGORIES)


@bp.route("/parametros/nuevo", methods=["POST"])
@login_required
@permission_required("admin.parameters")
def parameter_create():
    key = request.form.get("key", "").strip()
    value = request.form.get("value", "").strip()
    category = request.form.get("category", "generales")
    kind = request.form.get("kind", "text")
    description = request.form.get("description", "").strip()

    if not key:
        flash("La clave del parámetro es obligatoria.", "danger")
    elif Parameter.query.filter_by(key=key).first():
        flash("Ya existe un parámetro con esa clave.", "danger")
    else:
        db.session.add(Parameter(key=key, value=value, category=category, kind=kind, description=description))
        log_audit(current_user.id, "Crear parámetro", "Parámetro", key)
        db.session.commit()
        flash("Parámetro creado.", "success")
    return redirect(url_for("admin.parameters"))


# ---------- Auditoría ----------
@bp.route("/auditoria")
@login_required
@permission_required("admin.audit")
def audit():
    records = Audit.query.order_by(Audit.created_at.desc()).limit(300).all()
    return render_template("admin/audit.html", records=records)


# ---------- Gestión de datos (exportar / borrar) ----------
@bp.route("/datos")
@login_required
@permission_required("admin.audit")
def data_management():
    stats = {
        "clients":  Client.query.count(),
        "loans":    Loan.query.count(),
        "payments": Payment.query.count(),
    }
    return render_template("admin/data.html", stats=stats)


@bp.route("/exportar-csv")
@login_required
@permission_required("admin.audit")
def export_csv():
    """Genera un ZIP con CSVs de las tablas principales."""

    def write_csv(rows, fields):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(fields)
        for row in rows:
            w.writerow([getattr(row, f, "") for f in fields])
        return buf.getvalue().encode("utf-8-sig")  # BOM para Excel

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Clientes
        clients = Client.query.order_by(Client.id).all()
        zf.writestr("clientes.csv", write_csv(clients, [
            "id", "code", "first_name", "last_name",
            "identification_type", "identification_number",
            "country", "address", "phone", "email", "created_at",
        ]))

        # Préstamos
        loans = Loan.query.order_by(Loan.id).all()
        zf.writestr("prestamos.csv", write_csv(loans, [
            "id", "code", "client_id", "principal", "annual_rate",
            "installments_count", "frequency_days", "amortization_type",
            "start_date", "status", "created_at",
        ]))

        # Pagos
        payments = Payment.query.order_by(Payment.id).all()
        zf.writestr("pagos.csv", write_csv(payments, [
            "id", "code", "client_id", "loan_id", "amount",
            "payment_date", "concept", "receipt_number", "status", "created_at",
        ]))

        # Obligaciones
        obligations = Obligation.query.order_by(Obligation.id).all()
        zf.writestr("obligaciones.csv", write_csv(obligations, [
            "id", "loan_id", "number", "due_date", "scheduled_value",
            "capital", "interest", "pending_capital", "pending_interest",
            "status", "paid_date",
        ]))

    zip_buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    log_audit(current_user.id, "Exportar datos", "Sistema")
    db.session.commit()
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"cartera_export_{ts}.zip",
    )


@bp.route("/borrar-datos", methods=["POST"])
@login_required
@permission_required("admin.audit")
def delete_data():
    """Elimina datos operativos conservando usuarios/roles/parámetros."""
    confirm = request.form.get("confirm", "").strip().upper()
    if confirm not in ("ELIMINAR", "BORRAR"):
        flash("Confirmación incorrecta. Escriba ELIMINAR para continuar.", "danger")
        return redirect(url_for("admin.data_management"))

    try:
        # Orden respetando FK: aplicaciones → pagos → obligaciones → gestiones → documentos → préstamos → clientes
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        CollectionManagement.query.delete()
        Document.query.delete()
        Loan.query.delete()
        Client.query.delete()
        log_audit(current_user.id, "Borrar todos los datos operativos", "Sistema")
        db.session.commit()
        flash("Datos operativos eliminados. La base quedó limpia.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error al borrar datos: {exc}", "danger")

    return redirect(url_for("admin.data_management"))
