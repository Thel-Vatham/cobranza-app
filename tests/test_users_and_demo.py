import unittest
from app import create_app
from app.config import Config
from app.models import User, Client, Loan, Payment

class UserRolesAndTraceabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class TC(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            AUTH_DISABLED = False
            SESSION_COOKIE_SECURE = False
        cls.app = create_app(TC)
        with cls.app.app_context():
            from app.seed import _seed_demo_data
            _seed_demo_data(force=True)

    def test_users_exist_and_passwords(self):
        with self.app.app_context():
            users = User.query.all()
            usernames = [u.username for u in users]
            self.assertEqual(sorted(usernames), ["admin", "user_0"])
            
            admin = User.query.filter_by(username="admin").first()
            self.assertTrue(admin.check_password("09300"))
            self.assertEqual(admin.role.name, "Administrador")
            self.assertTrue(admin.has_permission("admin.users"))
            self.assertTrue(admin.has_permission("admin.audit"))
            
            user_0 = User.query.filter_by(username="user_0").first()
            self.assertTrue(user_0.check_password("09300"))
            self.assertEqual(user_0.role.name, "Operador de cobranza")
            self.assertTrue(user_0.has_permission("clients.view"))
            self.assertTrue(user_0.has_permission("loans.create"))
            self.assertTrue(user_0.has_permission("payments.create"))
            self.assertFalse(user_0.has_permission("admin.users"))
            self.assertFalse(user_0.has_permission("admin.audit"))

    def test_admin_full_access(self):
        c = self.app.test_client()
        # Login admin
        resp = c.post("/login", data={"username": "admin", "password": "09300"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        # Acceso a todo
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/clientes/").status_code, 200)
        self.assertEqual(c.get("/prestamos/").status_code, 200)
        self.assertEqual(c.get("/pagos/").status_code, 200)
        self.assertEqual(c.get("/cobranza/").status_code, 200)
        self.assertEqual(c.get("/documentos/").status_code, 200)
        self.assertEqual(c.get("/reportes/cartera").status_code, 200)
        self.assertEqual(c.get("/admin/usuarios").status_code, 200)
        self.assertEqual(c.get("/admin/roles").status_code, 200)
        self.assertEqual(c.get("/admin/parametros").status_code, 200)
        self.assertEqual(c.get("/admin/auditoria").status_code, 200)
        self.assertEqual(c.get("/admin/datos").status_code, 200)
        self.assertEqual(c.get("/admin/exportar-csv").status_code, 200)

    def test_user_0_restricted_access(self):
        c = self.app.test_client()
        # Login user_0
        resp = c.post("/login", data={"username": "user_0", "password": "09300"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        # Puede ver y hacer gestion
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/clientes/").status_code, 200)
        self.assertEqual(c.get("/prestamos/").status_code, 200)
        self.assertEqual(c.get("/pagos/").status_code, 200)
        self.assertEqual(c.get("/cobranza/").status_code, 200)
        self.assertEqual(c.get("/documentos/").status_code, 200)
        self.assertEqual(c.get("/reportes/cartera").status_code, 200)
        # BLOQUEADO de administracion / export / wipe
        self.assertEqual(c.get("/admin/usuarios").status_code, 403)
        self.assertEqual(c.get("/admin/roles").status_code, 403)
        self.assertEqual(c.get("/admin/parametros").status_code, 403)
        self.assertEqual(c.get("/admin/auditoria").status_code, 403)
        self.assertEqual(c.get("/admin/datos").status_code, 403)
        self.assertEqual(c.get("/admin/exportar-csv").status_code, 403)
        resp_wipe = c.post("/admin/borrar-datos", data={"confirm": "BORRAR"})
        self.assertEqual(resp_wipe.status_code, 403)

    def test_demo_traceability(self):
        with self.app.app_context():
            self.assertGreaterEqual(Client.query.count(), 2)
            self.assertGreaterEqual(Loan.query.count(), 2)
            self.assertGreaterEqual(Payment.query.count(), 2)
            c1 = Client.query.filter_by(identification_number="1057014054").first()
            self.assertIsNotNone(c1)
            self.assertEqual(c1.full_name, "NICOLAS SANTA GONZALEZ")
            c2 = Client.query.filter_by(identification_number="1023456789").first()
            self.assertIsNotNone(c2)
            self.assertEqual(c2.full_name, "CAROLINA MARTINEZ RUIZ")
            self.assertGreater(len(c2.references), 0)

if __name__ == "__main__":
    unittest.main()