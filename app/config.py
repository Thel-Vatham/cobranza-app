import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "si"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cartera-dev-secret-cambiar-en-produccion")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _as_bool(
        os.environ.get("SESSION_COOKIE_SECURE"),
        default=bool(os.environ.get("RENDER")),
    )
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Base de datos: en producción se usa DATABASE_URL (PostgreSQL en Render).
    # En desarrollo local se mantiene SQLite como respaldo.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "cartera.db"),
    )
    # Render entrega DATABASE_URL con prefijo "postgres://"; SQLAlchemy requiere "postgresql://".
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        **({"connect_args": {"timeout": 30}} if "sqlite" in SQLALCHEMY_DATABASE_URI else {}),
    }

    # Autenticación: login estricto respetando sesión de admin y user_0
    AUTH_DISABLED = _as_bool(
        os.environ.get("AUTH_DISABLED"),
        default=False,
    )
    RATELIMIT_ENABLED = _as_bool(
        os.environ.get("RATELIMIT_ENABLED"),
        default=False,
    )

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB

    ALLOWED_EXTENSIONS = {
        "png", "jpg", "jpeg", "gif", "webp", "pdf",
        "doc", "docx", "xls", "xlsx", "txt", "csv",
    }
