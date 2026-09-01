"""Auditoría integral del sistema Cartera.

Recrea el flujo completo de negocio sobre una BD temporal y valida:
login, permisos, clientes, referencias, préstamos, amortización (francesa/alemana),
obligaciones, aplicación de pagos, anulación, documentos/nomenclatura, OCR,
cobranza, reportes, score, auditoría y parámetros.

Ejecutar directamente (no es unittest):
    .\.venv\Scripts\python.exe tests\test_audit_full.py
Exit 0 = todo OK, Exit 1 = hay fallos.
"""
import io
import os
import sys
import tempfile
import traceback

# Forzar UTF-8 en stdout/stderr (Windows usa cp1252 por defecto)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date

from PIL import Image, ImageDraw, ImageFont

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import (Audit, Client, CollectionManagement, Document,
                        Obligation, Payment, Permission, Role, User)
from app.services.documents import build_stored_name
from app.services.financial import calculate_schedule

# ---------------- Config de prueba ----------------
tmp = tempfile.mkdtemp()
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(tmp, "audit.db")
    UPLOAD_FOLDER = os.path.join(tmp, "uploads")
    WTF_CSRF_ENABLED = False
    AUTH_DISABLED = False

PASS = 0
FAIL = 0
CHECKS = []

def check(name, condition, detail=""):
    global PASS, FAIL
    status = "✅" if condition else "❌"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append((status, name, detail))
    print(f"{status} {name}" + (f"  → {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

app = create_app(TestConfig)
client = app.test_client()

# ---------------- 1. LOGIN Y SEGURIDAD ----------------
section("1. LOGIN, ROLES Y PERMISOS")

# Sin login -> redirige a /login
r = client.get("/")
check("Rutas protegidas redirigen sin sesión", r.status_code in (302, 401), f"status={r.status_code}")

# Login incorrecto
r = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=True)
with app.app_context():
    check("Login incorrecto rechazado", "Usuario o contraseña incorrectos" in r.get_data(as_text=True))

# Login correcto
r = client.post("/login", data={"username": "admin", "password": "09300"}, follow_redirects=True)
check("Login admin correcto", r.status_code == 200)

with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    roles = Role.query.all()
    perms = Permission.query.count()
    check("Rol Administrador con acceso total", admin.has_permission("admin.audit"))
    check("Roles sembrados (3)", len(roles) == 3, f"{len(roles)} roles")
    check("Permisos sembrados (19)", perms == 19, f"{perms} permisos")

    # Usuario inactivo no entra
    from app.models import User as U
    # Operador de cobranza NO tiene admin.audit
    op = Role.query.filter_by(name="Operador de cobranza").first()
    check("Operador NO tiene permiso admin.audit", not op.has_permission("admin.audit"))

# ---------------- 2. CLIENTE + REFERENCIAS ----------------
section("2. CREACIÓN DE CLIENTE")

r = client.post("/clientes/nuevo", data={
    "first_name": "María", "last_name": "Rodríguez",
    "identification_type": "CC", "identification_number": "1015701405",
    "country": "Colombia", "address": "Calle 50 # 12-34",
    "phone": "3105551234", "email": "maria.rodriguez@gmail.com",
    "ref_name": ["Pedro López", "Casa Prestamista S.A."],
    "ref_relationship": ["Codeudor", "Referencia"],
    "ref_identification": ["987654321", "900123456"],
    "ref_phone": ["3112223344", "6011234567"],
    "ref_address": ["Av 30 # 8-90", ""],
}, follow_redirects=True)
check("Crear cliente responde 200", r.status_code == 200)
with app.app_context():
    cli = Client.query.filter_by(identification_number="1015701405").first()
    check("Cliente creado", cli is not None)
    check("Código generado CL-XXXXX", cli.code.startswith("CL-"))
    check("Nombre completo", cli.full_name == "María Rodríguez")
    check("Referencias creadas (2)", len(cli.references) == 2, f"{len(cli.references)} refs")
    check("Codeudor registrado", cli.references[0].relationship == "Codeudor")
    CLIENTE_ID = cli.id

# ---------------- 3. PRÉSTAMO Y AMORTIZACIÓN ----------------
section("3. PRÉSTAMO Y AMORTIZACIÓN")

with app.app_context():
    cli = Client.query.get(CLIENTE_ID)

r = client.post("/prestamos/nuevo", data={
    "client_id": CLIENTE_ID, "principal": "2000000",
    "annual_rate": "36", "installments_count": "6",
    "frequency_days": "30", "amortization_type": "frances",
    "start_date": "2026-01-15",
}, follow_redirects=True)
check("Crear préstamo responde 200", r.status_code == 200)

with app.app_context():
    from app.models import Loan
    loan = Loan.query.filter_by(client_id=CLIENTE_ID).first()
    check("Préstamo creado", loan is not None)
    check("Código PR-XXXXX", loan.code.startswith("PR-"))
    check("Tasa convertida a decimal (0.20)", float(loan.annual_rate) == 0.20, f"{loan.annual_rate}")
    check("6 obligaciones generadas", len(loan.obligations) == 6, f"{len(loan.obligations)}")

    # Validación: francesa con tasa periódica i = 0.20 (20% por período)
    sched = calculate_schedule(2000000, 0.20, 6, date(2026, 1, 15))
    cuota = float(sched[0]["scheduled_value"])
    # cuota = 2M * 0.20 / (1 - 1.20^-6) = 400,000 / 0.665102 = 601,411.53
    check("Cuota francesa correcta (~601,411.53)", abs(cuota - 601411.53) < 1.0, f"{cuota:,.2f}")
    total_capital = sum(float(x["capital"]) for x in sched)
    check("Suma de capital = principal (2,000,000)", abs(total_capital - 2000000) < 0.01, f"{total_capital:,.2f}")
    # En la última cuota capital = saldo restante e interés = saldo_anterior x 0.20
    last_cap, last_int = float(sched[-1]["capital"]), float(sched[-1]["interest"])
    check("Última cuota: interés = capital x 20% (liquida saldo)", abs(last_int - round(last_cap * 0.20, 2)) < 0.01, f"cap={last_cap:,.2f} int={last_int:,.2f}")
    check("Fechas espaciadas 30 días", (sched[1]["due_date"] - sched[0]["due_date"]).days == 30)
    check("Estado inicial 'pendiente'", all(o.status == "pendiente" for o in loan.obligations))

# Amortización alemana
r = client.post("/prestamos/nuevo", data={
    "client_id": CLIENTE_ID, "principal": "1200000",
    "installments_count": "4",
    "frequency_days": "30", "amortization_type": "aleman",
    "start_date": "2026-02-01",
}, follow_redirects=True)
with app.app_context():
    loan2 = Loan.query.filter_by(client_id=CLIENTE_ID).order_by(Loan.id.desc()).first()
    check("Préstamo alemán creado", loan2 is not None)
    if loan2:
        sched_a = calculate_schedule(1200000, 0.20, 4, date(2026, 2, 1), amortization_type="aleman")
        c0, c1 = float(sched_a[0]["capital"]), float(sched_a[1]["capital"])
        i0, i1 = float(sched_a[0]["interest"]), float(sched_a[1]["interest"])
        check("Capital fijo alemán (300,000)", abs(c0 - 300000) < 0.01)
        check("Interés decreciente alemán", i1 < i0, f"{i0:,.2f} -> {i1:,.2f}")
        check("Cuota 1 alemán = 540,000", abs(float(sched_a[0]["scheduled_value"]) - 540000) < 0.01)

# ---------------- 4. PAGOS Y APLICACIÓN ----------------
section("4. APLICACIÓN DE PAGOS")

with app.app_context():
    loan = Loan.query.filter_by(client_id=CLIENTE_ID).order_by(Loan.id).first()
    cuota1 = loan.obligations[0]
    cuota1_int = float(cuota1.interest)
    cuota1_cap = float(cuota1.capital)
    loan_id = loan.id

# Pago exacto de la cuota 1 (interés + capital)
pago_exacto = round(cuota1_int + cuota1_cap, 2)
r = client.post("/pagos/nuevo", data={
    "loan_id": loan_id, "amount": str(pago_exacto),
    "payment_date": "2026-02-10", "concept": "Pago cuota 1",
    "receipt_number": "REC-001",
}, follow_redirects=True)
check("Registrar pago responde 200", r.status_code == 200)

with app.app_context():
    from app.models import Payment
    loan = Loan.query.get(loan_id)
    p1 = Payment.query.filter_by(loan_id=loan_id).first()
    check("Pago creado con código PG-XXXXX", p1 and p1.code.startswith("PG-"))
    check("Pago estado 'aplicado'", p1.status == "aplicado")
    check("Pago aplicado a 1 obligación", len(p1.applications) == 1, f"{len(p1.applications)} apps")
    if p1.applications:
        a = p1.applications[0]
        check("Interés aplicado completo", abs(float(a.interest_applied) - cuota1_int) < 0.01)
        check("Capital aplicado completo", abs(float(a.capital_applied) - cuota1_cap) < 0.01)
    o1 = loan.obligations[0]
    check("Cuota 1 marcada 'pagada'", o1.status == "pagada", o1.status)
    check("Fecha de pago registrada", o1.paid_date is not None)
    total_programado = sum(float(o.scheduled_value) for o in loan.obligations)
    check("Saldo pendiente del préstamo reducido", loan.outstanding_balance < total_programado, f"{loan.outstanding_balance:,.2f} < {total_programado:,.2f}")

# Pago parcial MENOR que el interés pendiente -> todo debe ir a interés
with app.app_context():
    loan = Loan.query.get(loan_id)
    o2 = loan.obligations[1]
    o2_int_pend = float(o2.pending_interest)
    print(f"    [diag] interés pendiente cuota 2: {o2_int_pend:,.2f}")

r = client.post("/pagos/nuevo", data={
    "loan_id": loan_id, "amount": "10000",
    "payment_date": "2026-03-10", "concept": "Abono parcial",
    "receipt_number": "REC-002",
}, follow_redirects=True)
with app.app_context():
    loan = Loan.query.get(loan_id)
    p2 = Payment.query.filter_by(loan_id=loan_id).order_by(Payment.id.desc()).first()
    check("Pago parcial creado", p2 and p2.status == "aplicado")
    if p2 and p2.applications:
        a = p2.applications[0]
        check("Pago parcial → 100% a interés (menor que interés pendiente)",
              abs(float(a.interest_applied) - 10000) < 0.01 and float(a.capital_applied) == 0,
              f"int={a.interest_applied} cap={a.capital_applied}")
    o2 = loan.obligations[1]
    check("Cuota 2 parcialmente pagada ('parcial')", o2.status == "parcial", o2.status)

# Pago que cubre el resto de cuota 2 (interés restante + capital) -> interés primero dentro de la cuota
with app.app_context():
    loan = Loan.query.get(loan_id)
    o2_rest_int = float(loan.obligations[1].pending_interest)
    o2_rest_cap = float(loan.obligations[1].pending_capital)
    monto_c2 = round(o2_rest_int + o2_rest_cap, 2)
r = client.post("/pagos/nuevo", data={
    "loan_id": loan_id, "amount": str(monto_c2),
    "payment_date": "2026-03-20", "concept": "Completa cuota 2",
    "receipt_number": "REC-002B",
}, follow_redirects=True)
with app.app_context():
    loan = Loan.query.get(loan_id)
    p2b = Payment.query.filter_by(loan_id=loan_id).order_by(Payment.id.desc()).first()
    a = p2b.applications[0]
    check("Interés restante se cubre antes que capital", abs(float(a.interest_applied) - o2_rest_int) < 0.01,
          f"int={a.interest_applied} cap={a.capital_applied}")
    check("Cuota 2 pagada", loan.obligations[1].status == "pagada")

# Pago con excedente (cubre cuota 3 y parte de la 4)
with app.app_context():
    loan = Loan.query.get(loan_id)
    o3_pend = round(loan.obligations[2].pending_balance, 2)
r = client.post("/pagos/nuevo", data={
    "loan_id": loan_id, "amount": str(o3_pend + 50000),
    "payment_date": "2026-04-10", "concept": "Pago cuota 3 + abono",
    "receipt_number": "REC-003",
}, follow_redirects=True)
with app.app_context():
    loan = Loan.query.get(loan_id)
    p3 = Payment.query.filter_by(loan_id=loan_id).order_by(Payment.id.desc()).first()
    check("Excedente aplica a siguiente cuota", len(p3.applications) == 2, f"{len(p3.applications)} apps")
    check("Cuota 3 pagada por excedente", loan.obligations[2].status == "pagada")

# ---------------- 5. ANULACIÓN ----------------
section("5. ANULACIÓN DE PAGO")

with app.app_context():
    loan = Loan.query.get(loan_id)
    p1 = Payment.query.filter_by(loan_id=loan_id).order_by(Payment.id).first()
    p1_id = p1.id
    monto_p1 = float(p1.amount)
    saldo_antes = loan.outstanding_balance

r = client.post(f"/pagos/{p1_id}/anular", follow_redirects=True)
check("Anular pago responde 200", r.status_code == 200)
with app.app_context():
    loan = Loan.query.get(loan_id)
    p1 = Payment.query.get(p1_id)
    check("Pago anulado", p1.status == "anulado")
    check("Cuota 1 vuelve a 'pendiente'", loan.obligations[0].status == "pendiente", loan.obligations[0].status)
    check("Saldo restaurado (+monto del pago anulado)",
          abs(loan.outstanding_balance - (saldo_antes + monto_p1)) < 0.01,
          f"antes={saldo_antes:,.2f} después={loan.outstanding_balance:,.2f} +{monto_p1:,.2f}")

# ---------------- 6. DOCUMENTOS Y NOMENCLATURA ----------------
section("6. DOCUMENTOS Y NOMENCLATURA")

png = io.BytesIO()
img = Image.new("RGB", (60, 20), "white")
ImageDraw.Draw(img)
img.save(png, format="PNG")
png.seek(0)

r = client.post(f"/clientes/{CLIENTE_ID}/documentos", data={
    "doc_type": "identificacion",
    "file": (png, "mi-cedula.png"),
}, content_type="multipart/form-data", follow_redirects=True)
check("Subir documento responde 200", r.status_code == 200)
with app.app_context():
    doc = Document.query.filter_by(entity_type="cliente", entity_id=CLIENTE_ID).first()
    check("Documento creado", doc is not None)
    if doc:
        check("Nomenclatura trazable", doc.stored_name.startswith(f"cliente/{CLIENTE_ID}/cliente-{CLIENTE_ID}-identificacion-"), doc.stored_name)
        check("Archivo existe en disco", os.path.exists(doc.path))
        check("Nombre original conservado", doc.original_name == "mi-cedula.png")
        rdl = client.get(f"/documentos/{doc.id}/descargar")
        check("Descarga del documento 200", rdl.status_code == 200, f"status={rdl.status_code}")

# Validación de build_stored_name (siempre con '/')
n = build_stored_name("cliente", CLIENTE_ID, "identificacion", "png")
check("build_stored_name formato correcto (slash)", n.startswith(f"cliente/{CLIENTE_ID}/cliente-{CLIENTE_ID}-identificacion-20") and n.endswith(".png") and "\\" not in n, n)

# Reemplazo de documento
png2 = io.BytesIO()
ImageDraw.Draw(Image.new("RGB", (60, 20), "white")).text((2, 2), "x", fill="black")
png2.seek(0)
r = client.post(f"/documentos/{doc.id}/reemplazar", data={"file": (png2, "nueva.png")}, content_type="multipart/form-data", follow_redirects=True)
with app.app_context():
    doc2 = Document.query.get(doc.id)
    check("Reemplazo conserva trazabilidad", doc2.stored_name.startswith(f"cliente/{CLIENTE_ID}/cliente-{CLIENTE_ID}-") and "\\" not in doc2.stored_name, doc2.stored_name)

# ---------------- 7. OCR ----------------
section("7. OCR (imagen y PDF)")

# Imagen con texto legible
img = Image.new("RGB", (1600, 600), "white")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 44)
except Exception:
    font = ImageFont.load_default()
d.text((40, 40), "CEDULA DE CIUDADANIA", fill="black", font=font)
d.text((40, 110), "NUMERO 1.057.014.054", fill="black", font=font)
d.text((40, 180), "APELLIDOS: RODRIGUEZ GOMEZ", fill="black", font=font)
d.text((40, 250), "NOMBRES: MARIA FERNANDA", fill="black", font=font)
buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

r = client.post("/clientes/ocr", data={"file": (buf, "cedula.png")}, content_type="multipart/form-data")
check("Endpoint OCR responde JSON 200", r.status_code == 200 and r.is_json)
if r.is_json:
    data = r.get_json()
    check("OCR ok=True", data.get("ok") is True)
    try:
        import easyocr  # noqa: F401
        has_easyocr = True
    except ImportError:
        has_easyocr = False

    if has_easyocr:
        f = data.get("fields", {})
        check("OCR texto no vacío", bool(data.get("text", "").strip()), data.get("text", "")[:60].replace("\n", " | "))
        check("OCR detecta cédula", f.get("identification_number") == "1057014054", f.get("identification_number"))
        check("OCR detecta apellidos", "RODRIGUEZ" in (f.get("last_name") or "").upper(), f.get("last_name"))
        check("OCR detecta nombres", "MARIA" in (f.get("first_name") or "").upper(), f.get("first_name"))
    else:
        check("OCR maneja ausencia de EasyOCR sin fallar", data.get("ok") is True, "Degradación elegante activa")

# PDF digital
import fitz
pdf = fitz.open()
pg = pdf.new_page()
pg.insert_text((72, 72), "NUMERO 1.057.014.054")
pg.insert_text((72, 100), "APELLIDOS: RODRIGUEZ GOMEZ")
pg.insert_text((72, 128), "NOMBRES: MARIA FERNANDA")
pdf_bytes = pdf.tobytes()
pdf.close()
r = client.post("/clientes/ocr", data={"file": (io.BytesIO(pdf_bytes), "doc.pdf")}, content_type="multipart/form-data")
check("OCR PDF responde JSON 200", r.status_code == 200 and r.is_json)
if r.is_json:
    f2 = r.get_json().get("fields", {})
    check("OCR PDF detecta cédula", f2.get("identification_number") == "1057014054", f2.get("identification_number"))

# Archivo no permitido
r = client.post("/clientes/ocr", data={"file": (io.BytesIO(b"x"), "virus.exe")}, content_type="multipart/form-data")
check("OCR rechaza extensión no permitida", r.status_code == 400 and r.is_json)

# ---------------- 8. COBRANZA ----------------
section("8. COBRANZA")

# Obligaciones vencidas del préstamo 1 (fechas 2026-01-15+, hoy es 2026-08-20 → vencidas)
r = client.get("/cobranza/")
check("Lista de cobranza 200", r.status_code == 200, f"status={r.status_code}")

with app.app_context():
    from app.models import Obligation as Ob
    vencidas = Ob.query.join(Loan).join(Client).filter(
        Ob.status != "pagada", Ob.due_date < __import__("datetime").datetime.utcnow().date()
    ).all()
    check("Hay obligaciones vencidas", len(vencidas) > 0, f"{len(vencidas)} vencidas")
    ob_id = vencidas[0].id if vencidas else None

if ob_id:
    r = client.post(f"/cobranza/gestion/{ob_id}", data={
        "action": "llamada", "notes": "Cliente promete pagar el viernes",
        "next_date": "2026-08-25",
    }, follow_redirects=True)
    check("Registrar gestión 200", r.status_code == 200)
    with app.app_context():
        g = CollectionManagement.query.order_by(CollectionManagement.id.desc()).first()
        check("Gestión registrada", g is not None and g.action == "llamada")
        check("Próxima fecha guardada", str(g.next_date) == "2026-08-25")

r = client.get("/cobranza/gestiones")
check("Historial de gestiones 200", r.status_code == 200)

# ---------------- 9. REPORTES Y SCORE ----------------
section("9. REPORTES Y SCORE")

r = client.get("/")
check("Dashboard 200", r.status_code == 200)
r = client.get("/reportes/cartera")
check("Reporte cartera 200", r.status_code == 200)
r = client.get("/reportes/score")
check("Reporte score 200", r.status_code == 200)

with app.app_context():
    from app.services.scoring import compute_score
    cli = Client.query.get(CLIENTE_ID)
    sc = compute_score(cli)
    check("Score calculado 0-100", sc["score"] is not None and 0 <= sc["score"] <= 100, f"score={sc['score']} ({sc['band']})")
    check("Banda válida", sc["band"] in ("Excelente", "Bueno", "Regular", "Riesgo alto"))

    # Cliente sin historial
    cli2 = Client(code="CL-99999", first_name="Sin", last_name="Historial",
                  identification_number="99999")
    db.session.add(cli2); db.session.commit()
    sc2 = compute_score(cli2)
    check("Cliente sin historial → None", sc2["score"] is None)

# ---------------- 10. AUDITORÍA Y PARÁMETROS ----------------
section("10. AUDITORÍA Y PARÁMETROS")

r = client.get("/admin/auditoria")
check("Auditoría 200", r.status_code == 200)
with app.app_context():
    n_audit = Audit.query.count()
    check("Registros de auditoría generados", n_audit > 10, f"{n_audit} registros")
    acciones = {a.action for a in Audit.query.all()}
    for esperado in ("Inicio de sesión", "Crear cliente", "Crear préstamo", "Registrar pago", "Anular pago"):
        check(f"Auditoría: {esperado}", esperado in acciones)

r = client.get("/admin/parametros")
check("Parámetros 200", r.status_code == 200)
r = client.get("/admin/roles")
check("Roles 200", r.status_code == 200)
r = client.get("/admin/usuarios")
check("Usuarios 200", r.status_code == 200)

# ---------------- 11. LOGOUT ----------------
section("11. LOGOUT")

r = client.get("/logout", follow_redirects=True)
check("Logout redirige a login", "login" in r.request.path or r.status_code == 200)

# ---------------- RESUMEN ----------------
print(f"\n{'='*70}\n  RESUMEN DE AUDITORÍA\n{'='*70}")
print(f"  Aprobadas: {PASS}   Fallidas: {FAIL}   Total: {PASS+FAIL}")
if FAIL:
    print("\n  Fallos:")
    for s, n, d in CHECKS:
        if s == "❌":
            print(f"   ❌ {n}  {d}")
print(f"\n  BD temporal: {tmp}")
print(f"  Exit: {'OK' if FAIL == 0 else 'CON FALLOS'}")
import sys
sys.exit(1 if FAIL else 0)
