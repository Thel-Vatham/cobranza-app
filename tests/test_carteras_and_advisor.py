"""Pruebas automatizadas para el módulo de Carteras (Portfolios) y el rol de Asesor / Consultor.

Ejecutar con:
    .venv\\Scripts\\python -m unittest tests.test_carteras_and_advisor -v
"""
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import (Client, ClientReferral, Loan, Notification,
                        Obligation, Parameter, Portfolio, Role, User)
from app.services.financial import calculate_schedule


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test_portfolios.db")
    UPLOAD_FOLDER = tempfile.mkdtemp()
    WTF_CSRF_ENABLED = False


class TestCarterasAndAdvisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()

    def login(self, username, password="09300"):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

    def test_01_portfolio_creation_and_isolation(self):
        """Verifica la creación de carteras por admin y el aislamiento de datos entre ellas."""
        with self.app.app_context():
            # Iniciar sesión como administrador
            self.login("admin")

            # 1. Crear Cartera Norte asignada a user_0 con $1,000 USD
            user_0 = User.query.filter_by(username="user_0").first()
            self.assertIsNotNone(user_0)

            resp = self.client.post("/carteras/nueva", data={
                "name": "Cartera Norte USD",
                "code": "CART-NORTE",
                "assigned_capital_usd": "1000.00",
                "user_id": user_0.id,
                "description": "Cartera de prueba sector norte",
                "status": "activa",
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            p_norte = Portfolio.query.filter_by(code="CART-NORTE").first()
            self.assertIsNotNone(p_norte)
            self.assertEqual(float(p_norte.assigned_capital_usd), 1000.0)
            self.assertEqual(p_norte.user_id, user_0.id)

            # 2. Crear Cartera Sur asignada a admin con $2,000 USD
            resp = self.client.post("/carteras/nueva", data={
                "name": "Cartera Sur USD",
                "code": "CART-SUR",
                "assigned_capital_usd": "2000.00",
                "user_id": 1,
                "description": "Cartera de prueba sector sur",
                "status": "activa",
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            p_sur = Portfolio.query.filter_by(code="CART-SUR").first()
            self.assertIsNotNone(p_sur)

            # 3. Crear cliente A en Cartera Norte
            resp = self.client.post("/clientes/nuevo", data={
                "first_name": "Carlos",
                "last_name": "Norte",
                "identification_number": "101010",
                "identification_type": "CC",
                "portfolio_id": p_norte.id,
                "ref_name": ["Ref 1", "Ref 2"],
                "ref_relationship": ["Amigo", "Familiar"],
                "ref_identification": ["111", "222"],
                "ref_phone": ["3001", "3002"],
                "ref_address": ["", ""],
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            # 4. Crear cliente B en Cartera Sur
            resp = self.client.post("/clientes/nuevo", data={
                "first_name": "Diana",
                "last_name": "Sur",
                "identification_number": "202020",
                "identification_type": "CC",
                "portfolio_id": p_sur.id,
                "ref_name": ["Ref 3", "Ref 4"],
                "ref_relationship": ["Amigo", "Familiar"],
                "ref_identification": ["333", "444"],
                "ref_phone": ["3003", "3004"],
                "ref_address": ["", ""],
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            client_norte = Client.query.filter_by(identification_number="101010").first()
            client_sur = Client.query.filter_by(identification_number="202020").first()
            self.assertEqual(client_norte.portfolio_id, p_norte.id)
            self.assertEqual(client_sur.portfolio_id, p_sur.id)

            # 5. Cerrar sesión y loguearse como user_0
            self.logout()
            self.login("user_0")

            # Activar Cartera Norte en sesión
            self.client.post(f"/carteras/alternar/{p_norte.id}", follow_redirects=True)

            # Al listar clientes como user_0 en Cartera Norte: debe aparecer Carlos Norte y NO Diana Sur
            resp_clients = self.client.get("/clientes/")
            self.assertIn(b"Carlos", resp_clients.data)
            self.assertNotIn(b"Diana", resp_clients.data)

            self.logout()

    def test_02_enviar_a_asesor_and_notification(self):
        """Verifica la acción de enviar a asesor y la creación de la notificación interna."""
        with self.app.app_context():
            self.login("admin")

            client = Client.query.filter_by(identification_number="101010").first()
            consultor = User.query.filter_by(username="consultor_0").first()
            self.assertIsNotNone(client)
            self.assertIsNotNone(consultor)

            # Enviar a asesor
            resp = self.client.post(f"/clientes/{client.id}/enviar-asesor", data={
                "advisor_id": consultor.id,
                "reason": "Cobranza Especializada / Mora",
                "notes": "Cliente con atraso en pagos para evaluar acuerdo",
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            # Verificar que el cliente quedó marcado y la remisión se registró
            client_db = Client.query.get(client.id)
            self.assertTrue(client_db.referred_to_advisor)

            referral = ClientReferral.query.filter_by(client_id=client.id).first()
            self.assertIsNotNone(referral)
            self.assertEqual(referral.advisor_id, consultor.id)
            self.assertEqual(referral.reason, "Cobranza Especializada / Mora")
            self.assertEqual(referral.status, "pendiente")

            # Verificar que se generó la notificación para el consultor
            notif = Notification.query.filter_by(user_id=consultor.id).first()
            self.assertIsNotNone(notif)
            self.assertFalse(notif.is_read)
            self.assertIn("Carlos", notif.title)

            self.logout()

    def test_03_advisor_dashboard_and_file(self):
        """Verifica que el usuario con rol Consulta accede a su dashboard con clientes y notificaciones."""
        with self.app.app_context():
            # Iniciar sesión como consultor_0
            self.login("consultor_0")

            # Al ingresar a la raíz (/), debe redirigir a /asesor
            resp_root = self.client.get("/", follow_redirects=True)
            self.assertEqual(resp_root.status_code, 200)
            self.assertIn(b"Panel de", resp_root.data)

            # Acceder directamente al dashboard de asesoría
            resp_advisor = self.client.get("/asesor/")
            self.assertEqual(resp_advisor.status_code, 200)
            self.assertIn(b"Carlos", resp_advisor.data)
            self.assertIn(b"Score", resp_advisor.data)

            # Acceder a la ficha ejecutiva del cliente
            client = Client.query.filter_by(identification_number="101010").first()
            resp_detail = self.client.get(f"/asesor/cliente/{client.id}")
            self.assertEqual(resp_detail.status_code, 200)
            self.assertIn(b"Ficha Integral de", resp_detail.data)

            # Registrar dictamen del asesor
            referral = ClientReferral.query.filter_by(client_id=client.id).first()
            resp_dictamen = self.client.post(f"/asesor/cliente/{client.id}/dictamen", data={
                "referral_id": referral.id,
                "advisor_notes": "Se recomienda refinanciar a cuotas quincenales menores.",
                "status": "revisado",
            }, follow_redirects=True)
            self.assertEqual(resp_dictamen.status_code, 200)

            ref_updated = ClientReferral.query.get(referral.id)
            self.assertEqual(ref_updated.status, "revisado")
            self.assertIn("refinanciar", ref_updated.advisor_notes)

            # Marcar notificación como leída
            notif = Notification.query.filter_by(user_id=referral.advisor_id).first()
            resp_notif = self.client.post(f"/asesor/notificaciones/{notif.id}/leer", follow_redirects=True)
            self.assertEqual(resp_notif.status_code, 200)
            notif_updated = Notification.query.get(notif.id)
            self.assertTrue(notif_updated.is_read)

            self.logout()


if __name__ == "__main__":
    unittest.main()
