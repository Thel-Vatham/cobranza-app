"""Motor financiero centralizado.

Implementa el cálculo de cuotas (amortización francesa / cuota fija) y la
aplicación transaccional de pagos. Reglas determinísticas y testeables.
"""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ..extensions import db
from ..models import Loan, Obligation, PaymentApplication, Audit, Parameter

CENTS = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def calculate_schedule(principal, annual_rate, installments_count, start_date, frequency_days=30, amortization_type="frances"):
    """Devuelve una lista de diccionarios con el plan de pagos."""
    principal = money(principal)
    annual_rate = float(annual_rate or 0)
    n = int(installments_count)

    # Tasa por período de pago (por cuota, quincenal o mensual).
    # Se usa directamente sin convertir a anual, ya que el parámetro
    # 'tasa_interes_periodo' representa el % de interés por cada cuota.
    period_rate = annual_rate

    # Cálculo de cuota fija (Francés)
    if amortization_type == "frances":
        if period_rate <= 0:
            payment = (principal / n).quantize(CENTS, rounding=ROUND_HALF_UP)
        else:
            factor = (1 + period_rate) ** (-n)
            payment = (principal * Decimal(str(period_rate)) / (1 - Decimal(str(factor)))).quantize(CENTS, rounding=ROUND_HALF_UP)
    
    # Cálculo de capital fijo (Alemán)
    elif amortization_type == "aleman":
        fixed_capital = (principal / n).quantize(CENTS, rounding=ROUND_HALF_UP)

    balance = principal
    schedule = []
    due = start_date
    for i in range(1, n + 1):
        interest = (balance * Decimal(str(period_rate))).quantize(CENTS, rounding=ROUND_HALF_UP)
        
        if amortization_type == "frances":
            capital = (payment - interest).quantize(CENTS, rounding=ROUND_HALF_UP)
            if i == n:
                capital = balance
            payment_val = (capital + interest).quantize(CENTS, rounding=ROUND_HALF_UP)
        else: # aleman
            capital = fixed_capital
            if i == n:
                capital = balance
            payment_val = (capital + interest).quantize(CENTS, rounding=ROUND_HALF_UP)
            
        capital = min(capital, balance)
        balance = (balance - capital).quantize(CENTS, rounding=ROUND_HALF_UP)
        
        schedule.append({
            "number": i,
            "due_date": due,
            "scheduled_value": payment_val,
            "capital": capital,
            "interest": interest,
        })
        due = due + timedelta(days=frequency_days)
    return schedule


def generate_obligations(loan: Loan) -> list[Obligation]:
    schedule = calculate_schedule(
        loan.principal, loan.annual_rate, loan.installments_count,
        loan.start_date, loan.frequency_days, loan.amortization_type
    )
    obligations = []
    for item in schedule:
        obligations.append(Obligation(
            loan_id=loan.id,
            number=item["number"],
            due_date=item["due_date"],
            scheduled_value=item["scheduled_value"],
            capital=item["capital"],
            interest=item["interest"],
            pending_capital=item["capital"],
            pending_interest=item["interest"],
            status="pendiente",
        ))
    return obligations


def apply_payment(payment) -> list[dict]:
    """Aplica un pago a las obligaciones pendientes según orden_aplicacion_pago.

    Orden configurable:
    - 'interes_primero' (Estándar): Intereses pendientes primero, luego capital.
    - 'capital_primero': Capital pendiente primero (reduce saldo rápido), luego intereses.
    """
    loan = payment.loan
    remaining = money(payment.amount)
    applications = []

    obligations = sorted(
        [o for o in loan.obligations if o.status != "pagada"],
        key=lambda o: (o.due_date, o.number),
    )

    order = Parameter.get("orden_aplicacion_pago", "interes_primero")

    for obligation in obligations:
        if remaining <= 0:
            break

        if order == "capital_primero":
            # 1. Capital primero
            capital_to_apply = min(money(obligation.pending_capital), remaining)
            remaining = (remaining - capital_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)
            # 2. Interés después
            interest_to_apply = min(money(obligation.pending_interest), remaining)
            remaining = (remaining - interest_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)
        else:
            # interes_primero (Estándar recomendado)
            # 1. Interés primero
            interest_to_apply = min(money(obligation.pending_interest), remaining)
            remaining = (remaining - interest_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)
            # 2. Capital después
            capital_to_apply = min(money(obligation.pending_capital), remaining)
            remaining = (remaining - capital_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)

        if interest_to_apply > 0 or capital_to_apply > 0:
            obligation.pending_interest = (money(obligation.pending_interest) - interest_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)
            obligation.pending_capital = (money(obligation.pending_capital) - capital_to_apply).quantize(CENTS, rounding=ROUND_HALF_UP)
            obligation.status = "pagada" if obligation.pending_balance <= 0 else "parcial"
            if obligation.status == "pagada":
                obligation.paid_date = payment.payment_date

            application = PaymentApplication(
                payment_id=payment.id,
                obligation_id=obligation.id,
                capital_applied=capital_to_apply,
                interest_applied=interest_to_apply,
            )
            applications.append({
                "obligation": obligation.number,
                "capital": float(capital_to_apply),
                "interest": float(interest_to_apply),
            })
            db.session.add(application)

    # Estado del préstamo
    if loan.outstanding_balance <= 0:
        loan.status = "pagado"
    elif any(o.days_late > 0 for o in loan.obligations if o.status != "pagada"):
        loan.status = "mora"
    else:
        loan.status = "activo"

    return applications


def log_audit(user_id, action, entity=None, entity_id=None, details=None):
    db.session.add(Audit(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
    ))


def days_late_for(obligation) -> int:
    if obligation.status == "pagada":
        return 0
    today = datetime.utcnow().date()
    return (today - obligation.due_date).days if obligation.due_date < today else 0
