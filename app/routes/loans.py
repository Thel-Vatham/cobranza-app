from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, Loan
from ..services.decorators import permission_required
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
    query = Loan.query
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
    loans = query.order_by(Loan.created_at.desc()).all()
    return render_template("loans/list.html", loans=loans, q=q, status=status)


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@permission_required("loans.create")
def create():
    clients = Client.query.order_by(Client.first_name).all()
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        principal = request.form.get("principal", type=float)
        annual_rate = request.form.get("annual_rate", type=float) or 0
        installments_count = request.form.get("installments_count", type=int)
        frequency_days = request.form.get("frequency_days", type=int) or 15
        amortization_type = request.form.get("amortization_type") or "frances"
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()

        loan = Loan(
            code=_generate_code(),
            client_id=client_id,
            principal=principal,
            annual_rate=annual_rate / 100.0 if annual_rate else 0,
            installments_count=installments_count,
            frequency_days=frequency_days,
            amortization_type=amortization_type,
            start_date=start_date,
            status="activo",
        )
        if not client_id or not principal or not installments_count:
            flash("Cliente, valor principal y número de cuotas son obligatorios.", "danger")
            return render_template("loans/form.html", loan=loan, clients=clients)
        db.session.add(loan)
        db.session.flush()
        for obligation in generate_obligations(loan):
            db.session.add(obligation)
        log_audit(current_user.id, "Crear préstamo", "Préstamo", loan.id, f"{loan.code} monto {principal}")
        db.session.commit()
        flash(f"Préstamo {loan.code} creado con {installments_count} cuotas.", "success")
        return redirect(url_for("loans.detail", loan_id=loan.id))
    return render_template("loans/form.html", loan=None, clients=clients)


@bp.route("/<int:loan_id>")
@login_required
@permission_required("loans.view")
def detail(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    principal_val = float(loan.principal)
    balance_val = float(loan.outstanding_balance)
    total_capital_paid = max(0.0, principal_val - balance_val)
    pct_paid = round((total_capital_paid / principal_val * 100), 1) if principal_val > 0 else 0.0
    return render_template(
        "loans/detail.html",
        loan=loan,
        total_capital_paid=total_capital_paid,
        pct_paid=pct_paid,
    )
