import os
import shutil
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import (
    User,
    Role,
    Permission,
    Portfolio,
    Parameter,
    Client,
    Loan,
    Obligation,
    Payment,
    PaymentApplication,
    ClientReferral,
    Notification,
    Document,
    Reference,
    Audit
)

def clean_database():
    app = create_app()
    with app.app_context():
        print("\n" + "=" * 60)
        print("  LIMPIANDO BASE DE DATOS PARA PRODUCCIÓN")
        print("=" * 60)

        # 1. Purgar todas las tablas operativas
        deleted_pay_apps = PaymentApplication.query.delete()
        deleted_payments = Payment.query.delete()
        deleted_obligations = Obligation.query.delete()
        deleted_loans = Loan.query.delete()
        deleted_references = Reference.query.delete()
        deleted_referrals = ClientReferral.query.delete()
        deleted_clients = Client.query.delete()
        deleted_notifications = Notification.query.delete()
        deleted_documents = Document.query.delete()
        deleted_audits = Audit.query.delete()
        db.session.commit()

        print(f"  • Pagos y Aplicaciones eliminados: {deleted_payments + deleted_pay_apps}")
        print(f"  • Obligaciones eliminadas:         {deleted_obligations}")
        print(f"  • Préstamos eliminados:            {deleted_loans}")
        print(f"  • Clientes y referencias borrados: {deleted_clients + deleted_references}")
        print(f"  • Documentos y auditorías purgados:{deleted_documents + deleted_audits}")

        # 2. Limpiar carpeta de archivos subidos de prueba (uploads)
        upload_dir = app.config.get("UPLOAD_FOLDER")
        if upload_dir and os.path.exists(upload_dir):
            cleared_files = 0
            for item in os.listdir(upload_dir):
                item_path = os.path.join(upload_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        cleared_files += 1
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        cleared_files += 1
                except Exception as e:
                    pass
            print(f"  • Archivos temporales eliminados:  {cleared_files}")

        # 3. Garantizar Cartera Principal Activa
        portfolio = Portfolio.query.first()
        if not portfolio:
            portfolio = Portfolio(
                name="Cartera Principal USD",
                code="CART-001",
                assigned_capital_usd=Decimal("50000.00"),
                currency="USD",
                status="activa"
            )
            db.session.add(portfolio)
            db.session.commit()
            print("  • Cartera Principal USD creada y lista.")
        else:
            portfolio.status = "activa"
            db.session.commit()
            print(f"  • Cartera activa verificada: {portfolio.name} ({portfolio.code})")

        # 4. Verificar usuarios y roles
        admin = User.query.filter_by(username="admin").first()
        if admin:
            admin.status = "activo"
            db.session.commit()
            print("  • Usuario Administrador listo: 'admin' (Contraseña: 09300)")

        user_0 = User.query.filter_by(username="user_0").first()
        if user_0:
            user_0.status = "activo"
            db.session.commit()
            print("  • Usuario Operador listo:      'user_0' (Contraseña: 09300)")

        # 5. Parámetros del sistema
        default_params = {
            "tasa_interes_periodo": ("20.0", "Tasa fija por período (20% quincenal)"),
            "montos_prestamo_disponibles": ("75, 100, 125, 150", "Montos predefinidos en USD"),
            "orden_aplicacion_pago": ("interes_primero", "Orden de prelación de abonos"),
            "frecuencias_permitidas": ("quincenal", "Frecuencias habilitadas en préstamos"),
            "ciclos_quincenales": ("5-20, 10-25, 15-30", "Cortes quincenales oficiales"),
        }
        for k, (v, desc) in default_params.items():
            param = Parameter.query.filter_by(key=k).first()
            if not param:
                param = Parameter(key=k, value=v, description=desc)
                db.session.add(param)
            else:
                param.value = v
        db.session.commit()
        print("  • Parámetros del sistema listos y verificados.")

        print("=" * 60)
        print("  SISTEMA 100% LIMPIO Y LISTO PARA REGISTRAR DATOS REALES")
        print("  Clientes actuales:  ", Client.query.count())
        print("  Préstamos actuales: ", Loan.query.count())
        print("  Pagos actuales:     ", Payment.query.count())
        print("=" * 60 + "\n")

if __name__ == "__main__":
    clean_database()
