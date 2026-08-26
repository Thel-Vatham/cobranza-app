from datetime import date, datetime, timedelta
from decimal import Decimal
from .extensions import db
from .models import (Audit, Client, CollectionManagement, Document,
                     Loan, Obligation, Parameter, Payment,
                     PaymentApplication, Permission, Reference, Role, User)
from .services.financial import calculate_schedule

PERMISSIONS = [
    ("Ver panel principal", "dashboard.view", "Acceso al dashboard"),
    ("Ver clientes", "clients.view", "Consultar clientes"),
    ("Crear clientes", "clients.create", "Registrar clientes"),
    ("Editar clientes", "clients.edit", "Modificar clientes"),
    ("Ver préstamos", "loans.view", "Consultar préstamos"),
    ("Crear préstamos", "loans.create", "Registrar préstamos"),
    ("Editar préstamos", "loans.edit", "Modificar préstamos"),
    ("Ver pagos", "payments.view", "Consultar pagos"),
    ("Crear pagos", "payments.create", "Registrar y aplicar pagos"),
    ("Anular pagos", "payments.revert", "Revertir/anular pagos"),
    ("Ver cobranza", "collections.view", "Consultar cobranza"),
    ("Registrar cobranza", "collections.create", "Registrar gestión de cobranza"),
    ("Ver documentos", "documents.view", "Consultar documentos"),
    ("Cargar documentos", "documents.upload", "Subir documentos"),
    ("Ver reportes", "reports.view", "Consultar cartera y score"),
    ("Administrar usuarios", "admin.users", "Gestión de usuarios"),
    ("Administrar roles", "admin.roles", "Gestión de roles y permisos"),
    ("Administrar parámetros", "admin.parameters", "Parámetros del sistema"),
    ("Ver auditoría", "admin.audit", "Consultar auditoría"),
]

ROLES = {
    "Administrador": None,  # acceso total
    "Operador de cobranza": [
        "dashboard.view", "clients.view", "clients.create", "clients.edit",
        "loans.view", "loans.create", "payments.view", "payments.create",
        "collections.view", "collections.create", "documents.view", "documents.upload",
        "reports.view",
    ],
    "Consulta": [
        "dashboard.view", "clients.view", "loans.view", "payments.view",
        "collections.view", "documents.view", "reports.view",
    ],
}

# (key, value, category, kind, description)
PARAMETERS = [
    ("metodo_interes", "frances", "financieros", "text", "Método de amortización de la cuota"),
    ("periodicidad_interes", "mensual", "financieros", "text", "Periodicidad del interés"),
    ("orden_aplicacion_pago", "interes_primero", "financieros", "text", "Orden de aplicación del pago"),
    ("tasa_mora_diaria", "0.001", "financieros", "number", "Tasa de mora diaria (referencial)"),
    ("dias_proximos_vencer", "15", "cobranza", "number", "Días del horizonte de obligaciones por vencer"),
    ("dias_alerta_mora", "5", "cobranza", "number", "Umbral de días para alerta de mora temprana"),
    ("peso_puntualidad", "0.45", "scoring", "number", "Peso de puntualidad en el score"),
    ("peso_cumplimiento", "0.35", "scoring", "number", "Peso de cumplimiento en el score"),
    ("peso_mora", "0.20", "scoring", "number", "Peso de mora en el score"),
    ("dias_max_mora_score", "90", "scoring", "number", "Días máximos de mora para escalar la penalización"),
]


def seed_if_empty():
    _seed_permissions_and_roles()
    _seed_users()
    _seed_demo_data()
    seed_parameters()


def _seed_permissions_and_roles():
    if not Permission.query.first():
        for name, code, description in PERMISSIONS:
            db.session.add(Permission(name=name, code=code, description=description))
        db.session.flush()

    perms_by_code = {p.code: p for p in Permission.query.all()}

    for role_name, perm_codes in ROLES.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=role_name)
            if perm_codes:
                role.permissions = [perms_by_code[c] for c in perm_codes if c in perms_by_code]
            db.session.add(role)
        else:
            if perm_codes:
                role.permissions = [perms_by_code[c] for c in perm_codes if c in perms_by_code]
    db.session.flush()


def _seed_users():
    admin_role = Role.query.filter_by(name="Administrador").first()
    operator_role = Role.query.filter_by(name="Operador de cobranza").first()

    # Eliminar usuarios anteriores obsoletos para dejar solo admin y user_0
    User.query.filter(User.username.notin_(["admin", "user_0"])).delete()

    # Usuario admin (Acceso total)
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@cartera.local",
            full_name="Administrador",
            role_id=admin_role.id if admin_role else None,
            active=True,
        )
        db.session.add(admin)
    admin.set_password("09300")
    admin.role_id = admin_role.id if admin_role else None
    admin.active = True

    # Usuario user_0 (Solo gestión)
    user_0 = User.query.filter_by(username="user_0").first()
    if not user_0:
        user_0 = User(
            username="user_0",
            email="user_0@cartera.local",
            full_name="Operador de Gestión",
            role_id=operator_role.id if operator_role else None,
            active=True,
        )
        db.session.add(user_0)
    user_0.set_password("09300")
    user_0.role_id = operator_role.id if operator_role else None
    user_0.active = True

    db.session.commit()


def _seed_demo_data(force=False):
    """Genera datos de prueba realistas con 10 clientes, cartera de 3M COP y trazabilidad de 2 meses."""
    if not force and Client.query.first():
        return

    if force:
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        CollectionManagement.query.delete()
        Document.query.delete()
        Reference.query.delete()
        Loan.query.delete()
        Client.query.delete()
        db.session.commit()

    admin = User.query.filter_by(username="admin").first()
    admin_id = admin.id if admin else 1

    clients_def = [
        {
            "code": "CL-00001",
            "first_name": "NICOLAS",
            "last_name": "SANTA GONZALEZ",
            "id_num": "1057014054",
            "phone": "3101234567",
            "address": "Carrera 7 # 72-11, Bogotá",
            "email": "nicolas.santa@example.com",
            "city": "Bogotá",
            "references": [
                {"name": "MARIA ELENA GONZALEZ", "rel": "Familiar", "id_num": "51876543", "phone": "3119876543", "address": "Carrera 7 # 72-11, Bogotá"},
                {"name": "PEDRO PABLO SANTA", "rel": "Codeudor", "id_num": "19345678", "phone": "3123456789", "address": "Calle 68 # 14-20, Bogotá"}
            ],
            "loan": {
                "code": "PR-00001",
                "principal": 250000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 27),
                "paid_installments": 2,
            }
        },
        {
            "code": "CL-00002",
            "first_name": "CAROLINA",
            "last_name": "MARTINEZ RUIZ",
            "id_num": "1023456789",
            "phone": "3159876543",
            "address": "Calle 45 # 18-30, Medellín",
            "email": "carolina.martinez@example.com",
            "city": "Medellín",
            "references": [
                {"name": "LUIS FERNANDO TORRES", "rel": "Codeudor", "id_num": "798765432", "phone": "3112223344", "address": "Calle 45 # 18-30, Medellín"},
                {"name": "CLARA INES RUIZ", "rel": "Familiar", "id_num": "43567890", "phone": "3167778899", "address": "Circular 4 # 70-15, Medellín"}
            ],
            "loan": {
                "code": "PR-00002",
                "principal": 600000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 28),
                "paid_installments": 2,
            }
        },
        {
            "code": "CL-00003",
            "first_name": "ANDRES FELIPE",
            "last_name": "GOMEZ OROZCO",
            "id_num": "80123456",
            "phone": "3205551234",
            "address": "Avenida 6N # 24-05, Cali",
            "email": "andres.gomez@example.com",
            "city": "Cali",
            "references": [
                {"name": "MARIA PAULA GOMEZ", "rel": "Familiar", "id_num": "52987654", "phone": "3189998877", "address": "Avenida 6N # 24-05, Cali"},
                {"name": "CARLOS ALBERTO OROZCO", "rel": "Comercial", "id_num": "16789012", "phone": "3104443322", "address": "Calle 9 # 32-10, Cali"}
            ],
            "loan": {
                "code": "PR-00003",
                "principal": 400000,
                "annual_rate": 0.20,
                "installments": 3,
                "freq": 30,
                "start_date": date(2026, 7, 29),
                "paid_installments": 1,
            }
        },
        {
            "code": "CL-00004",
            "first_name": "DIANA MARCELA",
            "last_name": "RODRIGUEZ SILVA",
            "id_num": "52987123",
            "phone": "3147890123",
            "address": "Calle 72 # 53-19, Barranquilla",
            "email": "diana.rodriguez@example.com",
            "city": "Barranquilla",
            "references": [
                {"name": "GUSTAVO RODRIGUEZ", "rel": "Familiar", "id_num": "72345678", "phone": "3145556677", "address": "Calle 72 # 53-19, Barranquilla"},
                {"name": "SONIA SILVA PEREZ", "rel": "Codeudor", "id_num": "32876543", "phone": "3171112233", "address": "Carrera 46 # 80-25, Barranquilla"}
            ],
            "loan": {
                "code": "PR-00004",
                "principal": 350000,
                "annual_rate": 0.20,
                "installments": 3,
                "freq": 30,
                "start_date": date(2026, 7, 27),
                "paid_installments": 1,
            }
        },
        {
            "code": "CL-00005",
            "first_name": "CARLOS EDUARDO",
            "last_name": "HERRERA CASTRO",
            "id_num": "71234567",
            "phone": "3163334455",
            "address": "Carrera 27 # 36-14, Bucaramanga",
            "email": "carlos.herrera@example.com",
            "city": "Bucaramanga",
            "references": [
                {"name": "ALVARO HERRERA", "rel": "Familiar", "id_num": "91234567", "phone": "3168889900", "address": "Carrera 27 # 36-14, Bucaramanga"},
                {"name": "PATRICIA CASTRO", "rel": "Codeudor", "id_num": "63456789", "phone": "3154445566", "address": "Calle 48 # 33-20, Bucaramanga"}
            ],
            "loan": {
                "code": "PR-00005",
                "principal": 500000,
                "annual_rate": 0.20,
                "installments": 3,
                "freq": 30,
                "start_date": date(2026, 7, 28),
                "paid_installments": 1,
            }
        },
        {
            "code": "CL-00006",
            "first_name": "VALENTINA",
            "last_name": "RESTREPO LOPEZ",
            "id_num": "1037654321",
            "phone": "3124445566",
            "address": "Avenida Circunvalar # 12-40, Pereira",
            "email": "valentina.restrepo@example.com",
            "city": "Pereira",
            "references": [
                {"name": "SANTIAGO RESTREPO", "rel": "Codeudor", "id_num": "9876543", "phone": "3156667788", "address": "Avenida Circunvalar # 12-40, Pereira"},
                {"name": "GLORIA LOPEZ GIRALDO", "rel": "Familiar", "id_num": "42123456", "phone": "3113332211", "address": "Carrera 8 # 20-30, Pereira"}
            ],
            "loan": {
                "code": "PR-00006",
                "principal": 300000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 29),
                "paid_installments": 2,
            }
        },
        {
            "code": "CL-00007",
            "first_name": "JORGE ENRIQUE",
            "last_name": "CASTRO MORA",
            "id_num": "19456789",
            "phone": "3181112233",
            "address": "Carrera 23 # 55-08, Manizales",
            "email": "jorge.castro@example.com",
            "city": "Manizales",
            "references": [
                {"name": "HECTOR CASTRO", "rel": "Familiar", "id_num": "10234567", "phone": "3187776655", "address": "Carrera 23 # 55-08, Manizales"},
                {"name": "LUCIA MORA CARDONA", "rel": "Codeudor", "id_num": "30456789", "phone": "3142223344", "address": "Avenida Santander # 45-12, Manizales"}
            ],
            "loan": {
                "code": "PR-00007",
                "principal": 200000,
                "annual_rate": 0.20,
                "installments": 3,
                "freq": 30,
                "start_date": date(2026, 6, 20),
                "paid_installments": 1,
                "is_overdue": True,
            }
        },
        {
            "code": "CL-00008",
            "first_name": "LILIANA PATRICIA",
            "last_name": "VARGAS MENDOZA",
            "id_num": "43987654",
            "phone": "3178889900",
            "address": "Bocagrande Carrera 3 # 8-12, Cartagena",
            "email": "liliana.vargas@example.com",
            "city": "Cartagena",
            "references": [
                {"name": "ROBERTO VARGAS", "rel": "Familiar", "id_num": "73123456", "phone": "3176665544", "address": "Bocagrande Carrera 3 # 8-12, Cartagena"},
                {"name": "MARINA MENDOZA", "rel": "Comercial", "id_num": "45678901", "phone": "3103332211", "address": "Manga Avenida Jiménez # 18-05, Cartagena"}
            ],
            "loan": {
                "code": "PR-00008",
                "principal": 150000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 27),
                "paid_installments": 2,
            }
        },
        {
            "code": "CL-00009",
            "first_name": "MAURICIO ALEJANDRO",
            "last_name": "DUQUE JARAMILLO",
            "id_num": "98765432",
            "phone": "3107778899",
            "address": "Calle 14 # 16-25, Armenia",
            "email": "mauricio.duque@example.com",
            "city": "Armenia",
            "references": [
                {"name": "JAVIER DUQUE", "rel": "Familiar", "id_num": "75123456", "phone": "3105554433", "address": "Calle 14 # 16-25, Armenia"},
                {"name": "ANA MARIA JARAMILLO", "rel": "Codeudor", "id_num": "41987654", "phone": "3184443322", "address": "Avenida Bolívar # 19-30, Armenia"}
            ],
            "loan": {
                "code": "PR-00009",
                "principal": 150000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 28),
                "paid_installments": 2,
            }
        },
        {
            "code": "CL-00010",
            "first_name": "CAMILA ANDREA",
            "last_name": "ORTIZ PENAGOS",
            "id_num": "1018765432",
            "phone": "3132221100",
            "address": "Carrera 5 # 38-20, Ibagué",
            "email": "camila.ortiz@example.com",
            "city": "Ibagué",
            "references": [
                {"name": "FERNANDO ORTIZ", "rel": "Familiar", "id_num": "93456789", "phone": "3137776655", "address": "Carrera 5 # 38-20, Ibagué"},
                {"name": "SANDRA PENAGOS", "rel": "Codeudor", "id_num": "65123456", "phone": "3129998877", "address": "Calle 60 # 7-15, Ibagué"}
            ],
            "loan": {
                "code": "PR-00010",
                "principal": 100000,
                "annual_rate": 0.20,
                "installments": 4,
                "freq": 15,
                "start_date": date(2026, 7, 29),
                "paid_installments": 2,
            }
        }
    ]

    payment_counter = 1

    for c_def in clients_def:
        client = Client(
            code=c_def["code"],
            first_name=c_def["first_name"],
            last_name=c_def["last_name"],
            identification_type="CC",
            identification_number=c_def["id_num"],
            phone=c_def["phone"],
            email=c_def.get("email"),
            address=c_def["address"],
            country="Colombia",
        )
        db.session.add(client)
        db.session.flush()

        # Referencias y codeudores
        for r_info in c_def.get("references", []):
            db.session.add(Reference(
                client_id=client.id,
                full_name=r_info["name"],
                relationship=r_info.get("rel", "Referencia"),
                phone=r_info.get("phone", ""),
                identification_number=r_info.get("id_num", ""),
                address=r_info.get("address", ""),
            ))

        # Préstamo y amortización
        l_info = c_def["loan"]
        loan = Loan(
            code=l_info["code"],
            client_id=client.id,
            principal=Decimal(str(l_info["principal"])),
            annual_rate=Decimal(str(l_info["annual_rate"])),
            installments_count=l_info["installments"],
            frequency_days=l_info["freq"],
            amortization_type="frances",
            start_date=l_info["start_date"],
            status="mora" if l_info.get("is_overdue") else "activo",
        )
        db.session.add(loan)
        db.session.flush()

        # Generar cuotas de amortización
        schedule = calculate_schedule(
            loan.principal,
            loan.annual_rate,
            loan.installments_count,
            loan.start_date,
            loan.frequency_days,
            loan.amortization_type,
        )
        obligations = []
        for s in schedule:
            ob = Obligation(
                loan_id=loan.id,
                number=s["number"],
                due_date=s["due_date"],
                scheduled_value=s["scheduled_value"],
                capital=s["capital"],
                interest=s["interest"],
                pending_capital=s["capital"],
                pending_interest=s["interest"],
                status="pendiente",
            )
            db.session.add(ob)
            obligations.append(ob)
        db.session.flush()

        # Registrar pagos históricos aplicados
        paid_count = l_info.get("paid_installments", 0)
        for i in range(paid_count):
            ob = obligations[i]
            pay_val = float(ob.scheduled_value)
            payment = Payment(
                code=f"PG-{payment_counter:05d}",
                client_id=client.id,
                loan_id=loan.id,
                amount=pay_val,
                payment_date=ob.due_date,
                concept=f"Pago cuota {ob.number}",
                receipt_number=f"REC-{payment_counter:04d}",
                status="aplicado",
                registered_by=admin_id,
            )
            db.session.add(payment)
            db.session.flush()

            ob.pending_capital = 0
            ob.pending_interest = 0
            ob.status = "pagada"
            ob.paid_date = ob.due_date

            db.session.add(PaymentApplication(
                payment_id=payment.id,
                obligation_id=ob.id,
                capital_applied=ob.capital,
                interest_applied=ob.interest,
            ))
            payment_counter += 1

        # Si está en mora
        if l_info.get("is_overdue") and len(obligations) > 1:
            obligations[1].status = "vencida"

        # Adjuntar documentos reales de muestra para cada cliente
        # Fachada
        db.session.add(Document(
            entity_type="cliente",
            entity_id=client.id,
            doc_type="fachada",
            original_name=f"Foto_Fachada_{client.code}.jpeg",
            stored_name="WhatsApp Image 2026-08-20 at 12.03.10 PM.jpeg",
            extension="jpeg",
            size=261003,
            uploaded_by=admin_id,
        ))
        # Cédula / Identificación
        db.session.add(Document(
            entity_type="cliente",
            entity_id=client.id,
            doc_type="identificacion",
            original_name=f"Cedula_Ciudadania_{client.identification_number}.jpg",
            stored_name="CC.jpg",
            extension="jpg",
            size=32139,
            uploaded_by=admin_id,
        ))
        # Comprobante / Pagaré
        db.session.add(Document(
            entity_type="cliente",
            entity_id=client.id,
            doc_type="pagaré",
            original_name=f"Pagare_Firmado_{l_info['code']}.pdf",
            stored_name="cc3.pdf",
            extension="pdf",
            size=375205,
            uploaded_by=admin_id,
        ))

    # Gestiones de cobranza para demostrar alertas y compromisos
    c7 = Client.query.filter_by(code="CL-00007").first()
    if c7 and c7.loans:
        db.session.add(CollectionManagement(
            client_id=c7.id,
            loan_id=c7.loans[0].id,
            obligation_id=c7.loans[0].obligations[1].id if len(c7.loans[0].obligations) > 1 else None,
            action="llamada",
            notes="Llamada de gestión de cobro: Cliente informa retraso en nómina y establece compromiso de pago para este viernes.",
            next_date=date(2026, 8, 28),
            created_by=admin_id,
        ))

    c2 = Client.query.filter_by(code="CL-00002").first()
    if c2 and c2.loans and len(c2.loans[0].obligations) > 2:
        db.session.add(CollectionManagement(
            client_id=c2.id,
            loan_id=c2.loans[0].id,
            obligation_id=c2.loans[0].obligations[2].id,
            action="mensaje",
            notes="Recordatorio automático de vencimiento de cuota enviado por WhatsApp.",
            next_date=date(2026, 8, 27),
            created_by=admin_id,
        ))

    db.session.add(Audit(
        user_id=admin_id,
        action="Carga de cartera demo 3M",
        entity="Sistema",
        details="Generados 10 clientes con cartera activa de $3,000,000 COP y trazabilidad quincenal/mensual",
    ))

    db.session.commit()


def seed_parameters():
    """Inserta/actualiza parámetros conservando los valores ya configurados."""
    existing = {p.key: p for p in Parameter.query.all()}
    for key, value, category, kind, description in PARAMETERS:
        if key in existing:
            param = existing[key]
            param.description = description
            param.category = category
            param.kind = kind
        else:
            db.session.add(Parameter(
                key=key, value=value, category=category, kind=kind, description=description,
            ))
    db.session.commit()


def seed_parameters():
    """Inserta/actualiza parámetros conservando los valores ya configurados."""
    existing = {p.key: p for p in Parameter.query.all()}
    for key, value, category, kind, description in PARAMETERS:
        if key in existing:
            param = existing[key]
            param.description = description
            param.category = category
            param.kind = kind
        else:
            db.session.add(Parameter(
                key=key, value=value, category=category, kind=kind, description=description,
            ))
    db.session.commit()

