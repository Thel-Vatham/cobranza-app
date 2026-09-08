from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, Document, Loan, Parameter
from ..services.decorators import permission_required
from ..services.documents import allowed, create_document, replace_file
from ..services.financial import generate_obligations, log_audit

bp = Blueprint("loans", __name__, url_prefix="/prestamos")


def _generate_code():
    count = Loan.query.count() + 1
    return f"PR-{count:05d}"


@bp.route("/")
@login_required
@permission_required("loans.view")
def list_loans():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    freq = request.args.get("freq", "").strip()
    cycle = request.args.get("cycle", "").strip()
    amount = request.args.get("amount", type=float)

    is_admin = bool(current_user.role and current_user.role.name == "Administrador")
    active_portfolio_id = session.get("active_portfolio_id")

    query = Loan.query
    if not is_admin:
        if active_portfolio_id:
            query = query.filter_by(portfolio_id=active_portfolio_id)
        else:
            query = query.filter(Loan.id == -1)
    else:
        if active_portfolio_id:
            query = query.filter_by(portfolio_id=active_portfolio_id)
    if q:
        like = f"%{q}%"
        query = query.join(Client).filter(
            (Loan.code.ilike(like))
            | (Client.first_name.ilike(like))
            | (Client.last_name.ilike(like))
            | (Client.identification_number.ilike(like))
        )
    if status:
        query = query.filter(Loan.status == status)
    if freq:
        query = query.filter(Loan.frequency_type == freq)
    if cycle:
        query = query.filter(Loan.biweekly_cycle == cycle)
    if amount is not None:
        query = query.filter(Loan.principal == amount)

    loans = query.order_by(Loan.created_at.desc()).all()

    # Montos configurados en parámetros para botones de filtro
    montos_raw = Parameter.get("montos_prestamo_disponibles", "75, 100, 125, 150")
    montos_disponibles = [m.strip() for m in montos_raw.split(",") if m.strip()]

    return render_template(
        "loans/list.html",
        loans=loans,
        q=q,
        status=status,
        freq=freq,
        cycle=cycle,
        amount=amount,
        montos_disponibles=montos_disponibles,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("loans.create")
def create():
    # Tasa de interés por período (fija 20% default) y montos predefinidos
    tasa_actual = Parameter.get_float("tasa_interes_periodo", 20.0)
    montos_raw = Parameter.get("montos_prestamo_disponibles", "75, 100, 125, 150")
    montos_disponibles = [m.strip() for m in montos_raw.split(",") if m.strip()]

    is_admin = bool(current_user.role and current_user.role.name == "Administrador")
    active_portfolio_id = session.get("active_portfolio_id")

    if not is_admin:
        if active_portfolio_id:
            clients = Client.query.filter_by(portfolio_id=active_portfolio_id).order_by(Client.first_name).all()
        else:
            clients = []
    else:
        if active_portfolio_id:
            clients = Client.query.filter_by(portfolio_id=active_portfolio_id).order_by(Client.first_name).all()
        else:
            clients = Client.query.order_by(Client.first_name).all()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        principal = request.form.get("principal", type=float)
        annual_rate = Parameter.get_float("tasa_interes_periodo", 20.0)
        installments_count = request.form.get("installments_count", type=int) or 1
        frequency_type = request.form.get("frequency_type") or "quincenal"
        biweekly_cycle = request.form.get("biweekly_cycle") if frequency_type == "quincenal" else None
        frequency_days = 7 if frequency_type == "semanal" else 15
        amortization_type = request.form.get("amortization_type") or "frances"
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()

        client_obj = Client.query.get(client_id)
        loan_portfolio_id = client_obj.portfolio_id if client_obj else active_portfolio_id

        loan = Loan(
            code=_generate_code(),
            portfolio_id=loan_portfolio_id,
            client_id=client_id,
            principal=principal,
            annual_rate=annual_rate / 100.0,  # Convertir % a decimal
            installments_count=installments_count,
            frequency_days=frequency_days,
            frequency_type=frequency_type,
            biweekly_cycle=biweekly_cycle,
            amortization_type=amortization_type,
            start_date=start_date,
            status="activo",
        )
        if not client_id or not principal or not installments_count:
            flash("Cliente, monto en USD y número de cuotas son obligatorios.", "danger")
            return render_template(
                "loans/form.html",
                loan=loan,
                clients=clients,
                tasa_actual=tasa_actual,
                montos_disponibles=montos_disponibles,
            )
        db.session.add(loan)
        db.session.flush()
        for obligation in generate_obligations(loan):
            db.session.add(obligation)

        # Carga opcional de comprobante de envío / desembolso
        voucher_file = request.files.get("disbursement_voucher")
        if voucher_file and voucher_file.filename and allowed(voucher_file.filename):
            create_document("prestamo", loan.id, "comprobante", voucher_file, current_user.id)

        desc_modalidad = f"Semanal" if frequency_type == "semanal" else f"Quincenal (Corte {biweekly_cycle})"
        log_audit(current_user.id, "Crear préstamo", "Préstamo", loan.id, f"{loan.code} ${principal} USD {desc_modalidad} tasa {annual_rate}%")
        db.session.commit()
        flash(f"Préstamo {loan.code} creado por ${principal:,.2f} USD ({desc_modalidad}) con tasa fija de {annual_rate}%.", "success")
        return redirect(url_for("loans.detail", loan_id=loan.id))

    return render_template(
        "loans/form.html",
        loan=None,
        clients=clients,
        tasa_actual=tasa_actual,
        montos_disponibles=montos_disponibles,
    )


@bp.route("/<int:loan_id>")
@login_required
@permission_required("loans.view")
def detail(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    principal_val = float(loan.principal)
    total_capital_paid = sum(
        (float(o.capital or 0) - float(o.pending_capital or 0) for o in loan.obligations),
        0.0
    )
    pct_paid = round((total_capital_paid / principal_val * 100), 1) if principal_val > 0 else 0.0
    voucher_doc = Document.query.filter_by(entity_type="prestamo", entity_id=loan.id, doc_type="comprobante").first()

    return render_template(
        "loans/detail.html",
        loan=loan,
        total_capital_paid=total_capital_paid,
        pct_paid=pct_paid,
        voucher_doc=voucher_doc,
    )


@bp.route("/<int:loan_id>/comprobante", methods=["POST"])
@login_required
@permission_required("loans.create")
def upload_voucher(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    file = request.files.get("disbursement_voucher")
    if not file or not file.filename:
        flash("Debe seleccionar un archivo para el comprobante.", "danger")
    elif not allowed(file.filename):
        flash("Formato de archivo no permitido (use PDF, PNG, JPG, JPEG o WEBP).", "danger")
    else:
        doc = Document.query.filter_by(entity_type="prestamo", entity_id=loan.id, doc_type="comprobante").first()
        if doc:
            replace_file(doc, file)
            flash("Comprobante de desembolso actualizado exitosamente.", "success")
        else:
            create_document("prestamo", loan.id, "comprobante", file, current_user.id)
            flash("Comprobante de desembolso cargado exitosamente.", "success")
        log_audit(current_user.id, "Cargar comprobante de desembolso", "Préstamo", loan.id, f"{loan.code}: {file.filename}")
        db.session.commit()
    return redirect(url_for("loans.detail", loan_id=loan.id))
