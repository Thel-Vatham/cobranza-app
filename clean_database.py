"""
Script para purgar y dejar la base de datos limpia y lista para producción / uso real.
Elimina todos los datos de prueba y bots:
- Clientes y referencias
- Préstamos y obligaciones
- Pagos y aplicaciones
- Notificaciones y remisiones
- Gestiones de cobranza y documentos
- Archivos residuales en app/uploads/

Conserva intactos:
- Usuarios del sistema (admin, user_0, consultor_0)
- Roles y permisos
- Parámetros de configuración (USD, tasa fija, etc.)
- Cartera principal
"""
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app import create_app
from app.extensions import db
from app.models import (
    Audit,
    Client,
    ClientReferral,
    CollectionManagement,
    Document,
    Loan,
    Notification,
    Obligation,
    OCRResult,
    Payment,
    PaymentApplication,
    Portfolio,
    Reference,
    User,
)
from app.services.financial import log_audit


def clean_database():
    app = create_app()
    with app.app_context():
        print("\n🧹 INICIANDO LIMPIEZA DE BASE DE DATOS Y DATOS DE PRUEBA...")

        # 1. Contar registros actuales antes de borrar
        p_apps_count = PaymentApplication.query.count()
        payments_count = Payment.query.count()
        obligations_count = Obligation.query.count()
        loans_count = Loan.query.count()
        clients_count = Client.query.count()
        refs_count = Reference.query.count()
        docs_count = Document.query.count()
        notifs_count = Notification.query.count()
        refs_advisor_count = ClientReferral.query.count()

        # 2. Eliminación respetando llaves foráneas
        PaymentApplication.query.delete()
        Payment.query.delete()
        Obligation.query.delete()
        CollectionManagement.query.delete()
        OCRResult.query.delete()
        Document.query.delete()
        Reference.query.delete()
        ClientReferral.query.delete()
        Notification.query.delete()
        Loan.query.delete()
        Client.query.delete()

        admin_user = User.query.filter_by(username="admin").first()
        admin_id = admin_user.id if admin_user else None
        log_audit(admin_id, "Purga completa de datos de prueba y bots", "Sistema", details="Base de datos preparada para uso real")
        db.session.commit()

        # 3. Limpiar carpeta app/uploads de archivos temporales
        uploads_dir = os.path.join(app.root_path, "uploads")
        cleaned_files = 0
        if os.path.exists(uploads_dir):
            for root, dirs, files in os.walk(uploads_dir, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        cleaned_files += 1
                    except Exception as e:
                        print(f"No se pudo eliminar {file_path}: {e}")
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.rmdir(dir_path)
                    except Exception:
                        pass

        # 4. Asegurar que las carpetas base existan vacías
        os.makedirs(os.path.join(uploads_dir, "cliente"), exist_ok=True)
        os.makedirs(os.path.join(uploads_dir, "prestamo"), exist_ok=True)

        print("✔ Pagos y aplicaciones eliminados:", payments_count + p_apps_count)
        print("✔ Préstamos y obligaciones eliminados:", loans_count + obligations_count)
        print("✔ Clientes y referencias eliminados:", clients_count + refs_count)
        print("✔ Remisiones y notificaciones eliminadas:", refs_advisor_count + notifs_count)
        print("✔ Documentos y archivos eliminados:", docs_count + cleaned_files)

        # 5. Resumen final del estado del sistema
        print("\n" + "=" * 60)
        print("  ESTADO ACTUAL DEL SISTEMA (LISTO PARA PRODUCCIÓN)")
        print("=" * 60)
        print(f"  • Clientes:       {Client.query.count()} (Limpio)")
        print(f"  • Préstamos:      {Loan.query.count()} (Limpio)")
        print(f"  • Obligaciones:   {Obligation.query.count()} (Limpio)")
        print(f"  • Pagos:          {Payment.query.count()} (Limpio)")
        print(f"  • Notificaciones: {Notification.query.count()} (Limpio)")
        print(f"  • Carteras:       {Portfolio.query.count()} (Activa: 'Cartera Principal USD')")
        print(f"  • Usuarios:       {User.query.count()} (admin, user_0, consultor_0)")
        print("=" * 60)
        print("\n✨ ¡La aplicación está totalmente limpia y lista para ser utilizada!")


if __name__ == "__main__":
    clean_database()
