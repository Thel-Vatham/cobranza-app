from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from ..models import Client, Loan, Obligation, Payment
from ..services.decorators import permission_required
from ..services.scoring import compute_score

bp = Blueprint("reports", __name__, url_prefix="/reportes")


@bp.route("/cartera")
@login_required
@permission_required("reports.view")
def portfolio():
    today = datetime.utcnow().date()
    loans = Loan.query.all()
    obligations = Obligation.query.all()

    total = sum((l.outstanding_balance for l in loans), 0.0)
    active = sum((l.outstanding_balance for l in loans if l.status == "activo"), 0.0)
    overdue_obligations = [o for o in obligations if o.status != "pagada" and o.due_date < today]
    overdue = sum((o.pending_balance for o in overdue_obligations), 0.0)

    collected = sum((float(p.amount) for p in Payment.query.filter_by(status="aplicado").all()), 0.0)

    # Distribución por estado
    distribution = {}
    for l in loans:
        distribution[l.status] = distribution.get(l.status, 0) + l.outstanding_balance

    indicators = {
        "total": total,
        "active": active,
        "overdue": overdue,
        "collected": collected,
        "loans_active": sum(1 for l in loans if l.status in ("activo", "mora")),
        "obligations_overdue": len(overdue_obligations),
        "avg_days_late": round(
            sum((o.days_late for o in overdue_obligations)) / len(overdue_obligations), 1
        ) if overdue_obligations else 0,
    }

    return render_template(
        "reports/portfolio.html",
        indicators=indicators,
        distribution=distribution,
        loans=loans,
    )


@bp.route("/score")
@login_required
@permission_required("reports.view")
def scoring():
    clients = Client.query.all()
    results = []
    for client in clients:
        s = compute_score(client)
        results.append({"client": client, "score": s})
    results.sort(key=lambda r: (r["score"].get("score") is None, -(r["score"].get("score") or 0)))
    return render_template("reports/scoring.html", results=results)
