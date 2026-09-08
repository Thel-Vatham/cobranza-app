import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Client, Loan, Obligation, Payment, Parameter
from app.services.financial import (
    calculate_schedule,
    get_next_biweekly_dates,
    suggest_biweekly_cycle,
    generate_obligations,
    apply_payment,
)


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    AUTH_DISABLED = True
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class NewBusinessModelTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_parameters_defaults_usd_and_rate(self):
        """Verifica parámetros de tasa fija 20% y montos predefinidos en USD."""
        rate = Parameter.get_float("tasa_interes_periodo")
        self.assertEqual(rate, 20.0)

        montos = Parameter.get("montos_prestamo_disponibles")
        self.assertIsNotNone(montos)
        montos_list = [m.strip() for m in montos.split(",")]
        self.assertIn("75", montos_list)
        self.assertIn("100", montos_list)
        self.assertIn("125", montos_list)
        self.assertIn("150", montos_list)

    def test_weekly_schedule_generation(self):
        """Verifica que los préstamos semanales vencen exactamente cada 7 días."""
        start = date(2026, 9, 2)  # Miércoles
        # Préstamo de 100 USD con tasa 20% fija
        sched = calculate_schedule(
            principal=100,
            annual_rate=0.20,
            installments_count=2,
            start_date=start,
            frequency_type="semanal",
        )
        self.assertEqual(len(sched), 2)
        # Cuota 1 a los 7 días (9 de Septiembre)
        self.assertEqual(sched[0]["due_date"], date(2026, 9, 9))
        # Cuota 2 a los 14 días (16 de Septiembre)
        self.assertEqual(sched[1]["due_date"], date(2026, 9, 16))

        # Cuota fija francesa de 100 USD a 2 semanas con 20%
        # total pagado cubre interés y capital
        total_cap = sum(x["capital"] for x in sched)
        self.assertEqual(total_cap, Decimal("100.00"))

    def test_biweekly_cycle_cuts(self):
        """Verifica los 3 ciclos de corte quincenal (5-20, 10-25, 15-30)."""
        start = date(2026, 9, 1)

        # Ciclo 5-20
        cuts_5_20 = get_next_biweekly_dates(start, "5-20", 3)
        self.assertEqual(cuts_5_20[0], date(2026, 9, 5))
        self.assertEqual(cuts_5_20[1], date(2026, 9, 20))
        self.assertEqual(cuts_5_20[2], date(2026, 10, 5))

        # Ciclo 10-25
        cuts_10_25 = get_next_biweekly_dates(start, "10-25", 3)
        self.assertEqual(cuts_10_25[0], date(2026, 9, 10))
        self.assertEqual(cuts_10_25[1], date(2026, 9, 25))
        self.assertEqual(cuts_10_25[2], date(2026, 10, 10))

        # Ciclo 15-30
        cuts_15_30 = get_next_biweekly_dates(start, "15-30", 3)
        self.assertEqual(cuts_15_30[0], date(2026, 9, 15))
        self.assertEqual(cuts_15_30[1], date(2026, 9, 30))
        self.assertEqual(cuts_15_30[2], date(2026, 10, 15))

    def test_suggest_biweekly_cycle(self):
        """Verifica la asignación inteligente de ciclo según el día de la solicitud."""
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 3)), "5-20")
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 8)), "10-25")
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 14)), "15-30")
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 18)), "5-20")
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 23)), "10-25")
        self.assertEqual(suggest_biweekly_cycle(date(2026, 9, 29)), "15-30")

    def test_single_bullet_payment_waterfall(self):
        """Verifica la lógica de pago de 1 cuota: 100 USD + 20% = 120 USD.
        Prioridad 1: Interés 20 USD.
        Prioridad 2: Capital remanente."""
        cli = Client(code="CL-TEST-01", first_name="Carlos", last_name="Mora", identification_type="CC", identification_number="998877")
        db.session.add(cli)
        db.session.commit()

        loan = Loan(
            code="PR-TEST-01",
            client_id=cli.id,
            principal=Decimal("100.00"),
            annual_rate=Decimal("0.20"),
            installments_count=1,
            frequency_days=7,
            frequency_type="semanal",
            start_date=date(2026, 9, 1),
            status="activo",
        )
        db.session.add(loan)
        db.session.flush()

        for ob in generate_obligations(loan):
            db.session.add(ob)
        db.session.commit()

        self.assertEqual(len(loan.obligations), 1)
        ob = loan.obligations[0]
        self.assertEqual(ob.capital, Decimal("100.00"))
        self.assertEqual(ob.interest, Decimal("20.00"))
        self.assertEqual(ob.scheduled_value, Decimal("120.00"))

        # Caso A: Pago parcial de 50 USD
        pay1 = Payment(
            code="PG-TEST-01",
            client_id=cli.id,
            loan_id=loan.id,
            amount=Decimal("50.00"),
            payment_date=date(2026, 9, 8),
            status="aplicado",
        )
        db.session.add(pay1)
        db.session.flush()
        apps = apply_payment(pay1)
        db.session.commit()

        # El interés de 20 USD se cubrió al 100%
        self.assertEqual(ob.pending_interest, Decimal("0.00"))
        # El excedente (30 USD) fue a capital: 100 - 30 = 70 USD
        self.assertEqual(ob.pending_capital, Decimal("70.00"))
        self.assertEqual(ob.status, "parcial")
        self.assertEqual(loan.status, "activo")

        # Caso B: Pago restante de 70 USD para liquidar capital insoluto
        pay2 = Payment(
            code="PG-TEST-02",
            client_id=cli.id,
            loan_id=loan.id,
            amount=Decimal("70.00"),
            payment_date=date(2026, 9, 8),
            status="aplicado",
        )
        db.session.add(pay2)
        db.session.flush()
        apply_payment(pay2)
        db.session.commit()

        self.assertEqual(ob.pending_capital, Decimal("0.00"))
        self.assertEqual(ob.status, "pagada")
        self.assertEqual(loan.status, "pagado")

    def test_routes_filtering_loans_and_collections(self):
        """Verifica los filtros por modalidad, ciclo quincenal y monto en endpoints."""
        cli = Client(code="CL-TEST-02", first_name="Diana", last_name="Ríos", identification_type="CC", identification_number="112233")
        db.session.add(cli)
        db.session.commit()

        # Préstamo 1: Semanal, 75 USD
        l1 = Loan(
            code="PR-SEM-75",
            client_id=cli.id,
            principal=Decimal("75.00"),
            annual_rate=Decimal("0.20"),
            installments_count=1,
            frequency_days=7,
            frequency_type="semanal",
            start_date=date(2026, 8, 1),
            status="activo",
        )
        # Préstamo 2: Quincenal 10-25, 150 USD
        l2 = Loan(
            code="PR-QUI-150",
            client_id=cli.id,
            principal=Decimal("150.00"),
            annual_rate=Decimal("0.20"),
            installments_count=1,
            frequency_days=15,
            frequency_type="quincenal",
            biweekly_cycle="10-25",
            start_date=date(2026, 8, 10),
            status="activo",
        )
        db.session.add_all([l1, l2])
        db.session.flush()
        for ob in generate_obligations(l1):
            db.session.add(ob)
        for ob in generate_obligations(l2):
            db.session.add(ob)
        db.session.commit()

        # Test filtro de préstamos por modalidad semanal
        resp = self.client.get("/prestamos/?freq=semanal")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("PR-SEM-75", html)
        self.assertNotIn("PR-QUI-150", html)

        # Test filtro por ciclo quincenal 10-25
        resp2 = self.client.get("/prestamos/?cycle=10-25")
        self.assertEqual(resp2.status_code, 200)
        html2 = resp2.get_data(as_text=True)
        self.assertIn("PR-QUI-150", html2)
        self.assertNotIn("PR-SEM-75", html2)

        # Test filtro de cobranza por timing vencidas
        resp3 = self.client.get("/cobranza/?timing=vencidas")
        self.assertEqual(resp3.status_code, 200)
        html3 = resp3.get_data(as_text=True)
        self.assertIn("PR-SEM-75", html3)

    def test_simplified_parameters_and_scoring(self):
        """Verifica que se hayan eliminado parámetros obsoletos y que el score use 3 parámetros intuitivos."""
        from app.services.scoring import compute_score

        # 1. Verificar que los parámetros eliminados no existen
        obsolete_keys = [
            "orden_aplicacion_pago",
            "tasa_mora_diaria",
            "dias_proximos_vencer",
            "dias_alerta_mora",
            "peso_puntualidad",
            "peso_cumplimiento",
            "peso_mora",
            "umbral_score_regular",
        ]
        for key in obsolete_keys:
            self.assertIsNone(Parameter.query.filter_by(key=key).first(), f"Clave obsoleta encontrada: {key}")

        # 2. Verificar que existen los 3 parámetros de score intuitivos
        score_keys = ["umbral_score_excelente", "umbral_score_bueno", "dias_max_mora_score"]
        for key in score_keys:
            self.assertIsNotNone(Parameter.query.filter_by(key=key).first(), f"Clave requerida no encontrada: {key}")

        # 3. Validar cálculo del score
        cli = Client(
            code="CL-TEST-SCORE",
            first_name="Score",
            last_name="Tester",
            identification_number="99887766",
        )
        db.session.add(cli)
        db.session.flush()

        loan = Loan(
            code="PR-SCORE-1",
            client_id=cli.id,
            principal=Decimal("100.00"),
            annual_rate=Decimal("0.20"),
            installments_count=2,
            frequency_days=7,
            frequency_type="semanal",
            start_date=date(2026, 8, 1),
            status="activo",
        )
        db.session.add(loan)
        db.session.flush()

        # Generar 2 obligaciones pagadas a tiempo
        ob1 = Obligation(
            loan_id=loan.id,
            number=1,
            due_date=date(2026, 8, 8),
            scheduled_value=Decimal("60.00"),
            capital=Decimal("50.00"),
            interest=Decimal("10.00"),
            pending_capital=Decimal("0.00"),
            pending_interest=Decimal("0.00"),
            paid_date=date(2026, 8, 7),
            status="pagada",
        )
        ob2 = Obligation(
            loan_id=loan.id,
            number=2,
            due_date=date(2026, 8, 15),
            scheduled_value=Decimal("60.00"),
            capital=Decimal("50.00"),
            interest=Decimal("10.00"),
            pending_capital=Decimal("0.00"),
            pending_interest=Decimal("0.00"),
            paid_date=date(2026, 8, 14),
            status="pagada",
        )
        db.session.add_all([ob1, ob2])
        db.session.commit()

        res = compute_score(cli)
        self.assertEqual(res["score"], 100)
        self.assertEqual(res["band"], "Excelente")


if __name__ == "__main__":
    unittest.main()
