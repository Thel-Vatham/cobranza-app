from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..models import Client, CollectionManagement, Loan, Obligation, Parameter, Payment, Portfolio
from ..services.decorators import permission_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    # Si el usuario tiene rol Consulta (Asesor), redirigir directamente a su panel especializado
    if current_user.role and current_user.role.name == "Consulta":
        return redirect(url_for("advisor.index"))

    today = datetime.utcnow().date()
    horizon_days = int(Parameter.get("dias_proximos_vencer", "15") or 15)
    horizon = today + timedelta(days=horizon_days)

    is_admin = bool(current_user.role and current_user.role.name == "Administrador")
    active_portfolio_id = session.get("active_portfolio_id")

    # Filtrar según cartera activa
    if not is_admin:
        if active_portfolio_id:
            loans = Loan.query.filter_by(portfolio_id=active_portfolio_id).all()
            clients_count = Client.query.filter_by(portfolio_id=active_portfolio_id).count()
        else:
            loans = []
            clients_count = 0
    else:
        if active_portfolio_id:
            loans = Loan.query.filter_by(portfolio_id=active_portfolio_id).all()
            clients_count = Client.query.filter_by(portfolio_id=active_portfolio_id).count()
        else:
            loans = Loan.query.all()
            clients_count = Client.query.count()

    loan_ids = [l.id for l in loans]
    obligations = Obligation.query.filter(Obligation.loan_id.in_(loan_ids)).all() if loan_ids else []

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
    active_portfolio_val = max(0.0, total_portfolio - overdue_portfolio)

    # Próximas obligaciones: solo la SIGUIENTE cuota por cada préstamo dentro del horizonte
    upcoming_by_loan = {}
    for o in sorted(obligations, key=lambda x: x.due_date):
        if o.status != "pagada" and float(o.pending_balance) > 0 and today <= o.due_date <= horizon:
            if o.loan_id not in upcoming_by_loan:
                upcoming_by_loan[o.loan_id] = o
    upcoming = list(upcoming_by_loan.values())

    # Pagos ordenados por fecha de pago más reciente primero
    payments_query = Payment.query
    if loan_ids:
        payments_query = payments_query.filter(Payment.loan_id.in_(loan_ids))
    elif not is_admin:
        payments_query = payments_query.filter(Payment.id == -1)

    payments_recent = payments_query.order_by(
        Payment.payment_date.desc(), Payment.created_at.desc()
    ).limit(8).all()

    # Recaudo por periodo (últimos 30 días)
    last30 = today - timedelta(days=30)
    collected_30 = sum(
        (float(p.amount) for p in payments_query.all() if p.payment_date >= last30), 0.0
    )

    collections_today = 0
    if loan_ids:
        collections_today = CollectionManagement.query.filter(
            CollectionManagement.loan_id.in_(loan_ids),
            CollectionManagement.next_date == today
        ).count()

    indicators = {
        "capital_desembolsado": capital_disbursed,
        "cartera_total": total_portfolio,
        "cartera_vigente": active_portfolio_val,
        "cartera_vencida": overdue_portfolio,
        "obligaciones_vencidas": len(overdue_obligations),
        "prestamos_activos": sum(1 for l in loans if l.status in ("activo", "mora")),
        "recaudo_30d": collected_30,
        "clientes": clients_count,
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
