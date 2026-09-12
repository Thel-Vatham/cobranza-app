"""
Script generador de base de datos de prueba con 20 clientes y comportamientos reales:
- ⚪ BLANCO:
    1-3: Créditos nuevos recién solicitados/desembolsados (vigentes al día sin cuotas cumplidas aún).
    4-5: Clientes que ya cancelaron la totalidad de su crédito (Paz y Salvo).
- 🟢 VERDE (Al Día / Con Pagos):
    6-8: Abonan solo a interés (cubren interés de cuota y mantienen capital diferido al día).
    9-12: Abonan a capital e interés completos cuota a cuota (pagadores estrella excelentes).
- 🟠 NARANJA (En Mora 1 a 14 días):
    13-14: Mora reciente leve (2 a 4 días de atraso).
    15-16: Mora moderada (7 a 10 días de atraso, menos de 1 quincena).
- 🔴 ROJO (Mora Crítica >= 15 días):
    17-18: Mora de 1 quincena acumulada (15 a 20 días de atraso).
    19-20: Mora severa de más de 1 mes (30 a 60 días de atraso sin abonos).
"""
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app import create_app
from app.extensions import db
from app.models import (
    Client,
    Loan,
    Obligation,
    Payment,
    PaymentApplication,
    Portfolio,
    Reference,
    User,
)
from app.services.financial import generate_obligations, apply_payment, money


def seed_20_clients():
    app = create_app()
    with app.app_context():
        print("\n🚀 GENERANDO BASE DE DATOS DE ANÁLISIS (20 CLIENTES Y COMPORTAMIENTOS)...")

        # 1. Purgar datos previos de clientes, préstamos y pagos
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        Loan.query.delete()
        Reference.query.delete()
        Client.query.delete()
        db.session.commit()

        # 2. Obtener o crear Cartera Activa y Operador
        portfolio = Portfolio.query.first()
        if not portfolio:
            portfolio = Portfolio(
                name="Cartera Principal USD",
                code="CART-001",
                assigned_capital_usd=Decimal("50000.00"),
                currency="USD",
                status="activa"
            )
            db.session.add(portfolio)
            db.session.flush()

        operator = User.query.filter_by(username="user_0").first() or User.query.filter_by(username="admin").first()
        today = datetime.utcnow().date()

        # Lista de 20 clientes con datos completos
        dataset = [
            # ⚪ BLANCOS: Nuevos o Paz y Salvo
            {"id": 1, "code": "CL-00001", "name": "Alejandro Morales", "cc": "1018475891", "city": "Bogotá", "behavior": "blanco_nuevo", "loan_amt": 300, "cuotas": 4, "desc": "Crédito recién solicitado y desembolsado"},
            {"id": 2, "code": "CL-00002", "name": "Valentina Ospina", "cc": "1020485912", "city": "Medellín", "behavior": "blanco_nuevo", "loan_amt": 500, "cuotas": 6, "desc": "Solicitud nueva vigente sin vencimientos"},
            {"id": 3, "code": "CL-00003", "name": "Carlos Eduardo Silva", "cc": "1032847193", "city": "Cali", "behavior": "blanco_nuevo", "loan_amt": 200, "cuotas": 4, "desc": "Nuevo cliente a la espera del primer corte"},
            {"id": 4, "code": "CL-00004", "name": "Camila Andrea Rojas", "cc": "1045928374", "city": "Barranquilla", "behavior": "blanco_paz_salvo", "loan_amt": 400, "cuotas": 4, "desc": "Pagó todas las cuotas (Paz y salvo)"},
            {"id": 5, "code": "CL-00005", "name": "Julián David Castro", "cc": "1056718290", "city": "Bucaramanga", "behavior": "blanco_paz_salvo", "loan_amt": 600, "cuotas": 6, "desc": "Crédito cancelado en su totalidad"},

            # 🟢 VERDES: Al Día con pagos
            {"id": 6, "code": "CL-00006", "name": "Daniela Gómez Pérez", "cc": "1067829102", "city": "Pereira", "behavior": "verde_solo_interes", "loan_amt": 500, "cuotas": 4, "desc": "Abona exactamente el valor de interés"},
            {"id": 7, "code": "CL-00007", "name": "Mateo Rincón Lozano", "cc": "1078930192", "city": "Manizales", "behavior": "verde_solo_interes", "loan_amt": 1000, "cuotas": 6, "desc": "Abona intereses de cuotas cumplidas al día"},
            {"id": 8, "code": "CL-00008", "name": "Sofía Elena Herrera", "cc": "1089041283", "city": "Cartagena", "behavior": "verde_solo_interes", "loan_amt": 300, "cuotas": 4, "desc": "Cliente que cubre intereses sin mora"},
            {"id": 9, "code": "CL-00009", "name": "Nicolás Torres Restrepo", "cc": "1090152374", "city": "Bogotá", "behavior": "verde_capital_interes", "loan_amt": 800, "cuotas": 6, "desc": "Abona capital e interés completo puntualmente"},
            {"id": 10, "code": "CL-00010", "name": "Mariana Cardona Vargas", "cc": "1101263465", "city": "Medellín", "behavior": "verde_capital_interes", "loan_amt": 400, "cuotas": 4, "desc": "Pagadora puntual con 2 cuotas completas"},
            {"id": 11, "code": "CL-00011", "name": "Andrés Felipe Muñoz", "cc": "1112374556", "city": "Cali", "behavior": "verde_capital_interes", "loan_amt": 1200, "cuotas": 8, "desc": "Excelente comportamiento: cuotas al día"},
            {"id": 12, "code": "CL-00012", "name": "Laura Marcela Ortiz", "cc": "1123485647", "city": "Ibagué", "behavior": "verde_capital_interes", "loan_amt": 300, "cuotas": 4, "desc": "Abona cuota completa de capital e interés"},

            # 🟠 NARANJAS: Mora reciente (1 a 14 días)
            {"id": 13, "code": "CL-00013", "name": "Santiago Duque Marín", "cc": "1134596738", "city": "Villavicencio", "behavior": "naranja_mora_leve", "mora_dias": 3, "loan_amt": 400, "cuotas": 4, "desc": "Atraso leve de 3 días en cuota actual"},
            {"id": 14, "code": "CL-00014", "name": "Paula Andrea Caicedo", "cc": "1145607829", "city": "Santa Marta", "behavior": "naranja_mora_leve", "mora_dias": 4, "loan_amt": 600, "cuotas": 6, "desc": "Mora de 4 días en cuota pendiente"},
            {"id": 15, "code": "CL-00015", "name": "Juan Pablo Cárdenas", "cc": "1156718910", "city": "Cúcuta", "behavior": "naranja_mora_moderada", "mora_dias": 8, "loan_amt": 500, "cuotas": 4, "desc": "Mora moderada de 8 días"},
            {"id": 16, "code": "CL-00016", "name": "Isabella Méndez Rios", "cc": "1167829001", "city": "Pasto", "behavior": "naranja_mora_moderada", "mora_dias": 12, "loan_amt": 700, "cuotas": 6, "desc": "Mora de 12 días (a punto de quincena)"},

            # 🔴 ROJOS: Mora crítica (>= 15 días)
            {"id": 17, "code": "CL-00017", "name": "Cristian Camilo Parra", "cc": "1178930192", "city": "Neiva", "behavior": "rojo_mora_quincena", "mora_dias": 16, "loan_amt": 500, "cuotas": 4, "desc": "Mora crítica de 16 días (acumula quincena)"},
            {"id": 18, "code": "CL-00018", "name": "Diana Carolina Betancourt", "cc": "1189041283", "city": "Armenia", "behavior": "rojo_mora_quincena", "mora_dias": 22, "loan_amt": 800, "cuotas": 6, "desc": "Mora crítica de 22 días con 2 cuotas vencidas"},
            {"id": 19, "code": "CL-00019", "name": "Gabriel Eduardo Suárez", "cc": "1190152374", "city": "Montería", "behavior": "rojo_mora_severa", "mora_dias": 35, "loan_amt": 1000, "cuotas": 6, "desc": "Mora severa de 35 días sin respuesta"},
            {"id": 20, "code": "CL-00020", "name": "Vanessa Tatiana Salazar", "cc": "1201263465", "city": "Popayán", "behavior": "rojo_mora_severa", "mora_dias": 50, "loan_amt": 1500, "cuotas": 8, "desc": "Mora severa de 50 días (cartera castigada)"},
        ]

        payment_counter = 1

        for item in dataset:
            parts = item["name"].split()
            first_name = parts[0]
            last_name = " ".join(parts[1:])

            client = Client(
                code=item["code"],
                portfolio_id=portfolio.id,
                first_name=first_name,
                last_name=last_name,
                identification_type="CC",
                identification_number=item["cc"],
                city=item["city"],
                address=f"Calle {item['id']*3} # {item['id']*2}-10",
                phone=f"300{item['id']:07d}",
                email=f"{first_name.lower()}.{item['id']}@gmail.com",
                job_title="Comerciante / Empleado",
                employer_name=f"Empresa Comercial {item['city']}",
                salary=Decimal("1200.00"),
                bank_name="Bancolombia",
                account_type="Ahorros",
                account_number=f"987-{item['id']:06d}-2",
                account_holder=item["name"],
                referred_to_advisor=(item["behavior"].startswith("rojo"))
            )
            db.session.add(client)
            db.session.flush()

            # Añadir 2 referencias por cliente
            ref1 = Reference(
                client_id=client.id,
                full_name=f"Referencia 1 de {first_name}",
                relationship="Familiar",
                identification_number=f"70{item['id']:06d}",
                phone=f"310{item['id']:07d}",
                address=f"Carrera {item['id']*2} # 10-20"
            )
            ref2 = Reference(
                client_id=client.id,
                full_name=f"Referencia 2 de {first_name}",
                relationship="Comercial",
                identification_number=f"80{item['id']:06d}",
                phone=f"320{item['id']:07d}",
                address=f"Avenida {item['id']*2} # 5-15"
            )
            db.session.add_all([ref1, ref2])
            db.session.flush()

            # Crear préstamo
            behavior = item["behavior"]
            loan_code = f"CR-{item['id']:05d}"
            principal = Decimal(str(item["loan_amt"]))
            cuotas_count = item["cuotas"]

            # Determinar fecha de inicio del crédito según el escenario
            if behavior == "blanco_nuevo":
                start_date = today - timedelta(days=2)
            elif behavior == "blanco_paz_salvo":
                start_date = today - timedelta(days=cuotas_count * 15 + 10)
            elif "verde" in behavior:
                start_date = today - timedelta(days=30)
            elif "naranja" in behavior:
                mora_dias = item.get("mora_dias", 5)
                start_date = today - timedelta(days=15 + mora_dias)
            else: # rojo
                mora_dias = item.get("mora_dias", 20)
                start_date = today - timedelta(days=30 + mora_dias)

            loan = Loan(
                code=loan_code,
                portfolio_id=portfolio.id,
                client_id=client.id,
                principal=principal,
                annual_rate=Decimal("0.20"), # 20%
                installments_count=cuotas_count,
                frequency_days=15,
                frequency_type="quincenal",
                biweekly_cycle="15-30",
                start_date=start_date,
                status="activo"
            )
            db.session.add(loan)
            db.session.flush()

            # Generar obligaciones quincenales
            obligations = generate_obligations(loan)
            for ob in obligations:
                db.session.add(ob)
            db.session.flush()

            # Aplicar pagos y comportamientos específicos
            if behavior == "blanco_nuevo":
                # Crédito nuevo: Todas las cuotas a futuro
                for idx, ob in enumerate(obligations):
                    ob.due_date = today + timedelta(days=15 * (idx + 1))
                db.session.flush()

            elif behavior == "blanco_paz_salvo":
                # Pagó todo el crédito completamente
                for idx, ob in enumerate(obligations):
                    pay_date = start_date + timedelta(days=15 * (idx + 1))
                    ob.due_date = pay_date
                    payment = Payment(
                        code=f"PAG-{payment_counter:05d}",
                        client_id=client.id,
                        loan_id=loan.id,
                        amount=ob.scheduled_value,
                        payment_date=pay_date,
                        registered_by=operator.id,
                        concept=f"Pago total cuota #{ob.number} (Paz y Salvo)",
                        status="aplicado"
                    )
                    payment_counter += 1
                    db.session.add(payment)
                    db.session.flush()
                    apply_payment(payment)
                loan.status = "pagado"
                db.session.flush()

            elif behavior == "verde_solo_interes":
                # Solo abona interés: cuota 1 y 2 vencidas antes de hoy se cubre el interés exacto
                for idx, ob in enumerate(obligations):
                    if idx < 2:
                        ob.due_date = today - timedelta(days=15 * (2 - idx))
                        interes_val = ob.interest
                        payment = Payment(
                            code=f"PAG-{payment_counter:05d}",
                            client_id=client.id,
                            loan_id=loan.id,
                            amount=interes_val,
                            payment_date=ob.due_date,
                            registered_by=operator.id,
                            concept=f"Abono únicamente a Interés Cuota #{ob.number}",
                            status="aplicado"
                        )
                        payment_counter += 1
                        db.session.add(payment)
                        db.session.flush()
                        apply_payment(payment)
                    else:
                        # Cuotas restantes a futuro
                        ob.due_date = today + timedelta(days=15 * (idx - 1))
                db.session.flush()

            elif behavior == "verde_capital_interes":
                # Abona cuota completa a capital e interés puntual
                for idx, ob in enumerate(obligations):
                    if idx < 2:
                        ob.due_date = today - timedelta(days=15 * (2 - idx))
                        payment = Payment(
                            code=f"PAG-{payment_counter:05d}",
                            client_id=client.id,
                            loan_id=loan.id,
                            amount=ob.scheduled_value,
                            payment_date=ob.due_date,
                            registered_by=operator.id,
                            concept=f"Abono completo Capital + Interés Cuota #{ob.number}",
                            status="aplicado"
                        )
                        payment_counter += 1
                        db.session.add(payment)
                        db.session.flush()
                        apply_payment(payment)
                    else:
                        ob.due_date = today + timedelta(days=15 * (idx - 1))
                db.session.flush()

            elif "naranja" in behavior:
                # Mora reciente 1 a 14 días
                mora_dias = item.get("mora_dias", 5)
                # Cuota 1 venció hace mora_dias
                obligations[0].due_date = today - timedelta(days=mora_dias)
                for idx in range(1, len(obligations)):
                    obligations[idx].due_date = today + timedelta(days=15 * idx)
                loan.status = "mora"
                db.session.flush()

            elif "rojo" in behavior:
                # Mora crítica >= 15 días
                mora_dias = item.get("mora_dias", 20)
                obligations[0].due_date = today - timedelta(days=mora_dias)
                if len(obligations) > 1 and mora_dias >= 30:
                    obligations[1].due_date = today - timedelta(days=mora_dias - 15)
                    for idx in range(2, len(obligations)):
                        obligations[idx].due_date = today + timedelta(days=15 * (idx - 1))
                else:
                    for idx in range(1, len(obligations)):
                        obligations[idx].due_date = today + timedelta(days=15 * idx)
                loan.status = "mora"
                db.session.flush()

        db.session.commit()
        print("\n" + "=" * 65)
        print("  BASE DE DATOS CARGADA EXITOSAMENTE (20 CLIENTES)")
        print("=" * 65)
        print("  ⚪ Blancos  (Solicitud / Paz y Salvo):   5 clientes (CL-00001 a CL-00005)")
        print("  🟢 Verdes   (Al Día con Pagos):          7 clientes (CL-00006 a CL-00012)")
        print("     └─ 3 abonando solo a interés")
        print("     └─ 4 abonando capital + interés")
        print("  🟠 Naranjas (En Mora 1 a 14 días):       4 clientes (CL-00013 a CL-00016)")
        print("  🔴 Rojos    (Mora Crítica >= 15 días):   4 clientes (CL-00017 a CL-00020)")
        print("=" * 65)
        print("  Total Clientes:    ", Client.query.count())
        print("  Total Préstamos:   ", Loan.query.count())
        print("  Total Obligaciones:", Obligation.query.count())
        print("  Total Pagos:       ", Payment.query.count())
        print("=" * 65)
        print("\n✨ ¡Listo para analizar en http://localhost:5000/reportes/score !")


if __name__ == "__main__":
    seed_20_clients()
