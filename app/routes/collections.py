from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
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

    overdue = []
    obligations = Obligation.query.join(Loan).join(Client).all()
    for o in obligations:
        if o.status != "pagada" and o.due_date < today:
            overdue.append(o)

    if q:
        like = f"%{q}%"
        overdue = [
            o for o in overdue
            if like.strip("%") in (o.loan.client.full_name.lower() if o.loan.client else "")
            or like.strip("%") in (o.loan.client.identification_number.lower() if o.loan.client else "")
            or like.strip("%") in (o.loan.code.lower() if o.loan else "")
        ]

    overdue.sort(key=lambda o: o.due_date)
    return render_template("collections/list.html", overdue=overdue, today=today, q=q)


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
