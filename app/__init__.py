"""Cartera · Sistema de gestión de cartera y cobranza. Desarrollado por AVRORA TECH."""
import os

from flask import Flask
from flask_login import current_user, login_user

from .config import Config
from .extensions import db, login_manager, csrf, limiter


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Debe iniciar sesión para continuar."
    login_manager.login_message_category = "warning"

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def _auto_login():
        from flask import request as flask_req
        if app.config.get("AUTH_DISABLED") and not current_user.is_authenticated:
            if flask_req.endpoint and flask_req.endpoint.startswith("auth."):
                return
            user = (
                User.query.filter_by(username="admin").first()
                or User.query.filter_by(username="user_0").first()
                or User.query.first()
            )
            if user:
                login_user(user)

    # Blueprints
    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.clients import bp as clients_bp
    from .routes.loans import bp as loans_bp
    from .routes.payments import bp as payments_bp
    from .routes.collections import bp as collections_bp
    from .routes.documents import bp as documents_bp
    from .routes.reports import bp as reports_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    @app.template_filter("money")
    def money_filter(value):
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return "$0.00"

    @app.template_filter("d")
    def date_filter(value):
        if not value:
            return "—"
        return value.strftime("%d/%m/%Y")

    @app.template_filter("pct")
    def pct_filter(value):
        try:
            return f"{float(value) * 100:.2f}%"
        except (TypeError, ValueError):
            return "0%"

    from flask import render_template

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", code=403, message="No tiene permisos para realizar esta acción."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="El recurso solicitado no existe."), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Error interno 500: {e}", exc_info=True)
        return render_template("error.html", code=500, message="Ha ocurrido un error interno en el servidor. Por favor intente nuevamente."), 500

    with app.app_context():
        db.create_all()
        _ensure_columns()
        _deduplicate_references()
        from .seed import seed_if_empty, seed_parameters
        seed_if_empty()
        seed_parameters()
        _deduplicate_references()

    return app


def _deduplicate_references():
    """Elimina referencias duplicadas para un mismo cliente automáticamente."""
    try:
        from .models import Reference
        seen = set()
        to_delete = []
        for ref in Reference.query.order_by(Reference.id.asc()).all():
            key = (ref.client_id, ref.full_name.strip().upper(), (ref.identification_number or "").strip(), (ref.relationship or "").strip())
            if key in seen:
                to_delete.append(ref.id)
            else:
                seen.add(key)
        if to_delete:
            Reference.query.filter(Reference.id.in_(to_delete)).delete(synchronize_session=False)
            db.session.commit()
    except Exception:
        db.session.rollback()


def _ensure_columns():
    """Migración liviana para agregar columnas nuevas a tablas existentes."""
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    if "parameters" in table_names:
        cols = {c["name"] for c in inspector.get_columns("parameters")}
        with db.engine.begin() as conn:
            if "category" not in cols:
                conn.exec_driver_sql("ALTER TABLE parameters ADD COLUMN category VARCHAR(80)")
            if "kind" not in cols:
                conn.exec_driver_sql("ALTER TABLE parameters ADD COLUMN kind VARCHAR(20) DEFAULT 'text'")

    if "clients" in table_names:
        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        with db.engine.begin() as conn:
            if "city" not in client_cols:
                conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN city VARCHAR(80)")
            if "bank_name" not in client_cols:
                conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN bank_name VARCHAR(100)")
            if "account_type" not in client_cols:
                conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN account_type VARCHAR(40)")
            if "account_number" not in client_cols:
                conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN account_number VARCHAR(60)")
            if "account_holder" not in client_cols:
                conn.exec_driver_sql("ALTER TABLE clients ADD COLUMN account_holder VARCHAR(160)")
