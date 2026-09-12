"""
Script generador de base de datos de 20 clientes:
- Todos los préstamos son A UNA SOLA CUOTA (installments_count = 1).
- Distribuidos en TODOS LOS CICLOS QUINCENALES ('5-20', '10-25', '15-30').
- Simula todos los comportamientos:
    ⚪ BLANCOS:
        1-3: Solicitud / crédito recién creado a 1 cuota, vigente sin vencimiento.
        4-5: Pagó el crédito a 1 cuota completo (capital + interés) -> Vuelve a BLANCO (Paz y Salvo).
    🟢 VERDES:
        6-8: Abonó solo a interés antes o al corte -> Sigue al día (VERDE).
        9-12: Abonó cuota o abono mixto a capital e interés antes del corte -> Al día (VERDE).
    🟠 NARANJAS:
        13-16: Mora reciente de 1 a 14 días en su única cuota (distribuidos en ciclos 5-20, 10-25, 15-30).
    🔴 ROJOS:
        17-20: Mora crítica de >= 15 días (quincena o más acumulada) en su cuota (en ciclos 5-20, 10-25, 15-30).
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
from app.services.financial import generate_obligations, apply_payment


def seed_20_clients_single_installment():
    app = create_app()
    with app.app_context():
        print("\n🧹 LIMPIANDO Y GENERANDO NUEVA BASE DE DATOS A 1 SOLA CUOTA...")

        # 1. Purgar datos existentes de clientes, préstamos y pagos
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        Loan.query.delete()
        Reference.query.delete()
        Client.query.delete()
        db.session.commit()

        # 2. Cartera activa y operador
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

        # 20 clientes distribuidos en ciclos quincenales (5-20, 10-25, 15-30)
        # Todos con 1 sola cuota
        dataset = [
            # ⚪ BLANCOS: Nuevos o Paz y Salvo
            {"id": 1, "code": "CL-00001", "name": "Alejandro Morales", "cc": "1018475891", "city": "Bogotá", "cycle": "5-20", "behavior": "blanco_nuevo", "loan_amt": 300, "desc": "Crédito a 1 cuota recién solicitado (Corte 5-20)"},
            {"id": 2, "code": "CL-00002", "name": "Valentina Ospina", "cc": "1020485912", "city": "Medellín", "cycle": "10-25", "behavior": "blanco_nuevo", "loan_amt": 500, "desc": "Crédito a 1 cuota vigente sin vencimiento (Corte 10-25)"},
            {"id": 3, "code": "CL-00003", "name": "Carlos Eduardo Silva", "cc": "1032847193", "city": "Cali", "cycle": "15-30", "behavior": "blanco_nuevo", "loan_amt": 200, "desc": "Solicitud nueva a 1 cuota a futuro (Corte 15-30)"},
            {"id": 4, "code": "CL-00004", "name": "Camila Andrea Rojas", "cc": "1045928374", "city": "Barranquilla", "cycle": "5-20", "behavior": "blanco_paz_salvo", "loan_amt": 400, "desc": "Pagó su cuota única total -> Queda en Paz y Salvo (Blanco)"},
            {"id": 5, "code": "CL-00005", "name": "Julián David Castro", "cc": "1056718290", "city": "Bucaramanga", "cycle": "10-25", "behavior": "blanco_paz_salvo", "loan_amt": 600, "desc": "Canceló la totalidad de su préstamo -> Paz y Salvo (Blanco)"},

            # 🟢 VERDES: Al Día con pagos (unos solo a interés, otros a capital e interés)
            {"id": 6, "code": "CL-00006", "name": "Daniela Gómez Pérez", "cc": "1067829102", "city": "Pereira", "cycle": "5-20", "behavior": "verde_solo_interes", "loan_amt": 500, "desc": "Abonó solo a Interés ($100 USD), capital diferido al día"},
            {"id": 7, "code": "CL-00007", "name": "Mateo Rincón Lozano", "cc": "1078930192", "city": "Manizales", "cycle": "10-25", "behavior": "verde_solo_interes", "loan_amt": 1000, "desc": "Abonó solo el valor de Interés ($200 USD), sin mora"},
            {"id": 8, "code": "CL-00008", "name": "Sofía Elena Herrera", "cc": "1089041283", "city": "Cartagena", "cycle": "15-30", "behavior": "verde_solo_interes", "loan_amt": 300, "desc": "Abonó intereses pactados ($60 USD) manteniendo crédito activo"},
            {"id": 9, "code": "CL-00009", "name": "Nicolás Torres Restrepo", "cc": "1090152374", "city": "Bogotá", "cycle": "5-20", "behavior": "verde_capital_interes", "loan_amt": 800, "desc": "Abonó parte de capital e interés ($500 USD), al día"},
            {"id": 10, "code": "CL-00010", "name": "Mariana Cardona Vargas", "cc": "1101263465", "city": "Medellín", "cycle": "10-25", "behavior": "verde_capital_interes", "loan_amt": 400, "desc": "Abonó el 50% de la cuota total a tiempo ($240 USD)"},
            {"id": 11, "code": "CL-00011", "name": "Andrés Felipe Muñoz", "cc": "1112374556", "city": "Cali", "cycle": "15-30", "behavior": "verde_capital_interes", "loan_amt": 1200, "desc": "Abono fuerte de capital + interés ($800 USD), crédito al día"},
            {"id": 12, "code": "CL-00012", "name": "Laura Marcela Ortiz", "cc": "1123485647", "city": "Ibagué", "cycle": "5-20", "behavior": "verde_capital_interes", "loan_amt": 350, "desc": "Abono puntual al día"},

            # 🟠 NARANJAS: En Mora reciente (1 a 14 días)
            {"id": 13, "code": "CL-00013", "name": "Santiago Duque Marín", "cc": "1134596738", "city": "Villavicencio", "cycle": "5-20", "behavior": "naranja_mora", "mora_dias": 2, "loan_amt": 400, "desc": "Mora reciente de 2 días en corte 5-20"},
            {"id": 14, "code": "CL-00014", "name": "Paula Andrea Caicedo", "cc": "1145607829", "city": "Santa Marta", "cycle": "10-25", "behavior": "naranja_mora", "mora_dias": 5, "loan_amt": 600, "desc": "Mora de 5 días en corte 10-25"},
            {"id": 15, "code": "CL-00015", "name": "Juan Pablo Cárdenas", "cc": "1156718910", "city": "Cúcuta", "cycle": "15-30", "behavior": "naranja_mora", "mora_dias": 9, "loan_amt": 500, "desc": "Mora de 9 días en corte 15-30"},
            {"id": 16, "code": "CL-00016", "name": "Isabella Méndez Rios", "cc": "1167829001", "city": "Pasto", "cycle": "10-25", "behavior": "naranja_mora", "mora_dias": 13, "loan_amt": 700, "desc": "Mora de 13 días (casi la quincena)"},

            # 🔴 ROJOS: Mora crítica (>= 15 días acumulados)
            {"id": 17, "code": "CL-00017", "name": "Cristian Camilo Parra", "cc": "1178930192", "city": "Neiva", "cycle": "5-20", "behavior": "rojo_mora", "mora_dias": 16, "loan_amt": 500, "desc": "Acumuló 1 quincena de mora (16 días de atraso)"},
            {"id": 18, "code": "CL-00018", "name": "Diana Carolina Betancourt", "cc": "1189041283", "city": "Armenia", "cycle": "10-25", "behavior": "rojo_mora", "mora_dias": 22, "loan_amt": 800, "desc": "Mora crítica de 22 días de retraso en corte 10-25"},
            {"id": 19, "code": "CL-00019", "name": "Gabriel Eduardo Suárez", "cc": "1190152374", "city": "Montería", "cycle": "15-30", "behavior": "rojo_mora", "mora_dias": 32, "loan_amt": 1000, "desc": "Mora de más de 1 mes (32 días de retraso en corte 15-30)"},
            {"id": 20, "code": "CL-00020", "name": "Vanessa Tatiana Salazar", "cc": "1201263465", "city": "Popayán", "cycle": "5-20", "behavior": "rojo_mora", "mora_dias": 45, "loan_amt": 1500, "desc": "Mora crítica de 45 días sin abonos"},
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
                employer_name=f"Comercio {item['city']}",
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
                full_name=f"Referencia Familiar de {first_name}",
                relationship="Familiar",
                identification_number=f"70{item['id']:06d}",
                phone=f"310{item['id']:07d}",
                address=f"Carrera {item['id']*2} # 10-20"
            )
            ref2 = Reference(
                client_id=client.id,
                full_name=f"Referencia Comercial de {first_name}",
                relationship="Comercial",
                identification_number=f"80{item['id']:06d}",
                phone=f"320{item['id']:07d}",
                address=f"Avenida {item['id']*2} # 5-15"
            )
            db.session.add_all([ref1, ref2])
            db.session.flush()

            # Parámetros del crédito: 1 SOLA CUOTA, ciclo quincenal específico
            behavior = item["behavior"]
            loan_code = f"CR-{item['id']:05d}"
            principal = Decimal(str(item["loan_amt"]))
            cycle = item["cycle"]

            # Fecha de inicio según escenario
            if behavior == "blanco_nuevo":
                start_date = today - timedelta(days=2)
            elif behavior == "blanco_paz_salvo":
                start_date = today - timedelta(days=25)
            elif "verde" in behavior:
                start_date = today - timedelta(days=20)
            elif "naranja" in behavior:
                mora_dias = item.get("mora_dias", 5)
                start_date = today - timedelta(days=15 + mora_dias)
            else: # rojo
                mora_dias = item.get("mora_dias", 20)
                start_date = today - timedelta(days=15 + mora_dias)

            # Préstamo A 1 SOLA CUOTA
            loan = Loan(
                code=loan_code,
                portfolio_id=portfolio.id,
                client_id=client.id,
                principal=principal,
                annual_rate=Decimal("0.20"), # 20% quincenal
                installments_count=1,        # <--- EXACTAMENTE 1 CUOTA
                frequency_days=15,
                frequency_type="quincenal",
                biweekly_cycle=cycle,
                start_date=start_date,
                status="activo"
            )
            db.session.add(loan)
            db.session.flush()

            # Generar obligación (1 sola cuota)
            obligations = generate_obligations(loan)
            ob = obligations[0]
            db.session.add(ob)
            db.session.flush()

            # Simulación de comportamientos
            if behavior == "blanco_nuevo":
                # Crédito a 1 cuota recién desembolsado con vencimiento a futuro
                ob.due_date = today + timedelta(days=12)
                loan.status = "activo"
                db.session.flush()

            elif behavior == "blanco_paz_salvo":
                # Pagó el 100% de su única cuota (Capital + Interés) -> Vuelve a BLANCO (Paz y Salvo)
                ob.due_date = start_date + timedelta(days=15)
                payment = Payment(
                    code=f"PAG-{payment_counter:05d}",
                    client_id=client.id,
                    loan_id=loan.id,
                    amount=ob.scheduled_value,
                    payment_date=ob.due_date,
                    registered_by=operator.id,
                    concept=f"Cancelación total de crédito a 1 cuota (Paz y Salvo)",
                    status="aplicado"
                )
                payment_counter += 1
                db.session.add(payment)
                db.session.flush()
                apply_payment(payment)
                loan.status = "pagado"
                db.session.flush()

            elif behavior == "verde_solo_interes":
                # Abona ÚNICAMENTE al valor de interés ($100, $200 o $60 USD)
                # La cuota 1 se liquida y se genera automáticamente la cuota 2 para la siguiente quincena
                # con el saldo de capital + interés sobre el crédito total original.
                ob.due_date = today - timedelta(days=2)
                interes_monto = ob.interest
                payment = Payment(
                    code=f"PAG-{payment_counter:05d}",
                    client_id=client.id,
                    loan_id=loan.id,
                    amount=interes_monto,
                    payment_date=today - timedelta(days=2),
                    registered_by=operator.id,
                    concept=f"Abono únicamente a Interés (${interes_monto} USD)",
                    status="aplicado"
                )
                payment_counter += 1
                db.session.add(payment)
                db.session.flush()
                apply_payment(payment)
                db.session.flush()

            elif behavior == "verde_capital_interes":
                # Abona a capital e interés parcial (ej: cubre interés y parte de capital)
                # Se genera la cuota 2 para la siguiente quincena: saldo restante + interés del crédito total.
                ob.due_date = today - timedelta(days=3)
                abono_monto = Decimal(str(round(float(ob.scheduled_value) * 0.6, 2)))
                payment = Payment(
                    code=f"PAG-{payment_counter:05d}",
                    client_id=client.id,
                    loan_id=loan.id,
                    amount=abono_monto,
                    payment_date=today - timedelta(days=3),
                    registered_by=operator.id,
                    concept=f"Abono a Capital e Interés (${abono_monto} USD)",
                    status="aplicado"
                )
                payment_counter += 1
                db.session.add(payment)
                db.session.flush()
                apply_payment(payment)
                db.session.flush()

            elif behavior == "naranja_mora":
                # Mora reciente 1 a 14 días
                mora_dias = item.get("mora_dias", 4)
                ob.due_date = today - timedelta(days=mora_dias)
                loan.status = "mora"
                db.session.flush()

            elif behavior == "rojo_mora":
                # Mora crítica >= 15 días (quincena acumulada o más)
                mora_dias = item.get("mora_dias", 20)
                ob.due_date = today - timedelta(days=mora_dias)
                loan.status = "mora"
                db.session.flush()

        db.session.commit()
        print("\n" + "=" * 65)
        print("  BASE DE DATOS GENERADA A 1 SOLA CUOTA Y QUINCENAS VARIADAS")
        print("=" * 65)
        print("  • Cuotas por préstamo: EXACTAMENTE 1 CUOTA en todos los créditos")
        print("  • Cortes quincenales:  Distribuidos en 5-20, 10-25 y 15-30")
        print("  • Estados semáforo:")
        print("     ⚪ Blancos  (Solicitud / Paz y Salvo):  5 clientes")
        print("     🟢 Verdes   (Al Día / Con Pagos):       7 clientes")
        print("        └─ 3 abonando SOLO a Interés")
        print("        └─ 4 abonando Capital + Interés")
        print("     🟠 Naranjas (Mora 1 a 14 días):        4 clientes")
        print("     🔴 Rojos    (Mora >= 15 días):          4 clientes")
        print("=" * 65)
        print("  Total Clientes:    ", Client.query.count())
        print("  Total Préstamos:   ", Loan.query.count())
        print("  Total Obligaciones:", Obligation.query.count(), "(1 por crédito)")
        print("  Total Pagos:       ", Payment.query.count())
        print("=" * 65)


if __name__ == "__main__":
    seed_20_clients_single_installment()
