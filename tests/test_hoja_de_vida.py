import io
import unittest
from decimal import Decimal
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Client, Document, Reference, User

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    AUTH_DISABLED = True
    SESSION_COOKIE_SECURE = False

class HojaDeVidaTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def test_rejection_when_less_than_two_references(self):
        """Verifica que el sistema rechaza la creación si hay menos de 2 referencias."""
        resp = self.client.post("/clientes/nuevo", data={
            "first_name": "Pedro",
            "last_name": "Incompleto",
            "identification_type": "CC",
            "identification_number": "55443322",
            "ref_name": ["Solo Una Referencia"],
            "ref_phone": ["3001112233"],
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Debe ingresar exactamente dos (2) referencias", html)

        with self.app.app_context():
            cli = Client.query.filter_by(identification_number="55443322").first()
            self.assertIsNone(cli)

    def test_successful_creation_with_full_hoja_de_vida(self):
        """Verifica la creación con empleo, datos bancarios duales, 2 referencias y 4 archivos."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        id_num = f"88{uid}"

        debtor_img = (io.BytesIO(b"dummy image bytes"), "rostro.jpg")
        work_img = (io.BytesIO(b"dummy work bytes"), "oficina.jpg")
        facade_img = (io.BytesIO(b"dummy facade bytes"), "casa.jpg")
        id_doc = (io.BytesIO(b"%PDF-1.4 dummy id pdf"), "cedula.pdf")

        resp = self.client.post(
            "/clientes/nuevo",
            data={
                "first_name": "Alejandro",
                "last_name": "Morales Ruiz",
                "identification_type": "CC",
                "identification_number": id_num,
                "country": "Colombia",
                "city": "Bogotá",
                "address": "Calle 100 # 15-20",
                "phone": "3109998877",
                "email": "alejandro.morales@example.com",
                # Datos de empleo
                "employer_name": "Tecnología y Soluciones S.A.S.",
                "job_title": "Desarrollador de Software",
                "salary": "4.800.000",
                "employer_address": "Carrera 7 # 116-50",
                "employer_phone": "6017778899",
                # Desembolso
                "bank_name": "Bancolombia",
                "account_type": "Ahorros",
                "account_number": "10987654320",
                "account_holder": "Alejandro Morales",
                # Recaudo
                "collection_bank_name": "Nequi",
                "collection_account_type": "Billetera Digital",
                "collection_account_number": "3109998877",
                "collection_account_holder": "Alejandro Morales Ruiz",
                # Referencias (exactamente 2)
                "ref_name": ["Laura Morales", "Carlos Ruiz"],
                "ref_relationship": ["Codeudor", "Familiar"],
                "ref_identification": ["52111222", "19333444"],
                "ref_phone": ["3151112233", "3204445566"],
                "ref_address": ["Calle 100 # 15-20", "Carrera 9 # 70-10"],
                # 4 Fotografías / Documentos
                "debtor_photo": debtor_img,
                "work_photo": work_img,
                "facade_photo": facade_img,
                "id_document": id_doc,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Verificar renderizado en la Hoja de Vida
        self.assertIn("Alejandro Morales Ruiz", html)
        self.assertIn("Desarrollador de Software", html)
        self.assertIn("Tecnología y Soluciones S.A.S.", html)
        self.assertIn("4,800,000", html)
        self.assertIn("Bancolombia", html)
        self.assertIn("10987654320", html)
        self.assertIn("Nequi", html)
        self.assertIn("3109998877", html)
        self.assertIn("Laura Morales", html)
        self.assertIn("Carlos Ruiz", html)
        self.assertIn("Codeudor", html)

        # Verificar almacenamiento en base de datos
        with self.app.app_context():
            cli = Client.query.filter_by(identification_number=id_num).first()
            self.assertIsNotNone(cli)
            self.assertEqual(cli.employer_name, "Tecnología y Soluciones S.A.S.")
            self.assertEqual(cli.job_title, "Desarrollador de Software")
            self.assertEqual(cli.salary, Decimal("4800000.00"))
            self.assertEqual(cli.collection_bank_name, "Nequi")
            self.assertEqual(cli.collection_account_number, "3109998877")
            self.assertEqual(len(cli.references), 2)

            # Verificar 4 documentos asociados
            docs = Document.query.filter_by(entity_type="cliente", entity_id=cli.id).all()
            doc_types = {d.doc_type for d in docs}
            self.assertIn("foto_deudor", doc_types)
            self.assertIn("foto_trabajo", doc_types)
            self.assertIn("fachada", doc_types)
            self.assertIn("identificacion", doc_types)

            # Probar ruta view_raw para la foto del deudor
            d_photo = next(d for d in docs if d.doc_type == "foto_deudor")
            doc_resp = self.client.get(f"/documentos/{d_photo.id}/ver")
            self.assertEqual(doc_resp.status_code, 200)
            self.assertIn(doc_resp.mimetype, ["image/jpeg", "image/png", "application/octet-stream"])

    def test_edit_hoja_de_vida(self):
        """Verifica la edición de los datos de empleo y datos bancarios."""
        import uuid
        uid = uuid.uuid4().hex[:6]
        code = f"CL-E{uid}"
        id_num = f"99{uid}"
        with self.app.app_context():
            c = Client(
                code=code,
                first_name="Camila",
                last_name="Torres",
                identification_number=id_num,
                employer_name="Antigua Empresa",
                job_title="Auxiliar",
                salary=Decimal("1500000.00"),
            )
            c.references.append(Reference(full_name="Ref A", phone="3001"))
            c.references.append(Reference(full_name="Ref B", phone="3002"))
            db.session.add(c)
            db.session.commit()
            client_id = c.id

        resp = self.client.post(
            f"/clientes/{client_id}/editar",
            data={
                "first_name": "Camila",
                "last_name": "Torres Rios",
                "identification_type": "CC",
                "identification_number": "66554433",
                "employer_name": "Nueva Empresa Global",
                "job_title": "Directora de Operaciones",
                "salary": "6.000.000",
                "bank_name": "Davivienda",
                "account_number": "44332211",
                "collection_bank_name": "Daviplata",
                "collection_account_number": "3158889900",
                "ref_name": ["Codeudor Uno", "Referencia Dos"],
                "ref_relationship": ["Codeudor", "Personal"],
                "ref_phone": ["3119990011", "3129990022"],
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            cli = Client.query.get(client_id)
            self.assertEqual(cli.last_name, "Torres Rios")
            self.assertEqual(cli.employer_name, "Nueva Empresa Global")
            self.assertEqual(cli.job_title, "Directora de Operaciones")
            self.assertEqual(cli.salary, Decimal("6000000.00"))
            self.assertEqual(cli.bank_name, "Davivienda")
            self.assertEqual(cli.collection_bank_name, "Daviplata")
            self.assertEqual(len(cli.references), 2)

if __name__ == "__main__":
    unittest.main()
