"""Score de comportamiento de pago (0-100)."""
from datetime import datetime


def compute_score(client):
    """Calcula un score 0-100 basado en el historial verificable del cliente."""
    obligations = []
    for loan in client.loans:
        obligations.extend(loan.obligations)

    if not obligations:
        return {"score": None, "detail": "Sin historial suficiente."}

    total = len(obligations)
    paid = [o for o in obligations if o.status == "pagada"]

    # 1. Puntualidad: proporción pagada a tiempo (sin mora al momento del pago)
    on_time = 0
    for o in paid:
        if o.paid_date and o.paid_date <= o.due_date:
            on_time += 1
    punctuality = on_time / total if total else 0

    # 2. Cumplimiento: proporción de obligaciones pagadas
    compliance = len(paid) / total if total else 0

    # 3. Mora actual
    max_days_late = max((o.days_late for o in obligations if o.status != "pagada"), default=0)
    overdue_count = sum(1 for o in obligations if o.status != "pagada" and o.days_late > 0)

    # Pesos parametrizables
    w_punctuality = 0.45
    w_compliance = 0.35
    w_overdue = 0.20

    # Penalización por mora: 100 -> 0 conforme aumentan los días (máx 90)
    overdue_score = max(0.0, 1 - (max_days_late / 90.0))
    # Ajuste adicional por cantidad de obligaciones vencidas
    overdue_score = max(0.0, overdue_score - (overdue_count * 0.05))

    score = 100 * (
        w_punctuality * punctuality
        + w_compliance * compliance
        + w_overdue * overdue_score
    )

    score = max(0, min(100, round(score)))

    if score >= 80:
        band = "Excelente"
    elif score >= 60:
        band = "Bueno"
    elif score >= 40:
        band = "Regular"
    else:
        band = "Riesgo alto"

    return {
        "score": score,
        "band": band,
        "detail": {
            "total_obligaciones": total,
            "pagadas": len(paid),
            "puntualidad": round(punctuality * 100, 1),
            "cumplimiento": round(compliance * 100, 1),
            "max_dias_mora": max_days_late,
            "obligaciones_vencidas": overdue_count,
        },
    }
