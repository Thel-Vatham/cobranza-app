"""Score de comportamiento de pago (0-100)."""
from datetime import datetime
from ..models import Parameter


def compute_score(client):
    """Calcula un score 0-100 basado en el historial verificable del cliente y los parámetros del sistema."""
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

    # Tolerancia máxima de mora leída de los parámetros intuitivos (por defecto 30 días)
    dias_max = Parameter.get_float("dias_max_mora_score", 30.0)

    # Ponderaciones estandarizadas de producción (45% puntualidad, 35% cumplimiento, 20% mora)
    w_punctuality = 0.45
    w_compliance = 0.35
    w_overdue = 0.20

    # Penalización por mora: 100 -> 0 conforme aumentan los días (máx dias_max)
    overdue_score = max(0.0, 1.0 - (max_days_late / max(1.0, dias_max)))
    # Ajuste adicional por cantidad de obligaciones vencidas
    overdue_score = max(0.0, overdue_score - (overdue_count * 0.05))

    score = 100 * (
        w_punctuality * punctuality
        + w_compliance * compliance
        + w_overdue * overdue_score
    )

    score = max(0, min(100, round(score)))

    # Umbrales intuitivos parametrizables por el administrador
    u_excelente = Parameter.get_float("umbral_score_excelente", 80.0)
    u_bueno = Parameter.get_float("umbral_score_bueno", 60.0)
    u_regular = max(30.0, u_bueno - 20.0)

    if score >= u_excelente:
        band = "Excelente"
    elif score >= u_bueno:
        band = "Bueno"
    elif score >= u_regular:
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
