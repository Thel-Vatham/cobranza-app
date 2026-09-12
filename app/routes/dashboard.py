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

    # Capital asignado total de la cartera (disponible total asignado)
    if active_portfolio_id:
        portfolio_obj = Portfolio.query.get(active_portfolio_id)
        assigned_capital = float(portfolio_obj.assigned_capital_usd) if portfolio_obj else 0.0
    elif is_admin:
        # Suma de todas las carteras
        assigned_capital = sum(float(p.assigned_capital_usd or 0) for p in Portfolio.query.all())
    else:
        assigned_capital = 0.0

    capital_disbursed = sum((float(l.principal) for l in loans), 0.0)
    total_portfolio = sum((float(l.outstanding_balance) for l in loans), 0.0)

    # Obligaciones realmente vencidas (con saldo pendiente real > 0 y no pagadas)
    overdue_obligations = [
        o for o in obligations
        if o.status != "pagada" and float(o.pending_balance) > 0 and o.due_date < today
    ]
    overdue_obligations.sort(key=lambda o: o.due_date)
    # Capital en mora sin interés
    overdue_portfolio = sum((float(o.pending_capital or 0) for o in overdue_obligations), 0.0)

    # Obligaciones vigentes al día (no vencidas, con saldo pendiente > 0)
    vigente_obligations = [
        o for o in obligations
        if o.status != "pagada" and float(o.pending_balance) > 0 and o.due_date >= today
    ]
    # Capital vigente al día sin interés
    active_portfolio_val = sum((float(o.pending_capital or 0) for o in vigente_obligations), 0.0)

    # Capital colocado activo total (sin interés) = vigente + mora
    capital_colocado_activo = active_portfolio_val + overdue_portfolio

    # Saldo disponible de la cartera = Asignado menos capital prestado activo
    saldo_disponible = max(0.0, assigned_capital - capital_colocado_activo)

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

    # Interés generado: solo de créditos PAGADOS (liquidados) en el último mes
    # Se suman los pagos que cubrieron interés en créditos que ya están pagados
    last30 = today - timedelta(days=30)
    paid_loan_ids = {l.id for l in loans if l.status == "pagado"}
    interes_mes = 0.0
    if paid_loan_ids and loan_ids:
        pagos_liquidados = Payment.query.filter(
            Payment.loan_id.in_(paid_loan_ids),
            Payment.payment_date >= last30
        ).all()
        # El interés de cada cuota = principal × tasa
        for p in pagos_liquidados:
            loan_ref = next((l for l in loans if l.id == p.loan_id), None)
            if loan_ref:
                interes_mes += float(loan_ref.principal) * float(loan_ref.annual_rate)

    collections_today = 0
    if loan_ids:
        collections_today = CollectionManagement.query.filter(
            CollectionManagement.loan_id.in_(loan_ids),
            CollectionManagement.next_date == today
        ).count()

    indicators = {
        "capital_desembolsado": capital_disbursed,
        "cartera_total": saldo_disponible,
        "saldo_disponible": saldo_disponible,
        "capital_asignado": assigned_capital,
        "cartera_vigente": active_portfolio_val,
        "cartera_vencida": overdue_portfolio,
        "obligaciones_vencidas": len(overdue_obligations),
        "prestamos_activos": sum(1 for l in loans if l.status in ("activo", "mora")),
        "interes_mes": interes_mes,
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
