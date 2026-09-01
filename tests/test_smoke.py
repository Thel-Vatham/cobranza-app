"""Prueba de humo integral del prototipo Cartera.

Ejecutar con:
    python -m unittest tests.test_smoke -v
"""
import os
import tempfile
import unittest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Client, Loan, Payment, User


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
    UPLOAD_FOLDER = tempfile.mkdtemp()
    WTF_CSRF_ENABLED = False


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()

    def login(self):
        return self.client.post(
            "/login",
            data={"username": "admin", "password": "09300"},
            follow_redirects=True,
        )

    def test_full_flow(self):
        with self.app.app_context():
            # login
            resp = self.login()
            self.assertEqual(resp.status_code, 200)

            # crear cliente
            resp = self.client.post("/clientes/nuevo", data={
                "first_name": "Juan", "last_name": "Perez",
                "identification_type": "CC", "identification_number": "12345",
                "country": "Colombia", "address": "Calle 1",
                "phone": "300", "email": "j@x.com",
                "ref_name": ["Ana Gomez"], "ref_relationship": ["Referencia"],
                "ref_identification": ["999"], "ref_phone": ["301"], "ref_address": [""],
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            client = Client.query.filter_by(identification_number="12345").first()
            self.assertIsNotNone(client)
            self.assertEqual(client.full_name, "Juan Perez")
            self.assertEqual(len(client.references), 1)

            # crear préstamo
            resp = self.client.post("/prestamos/nuevo", data={
                "client_id": client.id, "principal": "1000000",
                "annual_rate": "24", "installments_count": "12",
                "frequency_days": "30", "start_date": "2026-01-01",
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            loan = Loan.query.filter_by(client_id=client.id).first()
            self.assertIsNotNone(loan)
            self.assertEqual(len(loan.obligations), 12)
            # cuota fija (amortización francesa al 20% por período) ~ 225,264.98
            self.assertAlmostEqual(float(loan.obligations[0].scheduled_value), 225264.98, delta=1.0)

            # registrar pago
            resp = self.client.post("/pagos/nuevo", data={
                "loan_id": loan.id, "amount": "200000",
                "payment_date": "2026-01-01", "concept": "Abono",
                "receipt_number": "R1",
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            payment = Payment.query.filter_by(loan_id=loan.id).first()
            self.assertIsNotNone(payment)
            self.assertGreater(len(payment.applications), 0)
            self.assertEqual(payment.status, "aplicado")

            # el saldo debe haberse reducido tras el abono
            initial_balance = 12 * 225264.98
            self.assertLess(loan.outstanding_balance, initial_balance)

            # recibo
            resp = self.client.get(f"/pagos/{payment.id}/recibo")
            self.assertEqual(resp.status_code, 200)

            # cliente sin préstamos ni historial
            resp_c2 = self.client.post("/clientes/nuevo", data={
                "first_name": "Cliente", "last_name": "Sin Prestamos",
                "identification_type": "CC", "identification_number": "99988877",
                "country": "Colombia", "city": "Medellín",
            }, follow_redirects=True)
            self.assertEqual(resp_c2.status_code, 200)

            # panel y reportes
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/reportes/cartera").status_code, 200)
            score_resp = self.client.get("/reportes/score")
            self.assertEqual(score_resp.status_code, 200)
            self.assertIn(b"Score de Comportamiento Crediticio", score_resp.data)
            self.assertEqual(self.client.get("/admin/usuarios").status_code, 200)


if __name__ == "__main__":
    unittest.main()
