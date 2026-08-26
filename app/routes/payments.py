from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, Document, Loan, Obligation, Payment
from ..services.decorators import permission_required
from ..services.documents import allowed, create_document
from ..services.financial import apply_payment, log_audit

bp = Blueprint("payments", __name__, url_prefix="/pagos")


def _generate_code():
    count = Payment.query.count() + 1
    return f"PG-{count:05d}"


@bp.route("/")
@login_required
@permission_required("payments.view")
def list_payments():
    q = request.args.get("q", "").strip()
    query = Payment.query
    if q:
        like = f"%{q}%"
        query = query.join(Client).filter(
            (Payment.code.ilike(like))
            | (Payment.receipt_number.ilike(like))
            | (Client.first_name.ilike(like))
            | (Client.last_name.ilike(like))
            | (Client.identification_number.ilike(like))
        )
    payments = query.order_by(Payment.created_at.desc()).all()
    return render_template("payments/list.html", payments=payments, q=q)


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("payments.create")
def create():
    loans = Loan.query.join(Client).order_by(Client.first_name).all()
    selected_loan = None

    if request.method == "POST":
        loan_id = request.form.get("loan_id", type=int)
        amount = request.form.get("amount", type=float)
        payment_date = datetime.strptime(request.form.get("payment_date"), "%Y-%m-%d").date()
        concept = request.form.get("concept", "").strip() or "Abono a préstamo"
        receipt_number = request.form.get("receipt_number", "").strip()

        loan = Loan.query.get_or_404(loan_id)
        if not amount or amount <= 0:
            flash("El valor recibido debe ser mayor a cero.", "danger")
            return render_template("payments/form.html", loans=loans, selected_loan=loan)

        payment = Payment(
            code=_generate_code(),
            client_id=loan.client_id,
            loan_id=loan.id,
            amount=amount,
            payment_date=payment_date,
            concept=concept,
            receipt_number=receipt_number or None,
            registered_by=current_user.id,
        )
        db.session.add(payment)
        db.session.flush()
        applications = apply_payment(payment)
        _save_comprobante(payment)
        log_audit(
            current_user.id, "Registrar pago", "Pago", payment.id,
            f"{payment.code} valor {amount} aplicado a {len(applications)} cuota(s)",
        )
        db.session.commit()
        flash("Pago registrado y aplicado correctamente.", "success")
        return redirect(url_for("payments.receipt", payment_id=payment.id))

    return render_template("payments/form.html", loans=loans, selected_loan=selected_loan)


def _save_comprobante(payment):
    """Asocia el comprobante documental subido al pago."""
    file = request.files.get("comprobante")
    if file and file.filename and allowed(file.filename):
        create_document("pago", payment.id, "comprobante", file, current_user.id)


@bp.route("/<int:payment_id>/comprobante", methods=["POST"])
@login_required
@permission_required("payments.create")
def attach_comprobante(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    file = request.files.get("comprobante")
    if not file or not file.filename:
        flash("Debe seleccionar un archivo.", "danger")
    elif not allowed(file.filename):
        flash("Formato de archivo no permitido.", "danger")
    else:
        create_document("pago", payment.id, "comprobante", file, current_user.id)
        log_audit(current_user.id, "Adjuntar comprobante", "Pago", payment.id, file.filename)
        db.session.commit()
        flash("Comprobante adjuntado al pago.", "success")
    return redirect(url_for("payments.receipt", payment_id=payment.id))


@bp.route("/<int:payment_id>/recibo")
@login_required
@permission_required("payments.view")
def receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    documents = Document.query.filter_by(entity_type="pago", entity_id=payment.id).order_by(Document.uploaded_at.desc()).all()
    return render_template("payments/receipt.html", payment=payment, documents=documents)


@bp.route("/<int:payment_id>/anular", methods=["POST"])
@login_required
@permission_required("payments.revert")
def revert(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.status == "anulado":
        flash("El pago ya está anulado.", "warning")
        return redirect(url_for("payments.list_payments"))

    # Reversión: devolver lo aplicado a cada obligación
    for app in payment.applications:
        obligation = app.obligation
        obligation.pending_capital = float(obligation.pending_capital) + float(app.capital_applied)
        obligation.pending_interest = float(obligation.pending_interest) + float(app.interest_applied)
        obligation.status = "pendiente"
        obligation.paid_date = None

    payment.status = "anulado"
    loan = payment.loan
    loan.status = "activo"
    log_audit(current_user.id, "Anular pago", "Pago", payment.id, f"{payment.code} anulado")
    db.session.commit()
    flash("Pago anulado. Saldos restaurados.", "success")
    return redirect(url_for("payments.list_payments"))
