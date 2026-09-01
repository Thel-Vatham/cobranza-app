import io
import unittest
import zipfile
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Client, Loan, Obligation, Payment, User

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    AUTH_DISABLED = True
    SESSION_COOKIE_SECURE = False

class NewFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def test_dashboard_access(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_client_live_search_page(self):
        resp = self.client.get("/clientes/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="client-search"', html)
        self.assertIn('id="search-count"', html)

    def test_data_management_page(self):
        resp = self.client.get("/admin/datos")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Exportar Base de Datos", html)
        self.assertIn("Eliminar Base Actual", html)
        self.assertIn('id="delete-modal"', html)

    def test_export_csv_zip(self):
        resp = self.client.get("/admin/exportar-csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
            names = zf.namelist()
            self.assertIn("clientes.csv", names)
            self.assertIn("prestamos.csv", names)
            self.assertIn("pagos.csv", names)
            self.assertIn("obligaciones.csv", names)
            self.assertIn("referencias.csv", names)
            self.assertIn("gestiones_cobranza.csv", names)

            # Verificar que los encabezados son amigables y en español
            client_csv = zf.read("clientes.csv").decode("utf-8-sig")
            self.assertIn("Código Cliente", client_csv)
            self.assertIn("Nombre Completo", client_csv)

            loans_csv = zf.read("prestamos.csv").decode("utf-8-sig")
            self.assertIn("Código Préstamo", loans_csv)
            self.assertIn("Nombre del Cliente", loans_csv)

    def test_wipe_data_flow(self):
        with self.app.app_context():
            # Crear cliente de prueba con codigo unico
            import time
            code = f"CL-{int(time.time()*1000)%100000:05d}"
            c = Client(code=code, first_name="Prueba", last_name="Demo", identification_number="999888")
            db.session.add(c)
            db.session.commit()
            self.assertGreater(Client.query.count(), 0)

        # Intento con confirmacion invalida
        resp = self.client.post("/admin/borrar-datos", data={"confirm": "otro"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            self.assertGreater(Client.query.count(), 0)

        # Confirmacion correcta BORRAR
        resp = self.client.post("/admin/borrar-datos", data={"confirm": "BORRAR"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Client.query.count(), 0)
            self.assertIsNotNone(User.query.filter_by(username="admin").first())
            self.assertIsNotNone(User.query.filter_by(username="user_0").first())

if __name__ == "__main__":
    unittest.main()