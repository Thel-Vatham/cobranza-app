from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.relationship(
        "Permission", secondary=role_permissions, backref="roles", lazy="selectin"
    )
    users = db.relationship("User", backref="role", lazy="selectin")

    def has_permission(self, code):
        return any(p.code == code for p in self.permissions)


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    full_name = db.Column(db.String(160))
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"))
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, code):
        if not self.role or not self.active:
            return False
        if self.role.name == "Administrador":
            return True
        return self.role.has_permission(code)


class Client(db.Model):
    __tablename__ = "clients"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    identification_type = db.Column(db.String(30), default="CC")
    identification_number = db.Column(db.String(60), nullable=False, index=True)
    country = db.Column(db.String(80), default="Colombia")
    address = db.Column(db.String(255))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    # Datos bancarios para desembolso / depósito
    bank_name = db.Column(db.String(100), nullable=True)
    account_type = db.Column(db.String(40), nullable=True)  # Ahorros, Corriente, Billetera Digital, etc.
    account_number = db.Column(db.String(60), nullable=True)
    account_holder = db.Column(db.String(160), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    references = db.relationship("Reference", backref="client", lazy="selectin", cascade="all, delete-orphan")
    loans = db.relationship("Loan", backref="client", lazy="selectin")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Reference(db.Model):
    __tablename__ = "references"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    relationship = db.Column(db.String(60))  # Referencia / Codeudor
    identification_number = db.Column(db.String(60))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(255))


class Loan(db.Model):
    __tablename__ = "loans"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    principal = db.Column(db.Numeric(14, 2), nullable=False)
    annual_rate = db.Column(db.Numeric(8, 4), nullable=False, default=0)  # e.g. 0.24 = 24%
    installments_count = db.Column(db.Integer, nullable=False)
    frequency_days = db.Column(db.Integer, default=30)
    amortization_type = db.Column(db.String(20), default="frances")  # frances | aleman
    start_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="activo")  # activo | pagado | mora | cancelado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    obligations = db.relationship(
        "Obligation", backref="loan", lazy="selectin",
        order_by="Obligation.number", cascade="all, delete-orphan",
    )
    payments = db.relationship("Payment", backref="loan", lazy="selectin")

    @property
    def outstanding_balance(self):
        return sum((o.pending_balance for o in self.obligations), 0.0)


class Obligation(db.Model):
    __tablename__ = "obligations"
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    scheduled_value = db.Column(db.Numeric(14, 2), nullable=False)
    capital = db.Column(db.Numeric(14, 2), nullable=False)
    interest = db.Column(db.Numeric(14, 2), nullable=False)
    pending_capital = db.Column(db.Numeric(14, 2), nullable=False)
    pending_interest = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(20), default="pendiente")  # pendiente | pagada | parcial | vencida
    paid_date = db.Column(db.Date)

    applications = db.relationship("PaymentApplication", backref="obligation", lazy="selectin")

    @property
    def pending_balance(self):
        return float(self.pending_capital or 0) + float(self.pending_interest or 0)

    @property
    def days_late(self):
        if self.status in ("pagada",):
            return 0
        today = datetime.utcnow().date()
        if self.due_date and self.due_date < today:
            return (today - self.due_date).days
        return 0


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    concept = db.Column(db.String(120))
    receipt_number = db.Column(db.String(40))
    status = db.Column(db.String(20), default="aplicado")  # aplicado | anulado
    registered_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", lazy="selectin")
    registered_user = db.relationship("User", lazy="selectin")
    applications = db.relationship(
        "PaymentApplication", backref="payment", lazy="selectin", cascade="all, delete-orphan"
    )


class PaymentApplication(db.Model):
    __tablename__ = "payment_applications"
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    obligation_id = db.Column(db.Integer, db.ForeignKey("obligations.id"), nullable=False)
    capital_applied = db.Column(db.Numeric(14, 2), default=0)
    interest_applied = db.Column(db.Numeric(14, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False)  # cliente | prestamo | pago
    entity_id = db.Column(db.Integer, nullable=False)
    doc_type = db.Column(db.String(60))  # identificacion | contrato | comprobante | ...
    original_name = db.Column(db.String(255))
    stored_name = db.Column(db.String(255), nullable=False)
    extension = db.Column(db.String(20))
    size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_user = db.relationship("User", lazy="selectin")
    ocr_results = db.relationship(
        "OCRResult", backref="document", lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def path(self):
        from flask import current_app
        import os
        return os.path.join(current_app.config["UPLOAD_FOLDER"], self.stored_name)


class OCRResult(db.Model):
    __tablename__ = "ocr_results"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    extracted_text = db.Column(db.Text)
    fields_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CollectionManagement(db.Model):
    __tablename__ = "collection_management"
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"))
    obligation_id = db.Column(db.Integer, db.ForeignKey("obligations.id"))
    action = db.Column(db.String(120), nullable=False)  # llamada, visita, mensaje, acuerdo
    notes = db.Column(db.Text)
    next_date = db.Column(db.Date)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", lazy="selectin")
    loan = db.relationship("Loan", lazy="selectin")
    obligation = db.relationship("Obligation", lazy="selectin")
    user = db.relationship("User", lazy="selectin")


class Audit(db.Model):
    __tablename__ = "audit"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(120), nullable=False)
    entity = db.Column(db.String(80))
    entity_id = db.Column(db.String(80))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", lazy="selectin")


class Parameter(db.Model):
    __tablename__ = "parameters"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(255))
    description = db.Column(db.String(255))
    category = db.Column(db.String(80), default="generales")
    kind = db.Column(db.String(20), default="text")  # text | number | boolean

    @staticmethod
    def get(key, default=None):
        p = db.session.query(Parameter).filter_by(key=key).first()
        return p.value if p else default

    @staticmethod
    def get_float(key, default=0.0):
        try:
            return float(Parameter.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def get_int(key, default=0):
        try:
            return int(float(Parameter.get(key, default)))
        except (TypeError, ValueError):
            return default
