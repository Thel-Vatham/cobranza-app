# 🚀 Guía de Despliegue y Operaciones — Cartera

> **Manual de Operaciones y Puesta en Producción**  
> Instrucciones paso a paso para desplegar la aplicación en Render, PythonAnywhere o servidores dedicados (Gunicorn/Nginx), gestión de volúmenes persistentes, variables de entorno y copias de seguridad.

---

## 1. Requisitos de Infraestructura y Entorno

- **Runtime**: Python 3.10, 3.11 o superior.
- **Memoria RAM Mínima**: 512 MB (1 GB recomendado si se habilita OCR con EasyOCR).
- **Almacenamiento**: Disco persistente para SQLite y carga de documentos (`UPLOAD_FOLDER`).
- **Servidor de Producción WSGI**: Gunicorn (Linux) o Waitress (Windows Server).

---

## 2. Variables de Entorno del Sistema

Configurar las siguientes variables en el entorno de producción (o en el gestor de secretos del proveedor de nube).

> 🔒 **REGLA DE SEGURIDAD**: Nunca expongas credenciales en repositorios ni modifiques archivos `.env` directamente en producción.

| Variable | Descripción | Valor por Defecto | Ejemplo Producción |
|---|---|---|---|
| `SECRET_KEY` | Llave criptográfica para firmas de sesión y CSRF | Aleatoria efímera | `f8a93...b2c` (64 hex chars) |
| `DATABASE_URL` | URI de conexión SQLAlchemy | `sqlite:///app/cartera.db` | `postgresql://user:pass@host:5432/cartera` |
| `UPLOAD_FOLDER` | Directorio en disco para almacenamiento de fotos/PDFs | `app/uploads` | `/data/uploads` |
| `AUTH_DISABLED` | Forzar autenticación estricta | `false` | `false` |
| `SESSION_COOKIE_SECURE` | Cookies transmitidas exclusivamente por HTTPS | `false` | `true` |
| `SESSION_COOKIE_HTTPONLY` | Mitigación XSS en cookies de sesión | `true` | `true` |
| `PORT` | Puerto de escucha del servicio web | `5000` | `10000` |

---

## 3. Despliegue en Render (Recomendado con Blueprint)

El repositorio incluye el archivo [render.yaml](file:///c:/Users/Area%20Tecnica%20Summa/Documents/cobranza/render.yaml) configurado para desplegar con **Persistent Disk** automático.

### Paso a Paso:
1. Inicia sesión en [Render.com](https://render.com).
2. Haz clic en **New +** → **Blueprint**.
3. Selecciona el repositorio del proyecto `cobranza-app`.
4. Render detectará automáticamente `render.yaml`:
   - Montará el disco persistente de 1 GB (`cartera-data`) en `/data`.
   - Establecerá `DATABASE_URL: sqlite:////data/cartera.db`.
   - Establecerá `UPLOAD_FOLDER: /data/uploads`.
   - Asignará una `SECRET_KEY` criptográfica autogenerada.
5. Haz clic en **Apply**. El build y arranque se completarán en aproximadamente 2 minutos.

### Despliegue con PostgreSQL Gestionado en Render:
Si deseas usar PostgreSQL en lugar de SQLite:
1. Crea una base de datos en **New +** → **PostgreSQL**.
2. En el Web Service de Render, agrega la variable de entorno `DATABASE_URL` vinculada a la base de datos creada.

---

## 4. Despliegue en PythonAnywhere

1. **Crear Web App**:
   - En el Dashboard de PythonAnywhere, dirígete a la pestaña **Web** → **Add a new web app**.
   - Selecciona **Manual configuration** y elige **Python 3.11**.
2. **Clonar e Instalar Dependencias**:
   - Abre una consola Bash en PythonAnywhere:
     ```bash
     git clone <URL_DEL_REPOSITORIO> ~/cobranza
     cd ~/cobranza
     python3.11 -m venv .venv
     source .venv/bin/activate
     pip install --upgrade pip
     pip install -r requirements.txt
     ```
3. **Configurar el archivo WSGI**:
   - Edita el archivo de configuración WSGI generado por PythonAnywhere y añade:
     ```python
     import sys, os
     path = os.path.expanduser('~/cobranza')
     if path not in sys.path:
         sys.path.insert(0, path)

     from run import app as application
     ```
4. **Recargar la Aplicación**:
   - Haz clic en **Reload <tu-usuario>.pythonanywhere.com**.

---

## 5. Inicialización de Datos y Primer Acceso

Al arrancar por primera vez, el sistema inicializa automáticamente la base de datos (`app/__init__.py` y `app/seed.py`):
- Tablas relacionales completas.
- Roles nativos (`Administrador`, `Operador de cobranza`, `Consulta`).
- Catálogo de 19 permisos del sistema.
- Cartera inicial por defecto ("Cartera Principal USD" con $1,500 USD de cupo).
- Parámetros dolarizados (tasa 20%, montos permitidos 75, 100, 125, 150 USD).

### Credenciales Sembradas:
| Perfil | Usuario | Contraseña | Alcance / Vistas |
|---|---|---|---|
| **Administrador** | `admin` | `09300` | Acceso global, carteras, usuarios, parámetros y auditoría |
| **Operador** | `user_0` | `09300` | Cartera activa asignada, creación de créditos, cobro |
| **Asesor / Consultor** | `consultor_0` | `09300` | Panel exclusivo de clientes remitidos y notificaciones |

> ⚠️ **RECOMENDACIÓN**: Cambiar las contraseñas en el primer inicio de sesión desde el módulo de administración de usuarios.

---

## 6. Procedimientos de Respaldo y Mantenimiento

### Respaldo de Base de Datos y Documentos
1. **Exportación Integrada**: Desde el panel de administración (`/admin/exportar-csv`), descarga un archivo ZIP con todos los datos tabulares en CSV.
2. **Copia Física de Archivos**:
   - Base de datos: respaldar el archivo `cartera.db` (o dump de PostgreSQL con `pg_dump`).
   - Expedientes: respaldar el directorio `uploads/` que almacena fotografías y documentos en PDF.
