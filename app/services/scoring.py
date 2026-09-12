"""Score y semáforo de comportamiento de pago."""
from datetime import datetime
from ..models import Parameter


def get_client_behavior_status(client):
    """
    Determina el semáforo y estado de comportamiento visual del cliente:
    - 'blanco'  : Crédito solicitado / en curso sin mora o cliente al día tras pagar sus compromisos.
    - 'verde'   : Ha efectuado pagos y se encuentra al día sin cuotas en mora.
    - 'naranja' : Entró en mora (1 a 14 días de atraso en alguna cuota activa).
    - 'rojo'    : Acumula una quincena o más de mora (>= 15 días de atraso).
    """
    today = datetime.utcnow().date()
    all_obligations = []
    has_loans = bool(client.loans)
    for loan in client.loans:
        all_obligations.extend(loan.obligations)

    if not all_obligations:
        # Cliente registrado sin créditos activos aún
        return {
            "key": "blanco",
            "label": "Sin Deuda / Solicitud",
            "badge_class": "badge-light",
            "color": "#64748b",
            "bg": "#f8fafc",
            "border": "#cbd5e1",
            "dot": "#94a3b8",
            "description": "Cliente nuevo o solicitud inicial sin historial de vencimiento."
        }

    # Revisar mora activa (cuotas pendientes cuya fecha de vencimiento ya pasó)
    unpaid = [o for o in all_obligations if o.status != "pagada"]
    paid_obligations = [o for o in all_obligations if o.status == "pagada"]
    has_partial_payment = any(o.status == "parcial" or (o.pending_balance < (float(o.scheduled_value or 0))) for o in unpaid)

    # Revisar si el cliente tiene algún pago aplicado en el sistema
    total_payments = 0
    for loan in client.loans:
        total_payments += sum(1 for p in loan.payments if p.status == "aplicado")

    has_made_payments = (len(paid_obligations) > 0) or has_partial_payment or (total_payments > 0)

    # Calcular máxima mora actual en cuotas no saldadas
    max_active_late_days = 0
    for o in unpaid:
        if o.due_date and o.due_date < today:
            days = (today - o.due_date).days
            if days > max_active_late_days:
                max_active_late_days = days

    if max_active_late_days >= 15:
        # Rojo: Acumuló 1 quincena o más de mora (15+ días)
        return {
            "key": "rojo",
            "label": f"Mora Crítica ({max_active_late_days}d)",
            "badge_class": "badge-danger",
            "color": "#dc2626",
            "bg": "#fef2f2",
            "border": "#fca5a5",
            "dot": "#ef4444",
            "description": f"Mora superior o igual a 1 quincena ({max_active_late_days} días de retraso)."
        }
    elif max_active_late_days >= 1:
        # Naranja: Entró en mora así sea 1 día hasta 14 días
        return {
            "key": "naranja",
            "label": f"En Mora ({max_active_late_days}d)",
            "badge_class": "badge-warning",
            "color": "#ea580c",
            "bg": "#fff7ed",
            "border": "#fdba74",
            "dot": "#f97316",
            "description": f"Atraso reciente en cuota ({max_active_late_days} día(s) de atraso)."
        }
    else:
        # Sin mora activa (0 días de atraso)
        if not unpaid:
            # Crédito liquidado/pagado totalmente o sin obligaciones pendientes -> Vuelve a quedar en blanco (Paz y Salvo)
            return {
                "key": "blanco",
                "label": "Paz y Salvo (Completado)",
                "badge_class": "badge-light",
                "color": "#475569",
                "bg": "#f8fafc",
                "border": "#cbd5e1",
                "dot": "#94a3b8",
                "description": "Crédito cancelado en su totalidad (Paz y Salvo)."
            }
        else:
            # Tiene crédito activo, no está en mora y aún no se ha llegado la fecha de pago
            return {
                "key": "verde",
                "label": "Al Día (Aún no vence)",
                "badge_class": "badge-success",
                "color": "#166534",
                "bg": "#f0fdf4",
                "border": "#86efac",
                "dot": "#22c55e",
                "description": "Cliente al día: sin mora activa y aún no vence su fecha de pago."
            }


def compute_score(client):
    """Calcula un score 0-100 basado en el historial verificable del cliente y los parámetros del sistema."""
    behavior_status = get_client_behavior_status(client)
    obligations = []
    for loan in client.loans:
        obligations.extend(loan.obligations)

    if not obligations:
        return {"score": None, "detail": "Sin historial suficiente.", "behavior": behavior_status}

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
        "behavior": behavior_status,
        "detail": {
            "total_obligaciones": total,
            "pagadas": len(paid),
            "puntualidad": round(punctuality * 100, 1),
            "cumplimiento": round(compliance * 100, 1),
            "max_dias_mora": max_days_late,
            "obligaciones_vencidas": overdue_count,
        },
    }
