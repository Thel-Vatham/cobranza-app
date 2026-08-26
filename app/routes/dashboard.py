from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from ..models import Client, CollectionManagement, Loan, Obligation, Parameter, Payment
from ..services.decorators import permission_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
@permission_required("dashboard.view")
def index():
    today = datetime.utcnow().date()
    horizon_days = int(Parameter.get("dias_proximos_vencer", "15") or 15)
    horizon = today + timedelta(days=horizon_days)

    loans = Loan.query.all()
    obligations = Obligation.query.all()

    # Capital original total desembolsado y saldos actuales
    capital_disbursed = sum((float(l.principal) for l in loans), 0.0)
    total_portfolio = sum((float(l.outstanding_balance) for l in loans), 0.0)

    # Obligaciones realmente vencidas (con saldo pendiente real > 0 y no pagadas)
    overdue_obligations = [
        o for o in obligations
        if o.status != "pagada" and float(o.pending_balance) > 0 and o.due_date < today
    ]
    overdue_obligations.sort(key=lambda o: o.due_date)
    overdue_portfolio = sum((float(o.pending_balance) for o in overdue_obligations), 0.0)
    active_portfolio = max(0.0, total_portfolio - overdue_portfolio)

    # Próximas obligaciones: solo la SIGUIENTE cuota por cada préstamo dentro del horizonte
    upcoming_by_loan = {}
    for o in sorted(obligations, key=lambda x: x.due_date):
        if o.status != "pagada" and float(o.pending_balance) > 0 and today <= o.due_date <= horizon:
            if o.loan_id not in upcoming_by_loan:
                upcoming_by_loan[o.loan_id] = o
    upcoming = list(upcoming_by_loan.values())

    # Pagos ordenados por fecha de pago más reciente primero
    payments_recent = Payment.query.order_by(
        Payment.payment_date.desc(), Payment.created_at.desc()
    ).limit(8).all()

    collections_today = CollectionManagement.query.filter(
        CollectionManagement.next_date == today
    ).count()

    # Recaudo por periodo (últimos 30 días)
    last30 = today - timedelta(days=30)
    collected_30 = sum(
        (float(p.amount) for p in Payment.query.all() if p.payment_date >= last30), 0.0
    )

    indicators = {
        "capital_desembolsado": capital_disbursed,
        "cartera_total": total_portfolio,
        "cartera_vigente": active_portfolio,
        "cartera_vencida": overdue_portfolio,
        "obligaciones_vencidas": len(overdue_obligations),
        "prestamos_activos": sum(1 for l in loans if l.status in ("activo", "mora")),
        "recaudo_30d": collected_30,
        "clientes": Client.query.count(),
    }

    return render_template(
        "dashboard.html",
        indicators=indicators,
        upcoming=upcoming[:10],
        overdue=overdue_obligations[:10],
        payments_recent=payments_recent,
        collections_today=collections_today,
        today=today,
        tomorrow=today + timedelta(days=1),
        day_after=today + timedelta(days=2),
        horizon_days=horizon_days,
    )
