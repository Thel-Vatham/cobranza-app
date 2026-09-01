import csv
import io
import zipfile
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, send_file, Response
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (Audit, Client, CollectionManagement, Document,
                       Loan, Obligation, OCRResult, Parameter, Payment,
                       PaymentApplication, Permission, Reference, Role, User)
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
MODULE_METADATA = {
    "dashboard": {"title": "Panel Principal", "icon": "dashboard", "desc": "Visualización del resumen operativo y KPIs de cartera."},
    "clients": {"title": "Clientes y Deudores", "icon": "users", "desc": "Consulta, registro y edición de clientes y referencias."},
    "loans": {"title": "Préstamos y Créditos", "icon": "briefcase", "desc": "Creación, liquidación y modificación de préstamos."},
    "payments": {"title": "Pagos y Recaudos", "icon": "banknote", "desc": "Registro de pagos, emisión de recibos y anulación de abonos."},
    "collections": {"title": "Cobranza en Campo", "icon": "phone", "desc": "Gestión de mora, 1-Tap WhatsApp y compromisos de pago."},
    "documents": {"title": "Expedientes y Documentos", "icon": "folder", "desc": "Carga y visualización de soportes y lectura OCR."},
    "reports": {"title": "Reportes y Analítica", "icon": "chart", "desc": "Consultas de cartera, comportamiento y score de riesgo."},
    "admin": {"title": "Administración del Sistema", "icon": "shield", "desc": "Gestión de usuarios, parámetros y auditoría."},
}

PERMISSION_DESCRIPTIONS = {
    "dashboard.view": "Acceder al panel de inicio y ver los indicadores de cartera.",
    "clients.view": "Consultar la lista de clientes y sus expedientes.",
    "clients.create": "Registrar nuevos clientes y codeudores.",
    "clients.edit": "Modificar datos personales y de contacto de clientes.",
    "loans.view": "Ver la lista de préstamos y los planes de amortización.",
    "loans.create": "Crear y desembolsar nuevos préstamos.",
    "loans.edit": "Modificar condiciones y datos de préstamos.",
    "payments.view": "Consultar el historial de pagos y recibos.",
    "payments.create": "Registrar y aplicar pagos a obligaciones.",
    "payments.revert": "Anular y revertir pagos aplicados.",
    "collections.view": "Consultar obligaciones en mora y listas de cobro.",
    "collections.create": "Registrar gestiones de cobro y promesas de pago.",
    "documents.view": "Ver y descargar documentos adjuntos.",
    "documents.upload": "Subir nuevos documentos y comprobantes.",
    "reports.view": "Consultar reportes de cartera y matriz de score.",
    "admin.users": "Crear, activar y editar usuarios del sistema.",
    "admin.roles": "Configurar roles y asignar permisos.",
    "admin.parameters": "Modificar los parámetros del sistema y score.",
    "admin.audit": "Consultar el registro de auditoría de actividades.",
}


@bp.route("/roles")
@login_required
@permission_required("admin.roles")
def roles():
    roles_list = Role.query.all()
    all_perms = Permission.query.all()

    # Agrupar permisos ordenadamente por módulo
    grouped_perms = {}
    for p in all_perms:
        mod_key = p.code.split(".")[0] if "." in p.code else "general"
        grouped_perms.setdefault(mod_key, []).append(p)

    return render_template(
        "admin/roles.html",
        roles=roles_list,
        grouped_perms=grouped_perms,
        modules=MODULE_METADATA,
        perm_desc=PERMISSION_DESCRIPTIONS,
    )


@bp.route("/roles/<int:role_id>", methods=["POST"])
@login_required
@permission_required("admin.roles")
def role_update(role_id):
    role = Role.query.get_or_404(role_id)
    selected = request.form.getlist("permissions", type=int)
    role.permissions = Permission.query.filter(Permission.id.in_(selected)).all() if selected else []
    log_audit(current_user.id, "Editar rol", "Rol", role.id, role.name)
    db.session.commit()
    flash(f"Permisos del rol '{role.name}' actualizados exitosamente.", "success")
    return redirect(url_for("admin.roles"))


# ---------- Parámetros ----------
from ..seed import seed_parameters

PARAM_CATEGORIES = {
    "financieros": {
        "label": "Crédito y Políticas de Pago",
        "icon": "banknote",
        "desc": "Tasa de interés por cuota y orden contable de imputación de pagos.",
    },
    "scoring": {
        "label": "Score y Matriz de Riesgo",
        "icon": "gauge",
        "desc": "Calibración del puntaje crediticio de 0 a 100 y umbrales de riesgo.",
    },
    "cobranza": {
        "label": "Cobranza y Alertas Operativas",
        "icon": "phone",
        "desc": "Tiempos de alerta y horizontes de seguimiento para cobranza.",
    },
    "generales": {
        "label": "Datos de la Empresa",
        "icon": "settings",
        "desc": "Configuración comercial y símbolo monetario de la plataforma.",
    },
}

PARAM_METADATA = {
    "tasa_interes_periodo": {
        "title": "Tasa de Interés Fija por Cuota",
        "unit": "% por cuota",
        "explanation": "Porcentaje de interés fijo aplicado a cada cuota (quincenal o mensual) sobre el saldo deudor.",
        "type": "number",
        "step": "0.1",
        "badge": "Centralizado en préstamos",
    },
    "orden_aplicacion_pago": {
        "title": "Prioridad de Imputación de Pagos",
        "unit": "",
        "explanation": "Define si los abonos del cliente liquidan primero los intereses pendientes o reducen directamente el capital.",
        "type": "select",
        "options": [
            ("interes_primero", "Intereses primero (Recomendado bancario) — Asegura rentabilidad cobrando intereses antes del capital."),
            ("capital_primero", "Capital primero — Reduce el saldo principal adeudado antes de cubrir intereses."),
        ],
    },
    "tasa_mora_diaria": {
        "title": "Interés Moratorio Diario (Referencia)",
        "unit": "% diario",
        "explanation": "Tasa de interés moratorio diario de referencia por cada día de atraso tras la fecha de vencimiento.",
        "type": "number",
        "step": "0.01",
    },
    "peso_puntualidad": {
        "title": "Peso de la Puntualidad en el Score",
        "unit": "% ponderación",
        "explanation": "Importancia porcentual de pagar en o antes de la fecha límite dentro del Score de 0 a 100.",
        "type": "number",
        "step": "1",
    },
    "peso_cumplimiento": {
        "title": "Peso del Cumplimiento de Cuotas",
        "unit": "% ponderación",
        "explanation": "Importancia porcentual de la cantidad de cuotas efectivamente pagadas sobre el total contratado.",
        "type": "number",
        "step": "1",
    },
    "peso_mora": {
        "title": "Penalización por Mora Activa",
        "unit": "% ponderación",
        "explanation": "Impacto negativo en el score cuando el cliente tiene cuotas actualmente vencidas e impagas.",
        "type": "number",
        "step": "1",
    },
    "dias_max_mora_score": {
        "title": "Días de Mora para Penalización Máxima",
        "unit": "días",
        "explanation": "Días de atraso a partir de los cuales el componente de mora del deudor cae al castigo máximo (0 pts).",
        "type": "number",
        "step": "1",
    },
    "umbral_score_excelente": {
        "title": "Puntaje Mínimo — Riesgo Bajo (Excelente)",
        "unit": "puntos",
        "explanation": "Puntaje requerido (0-100) para clasificar al deudor como Excelente / Apto para crédito inmediato.",
        "type": "number",
        "step": "1",
    },
    "umbral_score_bueno": {
        "title": "Puntaje Mínimo — Riesgo Medio (Bueno)",
        "unit": "puntos",
        "explanation": "Puntaje mínimo para clasificar al deudor con historial Bueno y riesgo controlado.",
        "type": "number",
        "step": "1",
    },
    "umbral_score_regular": {
        "title": "Puntaje Mínimo — Regular",
        "unit": "puntos",
        "explanation": "Puntaje mínimo para clasificación Regular. Por debajo de este valor, el deudor se clasifica como 'Riesgo Alto'.",
        "type": "number",
        "step": "1",
    },
    "dias_proximos_vencer": {
        "title": "Horizonte de Alerta de Vencimientos",
        "unit": "días",
        "explanation": "Días futuros que el sistema monitorea en el Panel Principal para alertar cuotas a vencer.",
        "type": "number",
        "step": "1",
    },
    "dias_alerta_mora": {
        "title": "Umbral de Alerta de Mora Temprana",
        "unit": "días",
        "explanation": "Días de retraso para destacar y priorizar una cuota en la lista de cobranza y gestiones en campo.",
        "type": "number",
        "step": "1",
    },
    "nombre_empresa": {
        "title": "Nombre Comercial de la Empresa",
        "unit": "",
        "explanation": "Nombre que se visualiza en encabezados, reportes y mensajes de WhatsApp.",
        "type": "text",
    },
    "moneda_simbolo": {
        "title": "Símbolo de Moneda",
        "unit": "",
        "explanation": "Símbolo visual utilizado para cifras monetarias en la aplicación (Ej: $, COP, USD).",
        "type": "text",
    },
}


@bp.route("/parametros", methods=["GET", "POST"])
@login_required
@permission_required("admin.parameters")
def parameters():
    # Garantizar que todos los parámetros estén sembrados
    seed_parameters()

    if request.method == "POST":
        # Actualizar valores existentes
        for param in Parameter.query.all():
            new_value = request.form.get(f"param_{param.id}")
            if new_value is not None and new_value != param.value:
                param.value = new_value.strip()
        log_audit(current_user.id, "Editar parámetros", "Parámetro")
        db.session.commit()
        flash("Parámetros del sistema actualizados exitosamente.", "success")
        return redirect(url_for("admin.parameters"))

    params = Parameter.query.all()
    # Excluir claves obsoletas de depuración si existieran
    hidden_keys = {"metodo_interes", "periodicidad_interes"}
    visible_params = [p for p in params if p.key not in hidden_keys]

    return render_template(
        "admin/parameters.html",
        params=visible_params,
        categories=PARAM_CATEGORIES,
        meta=PARAM_METADATA,
    )


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
        # Orden respetando FK: aplicaciones → pagos → obligaciones → gestiones → OCR → documentos → referencias → préstamos → clientes
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        CollectionManagement.query.delete()
        OCRResult.query.delete()
        Document.query.delete()
        Reference.query.delete()
        Loan.query.delete()
        Client.query.delete()
        log_audit(current_user.id, "Borrar todos los datos operativos", "Sistema")
        db.session.commit()
        flash("Base de datos limpia. Todos los clientes, préstamos y pagos fueron eliminados exitosamente.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error al borrar datos: {exc}", "danger")

    return redirect(url_for("admin.data_management"))


@bp.route("/cargar-demo", methods=["POST"])
@login_required
@permission_required("admin.audit")
def load_demo():
    """Carga voluntariamente el conjunto de prueba con 10 clientes y 3M COP."""
    try:
        from ..seed import _seed_demo_data
        _seed_demo_data(force=True)
        log_audit(current_user.id, "Cargar cartera demo de prueba", "Sistema")
        db.session.commit()
        flash("Cartera demo cargada exitosamente (10 clientes y $3,000,000 en créditos).", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error al cargar cartera demo: {exc}", "danger")

    return redirect(url_for("admin.data_management"))
