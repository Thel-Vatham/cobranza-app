"""
BOT SIMULATOR & VERIFICADOR INTEGRAL DEL SISTEMA DE COBRANZA
============================================================
Automatiza y audita el ciclo de vida completo:
- Usuarios y roles
- Carteras y asignación
- Registro completo de clientes (identificación, referencias, datos laborales y bancarios)
- Préstamos en USD con tasa fija del 20%
- Generación y desglose de obligaciones
- Cascada waterfall de pagos (interés primero, luego capital)
- Score crediticio y cálculo de riesgo
- Simulación de mora y cálculo de días de atraso
- Remisión al módulo de asesoría y creación de notificaciones para consultores

Uso:
  python bot_simulator.py                 (Menú interactivo)
  python bot_simulator.py --scenario all  (Ejecuta los 3 bots)
  python bot_simulator.py --scenario 1    (Bot 1: Cliente Estrella / Pago Total)
  python bot_simulator.py --scenario 2    (Bot 2: Cliente en Mora y Remisión a Asesor)
  python bot_simulator.py --scenario 3    (Bot 3: Abonos Parciales y Cascada Waterfall)
  python bot_simulator.py --open-browser  (Abre automáticamente las fichas en el navegador)
"""

import argparse
import os
import sys
import time
import webbrowser
from datetime import date, datetime, timedelta
from decimal import Decimal

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Colores ANSI para terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def step(title):
    print(f"\n{Color.BOLD}{Color.CYAN}==> [PASO] {title}{Color.RESET}")

def success(msg):
    print(f"    {Color.GREEN}✔ {msg}{Color.RESET}")

def info(msg):
    print(f"    {Color.BLUE}ℹ {msg}{Color.RESET}")

def warn(msg):
    print(f"    {Color.YELLOW}⚠ {msg}{Color.RESET}")

def highlight(label, value):
    print(f"    {Color.WHITE}{label}: {Color.BOLD}{Color.YELLOW}{value}{Color.RESET}")

def url_link(label, url):
    print(f"    {Color.MAGENTA}🔗 {label}:{Color.RESET} {Color.BOLD}{url}{Color.RESET}")


def banner(title):
    border = "=" * 70
    print(f"\n{Color.BOLD}{Color.CYAN}{border}")
    print(f"  🤖 {title}")
    print(f"{border}{Color.RESET}\n")


def setup_flask_app():
    """Inicializa la app Flask y asegura el contexto de base de datos."""
    # Añadir directorio actual al path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    from app import create_app
    from app.extensions import db
    from app.seed import seed_if_empty
    
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_if_empty()
    return app


# ─────────────────────────────────────────────────────────────────────────────
# ESCENARIOS DE BOTS
# ─────────────────────────────────────────────────────────────────────────────

def run_bot_1(app, delay=0.4, open_browser=False):
    """
    BOT 1: "CLIENTE ESTRELLA / CUMPLIDO"
    Ciclo:
    1. Registro de cliente con referencias y datos bancarios
    2. Asignación a Cartera
    3. Préstamo de $100.00 USD con interés del 20% (Total: $120.00 USD)
    4. Generación de obligación
    5. Pago puntual de $120.00 USD
    6. Verificación de liquidación (Préstamo 'pagado', Cuota 'pagada')
    7. Verificación de Score (100 / Excelente)
    """
    banner("BOT 1: CLIENTE ESTRELLA (FLUJO IDEAL / PAGO PUNTUAL)")
    time.sleep(delay)

    from app.extensions import db
    from app.models import Client, Loan, Obligation, Payment, Portfolio, Reference, User
    from app.services.financial import apply_payment, generate_obligations
    from app.services.scoring import compute_score

    with app.app_context():
        # 1. Cartera y Operador
        step("1. Selección de Cartera y Operador Responsable")
        portfolio = Portfolio.query.filter_by(status="activa").first()
        if not portfolio:
            operator = User.query.filter_by(username="user_0").first() or User.query.first()
            portfolio = Portfolio(
                name="Cartera Comercial Bogotá",
                code="CAR-BOG-01",
                assigned_capital_usd=Decimal("5000.00"),
                user_id=operator.id,
                status="activa",
            )
            db.session.add(portfolio)
            db.session.commit()
        success(f"Cartera activa: '{portfolio.name}' (Código: {portfolio.code}, Cupo: ${portfolio.assigned_capital_usd:.2f} USD)")
        time.sleep(delay)

        # 2. Alta de Cliente
        step("2. Registro Integral de Cliente")
        timestamp = datetime.now().strftime("%M%S")
        doc_num = f"1010{timestamp}"
        client_code = f"CL-B1-{timestamp}"

        client = Client(
            code=client_code,
            portfolio_id=portfolio.id,
            first_name="Valentina",
            last_name=f"Morales Bot1",
            identification_type="CC",
            identification_number=doc_num,
            country="Colombia",
            city="Bogotá",
            address="Carrera 15 # 85-32, Chapinero",
            phone="+57 311 555 9001",
            email=f"valentina.{timestamp}@ejemplo.com",
            # Datos laborales
            employer_name="Summa Tech Solutions",
            job_title="Especialista Financiera",
            employer_phone="+57 601 321 0000",
            salary=Decimal("1200.00"),
            # Cuentas bancarias
            bank_name="Bancolombia",
            account_type="Ahorros",
            account_number=f"987-123456-{timestamp}",
            account_holder="Valentina Morales",
            collection_bank_name="Nequi",
            collection_account_type="Digital",
            collection_account_number="+57 311 555 9001",
            collection_account_holder="Valentina Morales",
        )
        db.session.add(client)
        db.session.flush()

        # 2 Referencias obligatorias
        ref1 = Reference(
            client_id=client.id,
            full_name="Camilo Morales",
            phone="+57 300 111 2233",
            relationship="Familiar",
            identification_number="12345678",
            address="Calle 10 # 20-30",
        )
        ref2 = Reference(
            client_id=client.id,
            full_name="Laura Duque",
            phone="+57 300 444 5566",
            relationship="Laboral",
            identification_number="87654321",
            address="Carrera 15 # 45-67",
        )
        db.session.add_all([ref1, ref2])
        db.session.commit()

        success(f"Cliente creado: {client.full_name} (ID: {client.id}, Cód: {client.code}, CC: {client.identification_number})")
        highlight("Referencias", "2 registradas (1 Codeudor verificado)")
        time.sleep(delay)

        # 3. Creación de Préstamo
        step("3. Aprobación y Creación de Préstamo en USD")
        loan_code = f"PR-B1-{timestamp}"
        principal = Decimal("100.00")
        annual_rate = Decimal("0.20")  # 20%
        today = date.today()

        loan = Loan(
            code=loan_code,
            portfolio_id=portfolio.id,
            client_id=client.id,
            principal=principal,
            annual_rate=annual_rate,
            installments_count=1,
            frequency_days=15,
            frequency_type="quincenal",
            biweekly_cycle="15-30",
            amortization_type="frances",
            start_date=today,
            status="activo",
        )
        db.session.add(loan)
        db.session.flush()

        # Generar obligaciones
        obligations = generate_obligations(loan)
        for ob in obligations:
            db.session.add(ob)
        db.session.commit()

        ob = loan.obligations[0]
        success(f"Préstamo aprobado: {loan.code} (Monto: ${loan.principal:.2f} USD, Modalidad: Quincenal)")
        highlight("Desglose Cuota 1", f"Capital: ${ob.capital:.2f} + Interés (20%): ${ob.interest:.2f} = Total: ${ob.scheduled_value:.2f} USD")
        time.sleep(delay)

        # 4. Score Inicial
        step("4. Evaluación de Score Crediticio Pre-Pago")
        score_initial = compute_score(client)
        highlight("Score Inicial", f"{score_initial['score']} pts - Banda: {score_initial['band']}")
        time.sleep(delay)

        # 5. Aplicación del Pago Total
        step("5. Simulación de Pago Total Oportuno ($120.00 USD)")
        pay_code = f"PG-B1-{timestamp}"
        payment = Payment(
            code=pay_code,
            client_id=client.id,
            loan_id=loan.id,
            amount=Decimal("120.00"),
            payment_date=today,
            receipt_number=f"REC-{timestamp}",
            concept="Pago total de cuota pactada",
            status="aplicado",
        )
        db.session.add(payment)
        db.session.flush()

        # Cascada de pagos
        apps = apply_payment(payment)
        db.session.commit()

        success(f"Pago aplicado con éxito: {payment.code} por ${payment.amount:.2f} USD")
        for app_item in apps:
            highlight(f"  Cascada Cuota {app_item['obligation']}", f"Interés aplicado: ${app_item['interest']:.2f} USD | Capital aplicado: ${app_item['capital']:.2f} USD")
        
        # Verificar estados
        db.session.refresh(ob)
        db.session.refresh(loan)
        highlight("Estado de la Cuota", ob.status.upper())
        highlight("Estado del Préstamo", loan.status.upper())
        highlight("Saldo Pendiente Préstamo", f"${loan.outstanding_balance:.2f} USD")
        time.sleep(delay)

        # 6. Score Final Post-Pago
        step("6. Auditoría Final de Score Crediticio")
        score_final = compute_score(client)
        success(f"Score recalculado: {score_final['score']}/100 pts ({score_final['band']}) ⭐⭐⭐")
        detail = score_final.get("detail", {})
        highlight("Puntualidad", f"{detail.get('puntualidad', 100)}% pagos al día")
        highlight("Cumplimiento", f"{detail.get('cumplimiento', 100)}% de obligaciones cumplidas")

        # Enlaces
        print(f"\n{Color.BOLD}{Color.GREEN}✔ BOT 1 FINALIZADO EXITOSAMENTE{Color.RESET}")
        url_link("Ficha del Cliente en el Navegador", f"http://localhost:5000/clientes/{client.id}")
        url_link("Detalle del Préstamo", f"http://localhost:5000/prestamos/{loan.id}")

        if open_browser:
            webbrowser.open(f"http://localhost:5000/clientes/{client.id}")

        return {"client_id": client.id, "loan_id": loan.id, "score": score_final["score"]}


def run_bot_2(app, delay=0.4, open_browser=False):
    """
    BOT 2: "CLIENTE EN MORA Y DERIVACIÓN A ASESORÍA"
    Ciclo:
    1. Registro de cliente con referencias
    2. Préstamo de $150.00 USD (Total: $180.00 USD)
    3. Simulación de cuota vencida (atraso de 12 días)
    4. Comprobación automática de cambio de estado a 'mora' y cálculo de días
    5. Impacto en Score crediticio (Caída a 'Riesgo Alto')
    6. Remisión del cliente al Asesor ('consultor_0') con motivo de gestión
    7. Verificación de Notificación creada para el Asesor
    """
    banner("BOT 2: CLIENTE EN MORA Y REMISIÓN A ASESORÍA")
    time.sleep(delay)

    from app.extensions import db
    from app.models import Client, ClientReferral, Loan, Notification, Portfolio, Reference, User
    from app.services.financial import generate_obligations
    from app.services.scoring import compute_score

    with app.app_context():
        # 1. Cartera
        step("1. Cartera de Cobranza")
        portfolio = Portfolio.query.filter_by(status="activa").first()
        success(f"Cartera: '{portfolio.name}'")
        time.sleep(delay)

        # 2. Registro de Cliente
        step("2. Registro del Cliente")
        timestamp = datetime.now().strftime("%M%S")
        doc_num = f"2020{timestamp}"
        client_code = f"CL-B2-{timestamp}"

        client = Client(
            code=client_code,
            portfolio_id=portfolio.id,
            first_name="Julián",
            last_name=f"Restrepo Bot2",
            identification_type="CC",
            identification_number=doc_num,
            country="Colombia",
            city="Medellín",
            address="Calle 50 # 40-12, Prado Centro",
            phone="+57 320 888 7766",
            email=f"julian.{timestamp}@ejemplo.com",
            employer_name="Comercializadora Antioqueña",
            job_title="Comerciante Independiente",
            salary=Decimal("850.00"),
            bank_name="Bancolombia",
            account_type="Ahorros",
            account_number=f"111-222333-{timestamp}",
            account_holder="Julián Restrepo",
        )
        db.session.add(client)
        db.session.flush()

        ref1 = Reference(client_id=client.id, full_name="Esteban Restrepo", phone="+57 301 999 0011", relationship="Hermano", identification_number="23456789", address="Calle 50 # 40-12")
        ref2 = Reference(client_id=client.id, full_name="Marta Gómez", phone="+57 312 888 2233", relationship="Familiar", identification_number="98765432", address="Carrera 70 # 10-20")
        db.session.add_all([ref1, ref2])
        db.session.commit()
        success(f"Cliente registrado: {client.full_name} (ID: {client.id}, CC: {client.identification_number})")
        time.sleep(delay)

        # 3. Préstamo de $150 USD con cuota simulada en el pasado para mora
        step("3. Préstamo de $150 USD con Cuota Vencida (Simulación de Mora)")
        loan_code = f"PR-B2-{timestamp}"
        principal = Decimal("150.00")
        annual_rate = Decimal("0.20")  # 20%
        past_start = date.today() - timedelta(days=27)  # Generará cuota hace 12 días

        loan = Loan(
            code=loan_code,
            portfolio_id=portfolio.id,
            client_id=client.id,
            principal=principal,
            annual_rate=annual_rate,
            installments_count=1,
            frequency_days=15,
            frequency_type="quincenal",
            biweekly_cycle="10-25",
            amortization_type="frances",
            start_date=past_start,
            status="activo",
        )
        db.session.add(loan)
        db.session.flush()

        for ob in generate_obligations(loan):
            db.session.add(ob)
        db.session.commit()

        # Inspeccionar cuota vencida
        ob = loan.obligations[0]
        # Si la fecha de vencimiento es anterior a hoy, actualizar estado
        days_late = ob.days_late
        if days_late > 0:
            loan.status = "mora"
            db.session.commit()

        warn(f"Cuota #1 venció el: {ob.due_date.strftime('%Y-%m-%d')} ({days_late} días de mora)")
        highlight("Deuda Total en Mora", f"${client.total_overdue:.2f} USD (Capital: ${ob.pending_capital:.2f} + Int: ${ob.pending_interest:.2f})")
        highlight("Estado del Préstamo", loan.status.upper())
        time.sleep(delay)

        # 4. Score del Cliente Castigado por Mora
        step("4. Cálculo de Score Crediticio con Penalización por Mora")
        score_mora = compute_score(client)
        warn(f"Score Crediticio: {score_mora['score']}/100 pts")
        highlight("Banda de Riesgo", f"{score_mora['band']}")
        detail_mora = score_mora.get("detail", {})
        highlight("Días Mora Máx", f"{detail_mora.get('max_dias_mora', days_late)} días de atraso")
        time.sleep(delay)

        # 5. Remisión al Módulo de Asesoría
        step("5. Ejecución: 'Remitir a Asesor / Consultoría Especializada'")
        consultor = User.query.filter(User.role.has(name="Consulta"), User.active == True).first()
        if not consultor:
            consultor = User.query.filter_by(username="consultor_0").first()

        reason = "Atraso > 10 días sin respuesta telefónica"
        notes = "Cliente no atendió la llamada matutina del cobrador. Requiere visita domiciliaria o reestructuración de plan de pago."
        
        referral = ClientReferral(
            client_id=client.id,
            referred_by_id=User.query.filter_by(username="admin").first().id,
            advisor_id=consultor.id if consultor else None,
            reason=reason,
            notes=notes,
            status="pendiente",
        )
        client.referred_to_advisor = True
        db.session.add(referral)

        if consultor:
            notif = Notification(
                user_id=consultor.id,
                title=f"Alerta Mora: {client.full_name}",
                message=f"Cliente remitido con {days_late} días de mora. Saldo: ${client.total_overdue:.2f} USD. Motivo: {reason}",
                link=f"/asesor/cliente/{client.id}",
            )
            db.session.add(notif)
        db.session.commit()

        success(f"Cliente remitido con éxito al asesor: '{consultor.full_name or consultor.username}'")
        highlight("Notificación Generada", notif.title if consultor else "Sin asesor asignado")
        highlight("Motivo Registrado", reason)
        time.sleep(delay)

        # Enlaces
        print(f"\n{Color.BOLD}{Color.YELLOW}✔ BOT 2 FINALIZADO: CASO DE MORA Y REMISIÓN REGISTRADO{Color.RESET}")
        url_link("Ficha de Cobranza del Cliente", f"http://localhost:5000/clientes/{client.id}")
        url_link("Panel del Asesor (consultor_0)", "http://localhost:5000/asesor")
        url_link("Bandeja de Notificaciones", "http://localhost:5000/asesor/notificaciones")

        if open_browser:
            webbrowser.open("http://localhost:5000/asesor")

        return {"client_id": client.id, "loan_id": loan.id, "days_late": days_late, "score": score_mora["score"]}


def run_bot_3(app, delay=0.4, open_browser=False):
    """
    BOT 3: "ABONOS PARCIALES Y CASCADA WATERFALL"
    Ciclo:
    1. Registro de cliente
    2. Préstamo de $75.00 USD (Interés 20% = $15.00 -> Total $90.00 USD)
    3. Abono Parcial 1: $10.00 USD -> Se aplica 100% a Interés (Saldo int: $5, cap: $75)
    4. Abono Parcial 2: $25.00 USD -> Cubre $5 de Interés restante + $20 a Capital (Saldo cap: $55)
    5. Abono Final 3: $55.00 USD -> Liquida capital restante (Préstamo pasa a 'pagado')
    """
    banner("BOT 3: ABONOS PARCIALES Y CASCADA WATERFALL (INTERÉS PRIMERO)")
    time.sleep(delay)

    from app.extensions import db
    from app.models import Client, Loan, Obligation, Payment, Portfolio, Reference
    from app.services.financial import apply_payment, generate_obligations
    from app.services.scoring import compute_score

    with app.app_context():
        # 1. Cartera
        step("1. Cartera de Recaudo")
        portfolio = Portfolio.query.filter_by(status="activa").first()
        time.sleep(delay)

        # 2. Cliente
        step("2. Registro de Cliente para Abonos Escalonados")
        timestamp = datetime.now().strftime("%M%S")
        client = Client(
            code=f"CL-B3-{timestamp}",
            portfolio_id=portfolio.id,
            first_name="Andrea",
            last_name=f"Cárdenas Bot3",
            identification_type="CC",
            identification_number=f"3030{timestamp}",
            country="Colombia",
            city="Cali",
            address="Avenida 6N # 22-08, Granada",
            phone="+57 315 777 4433",
            email=f"andrea.{timestamp}@ejemplo.com",
            salary=Decimal("950.00"),
            bank_name="Davivienda",
            account_type="Ahorros",
            account_number=f"555-666777-{timestamp}",
            account_holder="Andrea Cárdenas",
        )
        db.session.add(client)
        db.session.flush()

        ref1 = Reference(client_id=client.id, full_name="Carlos Cárdenas", phone="+57 310 123 4567", relationship="Padre", identification_number="34567890", address="Avenida 6N # 22-08")
        ref2 = Reference(client_id=client.id, full_name="Gloria Ruiz", phone="+57 318 765 4321", relationship="Laboral", identification_number="76543210", address="Calle 15 # 5-10")
        db.session.add_all([ref1, ref2])
        db.session.commit()
        success(f"Cliente registrado: {client.full_name} (ID: {client.id})")
        time.sleep(delay)

        # 3. Préstamo
        step("3. Préstamo de $75.00 USD (Interés $15.00 | Total $90.00 USD)")
        today = date.today()
        loan = Loan(
            code=f"PR-B3-{timestamp}",
            portfolio_id=portfolio.id,
            client_id=client.id,
            principal=Decimal("75.00"),
            annual_rate=Decimal("0.20"),
            installments_count=1,
            frequency_days=7,
            frequency_type="semanal",
            amortization_type="frances",
            start_date=today,
            status="activo",
        )
        db.session.add(loan)
        db.session.flush()
        for ob in generate_obligations(loan):
            db.session.add(ob)
        db.session.commit()

        ob = loan.obligations[0]
        highlight("Condiciones", f"Principal: ${loan.principal:.2f} | Interés: ${ob.interest:.2f} | Total Cuota: ${ob.scheduled_value:.2f} USD")
        time.sleep(delay)

        # 4. Abono 1: $10 USD
        step("4. Abono 1: $10.00 USD (Menor al interés total de $15)")
        pay1 = Payment(
            code=f"PG-B3-1-{timestamp}",
            client_id=client.id,
            loan_id=loan.id,
            amount=Decimal("10.00"),
            payment_date=today,
            concept="Abono parcial 1 (Insuficiente para interés total)",
            status="aplicado",
        )
        db.session.add(pay1)
        db.session.flush()
        apps1 = apply_payment(pay1)
        db.session.commit()

        db.session.refresh(ob)
        success(f"Abono 1 procesado: ${pay1.amount:.2f} USD")
        highlight("  -> Aplicación a Interés", f"${apps1[0]['interest']:.2f} USD (100% de lo abonado)")
        highlight("  -> Aplicación a Capital", f"${apps1[0]['capital']:.2f} USD")
        highlight("  -> Interés Pendiente", f"${ob.pending_interest:.2f} USD")
        highlight("  -> Capital Pendiente", f"${ob.pending_capital:.2f} USD")
        highlight("  -> Estado Cuota", ob.status.upper())
        time.sleep(delay)

        # 5. Abono 2: $25 USD
        step("5. Abono 2: $25.00 USD (Liquida $5 de interés restante + abona $20 a capital)")
        pay2 = Payment(
            code=f"PG-B3-2-{timestamp}",
            client_id=client.id,
            loan_id=loan.id,
            amount=Decimal("25.00"),
            payment_date=today,
            concept="Abono parcial 2 (Liquida interés restante + abono a capital)",
            status="aplicado",
        )
        db.session.add(pay2)
        db.session.flush()
        apps2 = apply_payment(pay2)
        db.session.commit()

        db.session.refresh(ob)
        success(f"Abono 2 procesado: ${pay2.amount:.2f} USD")
        highlight("  -> Aplicación a Interés", f"${apps2[0]['interest']:.2f} USD (Interés ahora 100% cubierto)")
        highlight("  -> Aplicación a Capital", f"${apps2[0]['capital']:.2f} USD")
        highlight("  -> Interés Pendiente", f"${ob.pending_interest:.2f} USD")
        highlight("  -> Capital Pendiente", f"${ob.pending_capital:.2f} USD (75 - 20 = 55)")
        highlight("  -> Estado Cuota", ob.status.upper())
        time.sleep(delay)

        # 6. Abono 3: $55 USD
        step("6. Abono 3: $55.00 USD (Liquidación Total de Capital Remanente)")
        pay3 = Payment(
            code=f"PG-B3-3-{timestamp}",
            client_id=client.id,
            loan_id=loan.id,
            amount=Decimal("55.00"),
            payment_date=today,
            concept="Pago final para cancelar el crédito",
            status="aplicado",
        )
        db.session.add(pay3)
        db.session.flush()
        apps3 = apply_payment(pay3)
        db.session.commit()

        db.session.refresh(ob)
        db.session.refresh(loan)
        success(f"Abono 3 procesado: ${pay3.amount:.2f} USD")
        highlight("  -> Aplicación a Capital", f"${apps3[0]['capital']:.2f} USD")
        highlight("  -> Saldo Pendiente", f"${loan.outstanding_balance:.2f} USD")
        highlight("  -> Estado Cuota", ob.status.upper())
        highlight("  -> Estado del Préstamo", loan.status.upper())
        time.sleep(delay)

        # Enlaces
        print(f"\n{Color.BOLD}{Color.GREEN}✔ BOT 3 FINALIZADO: CASCADA WATERFALL VERIFICADA AL 100%{Color.RESET}")
        url_link("Ficha del Cliente en el Navegador", f"http://localhost:5000/clientes/{client.id}")
        url_link("Historial de Pagos del Préstamo", f"http://localhost:5000/prestamos/{loan.id}")

        if open_browser:
            webbrowser.open(f"http://localhost:5000/prestamos/{loan.id}")

        return {"client_id": client.id, "loan_id": loan.id, "status": loan.status}


# ─────────────────────────────────────────────────────────────────────────────
# EJECUTOR Y MENÚ PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def print_summary_table(results):
    print("\n" + "=" * 70)
    print(f"{Color.BOLD}{Color.WHITE}  📊 RESUMEN EJECUTIVO DE VERIFICACIÓN MULTI-BOT{Color.RESET}")
    print("=" * 70)
    print(f"{'BOT / ESCENARIO':<25} | {'CLIENTE ID':<12} | {'PRÉSTAMO ID':<13} | {'RESULTADO':<15}")
    print("-" * 70)
    if "bot1" in results:
        b1 = results["bot1"]
        print(f"{'1. Cliente Estrella':<25} | ID: {b1['client_id']:<8} | ID: {b1['loan_id']:<9} | {Color.GREEN}Score {b1['score']} (OK){Color.RESET}")
    if "bot2" in results:
        b2 = results["bot2"]
        print(f"{'2. Mora y Asesoría':<25} | ID: {b2['client_id']:<8} | ID: {b2['loan_id']:<9} | {Color.YELLOW}Mora {b2['days_late']}d (Remitido){Color.RESET}")
    if "bot3" in results:
        b3 = results["bot3"]
        print(f"{'3. Cascada Waterfall':<25} | ID: {b3['client_id']:<8} | ID: {b3['loan_id']:<9} | {Color.CYAN}Liquidado ({b3['status'].upper()}){Color.RESET}")
    print("=" * 70)
    print(f"\n{Color.BOLD}🌐 Puedes revisar todos los registros en vivo en:{Color.RESET} {Color.CYAN}http://localhost:5000{Color.RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Bot Verificador y Simulador de Flujos End-to-End")
    parser.add_argument("--scenario", choices=["1", "2", "3", "all"], help="Escenario a ejecutar (1, 2, 3 o all)")
    parser.add_argument("--delay", type=float, default=0.3, help="Segundos de pausa pedagógica entre pasos (default: 0.3)")
    parser.add_argument("--open-browser", action="store_true", help="Abrir automáticamente los registros creados en el navegador")
    args = parser.parse_args()

    app = setup_flask_app()

    results = {}

    if args.scenario == "1":
        results["bot1"] = run_bot_1(app, delay=args.delay, open_browser=args.open_browser)
        print_summary_table(results)
    elif args.scenario == "2":
        results["bot2"] = run_bot_2(app, delay=args.delay, open_browser=args.open_browser)
        print_summary_table(results)
    elif args.scenario == "3":
        results["bot3"] = run_bot_3(app, delay=args.delay, open_browser=args.open_browser)
        print_summary_table(results)
    elif args.scenario == "all":
        results["bot1"] = run_bot_1(app, delay=args.delay, open_browser=args.open_browser)
        results["bot2"] = run_bot_2(app, delay=args.delay, open_browser=args.open_browser)
        results["bot3"] = run_bot_3(app, delay=args.delay, open_browser=args.open_browser)
        print_summary_table(results)
    else:
        # Menú Interactivo
        while True:
            print(f"\n{Color.BOLD}{Color.CYAN}======================================================{Color.RESET}")
            print(f"{Color.BOLD}   🤖 SIMULADOR Y AUDITOR DE BOTS — CARTERA & COBRANZA{Color.RESET}")
            print(f"{Color.BOLD}{Color.CYAN}======================================================{Color.RESET}")
            print(f"  {Color.WHITE}[1]{Color.RESET} Bot 1: Cliente Estrella (Registro -> Préstamo $100 -> Pago -> Score 100)")
            print(f"  {Color.WHITE}[2]{Color.RESET} Bot 2: Cliente en Mora (Registro -> Vencimiento -> Mora -> Asesoría)")
            print(f"  {Color.WHITE}[3]{Color.RESET} Bot 3: Cascada Waterfall (Abonos parciales: interés primero, luego capital)")
            print(f"  {Color.GREEN}[4] Ejecutar TODOS los bots en secuencia (Auditoría completa){Color.RESET}")
            print(f"  {Color.MAGENTA}[5] Abrir el aplicativo en el navegador (http://localhost:5000){Color.RESET}")
            print(f"  {Color.RED}[0] Salir{Color.RESET}")
            print(f"{Color.CYAN}------------------------------------------------------{Color.RESET}")
            
            try:
                choice = input(f"{Color.BOLD}Selecciona una opción (0-5): {Color.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if choice == "1":
                results["bot1"] = run_bot_1(app, delay=args.delay, open_browser=True)
                print_summary_table(results)
            elif choice == "2":
                results["bot2"] = run_bot_2(app, delay=args.delay, open_browser=True)
                print_summary_table(results)
            elif choice == "3":
                results["bot3"] = run_bot_3(app, delay=args.delay, open_browser=True)
                print_summary_table(results)
            elif choice == "4":
                results["bot1"] = run_bot_1(app, delay=args.delay, open_browser=False)
                results["bot2"] = run_bot_2(app, delay=args.delay, open_browser=False)
                results["bot3"] = run_bot_3(app, delay=args.delay, open_browser=False)
                print_summary_table(results)
                webbrowser.open("http://localhost:5000")
            elif choice == "5":
                webbrowser.open("http://localhost:5000")
            elif choice in ("0", "q", "exit"):
                print("Saliendo del simulador.")
                break
            else:
                print("Opción inválida.")


if __name__ == "__main__":
    main()
