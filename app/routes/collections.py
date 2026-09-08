from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Client, CollectionManagement, Loan, Obligation
from ..services.decorators import permission_required
from ..services.financial import log_audit

bp = Blueprint("collections", __name__, url_prefix="/cobranza")


@bp.route("/")
@login_required
@permission_required("collections.view")
def list_collections():
    today = datetime.utcnow().date()
    q = request.args.get("q", "").strip()
    timing = request.args.get("timing", "vencidas").strip()
    freq = request.args.get("freq", "").strip()
    cycle = request.args.get("cycle", "").strip()
    amount = request.args.get("amount", type=float)

    is_admin = bool(current_user.role and current_user.role.name == "Administrador")
    active_portfolio_id = session.get("active_portfolio_id")

    query = Obligation.query.join(Loan).join(Client).filter(Obligation.status != "pagada")

    if not is_admin:
        if active_portfolio_id:
            query = query.filter(Loan.portfolio_id == active_portfolio_id)
        else:
            query = query.filter(Obligation.id == -1)
    else:
        if active_portfolio_id:
            query = query.filter(Loan.portfolio_id == active_portfolio_id)

    if timing == "vencidas":
        query = query.filter(Obligation.due_date < today)
    elif timing == "hoy":
        query = query.filter(Obligation.due_date == today)
    elif timing == "semana":
        next_week = today + timedelta(days=7)
        query = query.filter(Obligation.due_date >= today, Obligation.due_date <= next_week)
    elif timing == "todas":
        pass  # Todas las cuotas pendientes

    if freq:
        query = query.filter(Loan.frequency_type == freq)
    if cycle:
        query = query.filter(Loan.biweekly_cycle == cycle)
    if amount is not None:
        query = query.filter(Loan.principal == amount)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Client.first_name.ilike(like))
            | (Client.last_name.ilike(like))
            | (Client.identification_number.ilike(like))
            | (Loan.code.ilike(like))
        )

    overdue = query.order_by(Obligation.due_date.asc(), Obligation.number.asc()).all()

    # Montos configurados en parámetros
    from ..models import Parameter
    montos_raw = Parameter.get("montos_prestamo_disponibles", "75, 100, 125, 150")
    montos_disponibles = [m.strip() for m in montos_raw.split(",") if m.strip()]

    return render_template(
        "collections/list.html",
        overdue=overdue,
        today=today,
        q=q,
        timing=timing,
        freq=freq,
        cycle=cycle,
        amount=amount,
        montos_disponibles=montos_disponibles,
    )


@bp.route("/gestion/<int:obligation_id>", methods=["GET", "POST"])
@login_required
@permission_required("collections.create")
def register(obligation_id):
    obligation = Obligation.query.get_or_404(obligation_id)
    if request.method == "POST":
        action = request.form.get("action", "").strip() or "Gestión de cobro"
        notes_raw = request.form.get("notes", "").strip()
        comp_note = request.form.get("compromise_note", "").strip()
        final_notes = f"[{comp_note}] {notes_raw}".strip() if comp_note else notes_raw

        management = CollectionManagement(
            client_id=obligation.loan.client_id,
            loan_id=obligation.loan_id,
            obligation_id=obligation.id,
            action=action,
            notes=final_notes,
            next_date=datetime.strptime(request.form.get("next_date"), "%Y-%m-%d").date()
            if request.form.get("next_date") else None,
            created_by=current_user.id,
        )
        db.session.add(management)
        log_audit(
            current_user.id, "Registrar gestión de cobranza", "Cobranza", obligation.id,
            f"Cuota {obligation.number} del préstamo {obligation.loan.code}",
        )
        db.session.commit()
        flash("Gestión de cobranza registrada.", "success")
        return redirect(url_for("collections.list_collections"))
    return render_template("collections/form.html", obligation=obligation)


@bp.route("/gestiones")
@login_required
@permission_required("collections.view")
def history():
    records = CollectionManagement.query.order_by(CollectionManagement.created_at.desc()).limit(200).all()
    return render_template("collections/history.html", records=records)
