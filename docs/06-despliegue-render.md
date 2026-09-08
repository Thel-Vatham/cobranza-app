# Despliegue en Render (Persistent Disk / PostgreSQL)

Este documento explica cómo desplegar **Cartera** en Render asegurando persistencia de datos (base de datos y documentos subidos) y rendimiento óptimo.

## 1. Requisitos previos

- Cuenta en [Render](https://render.com).
- Repositorio del proyecto subido a GitHub/GitLab.
- Los archivos `Procfile`, `render.yaml` y `requirements.txt` ya están configurados en el repositorio.

## 2. Configuración preconfigurada en `render.yaml`

El archivo `render.yaml` incluye la especificación de infraestructura completa:
- **Runtime**: Python 3.10+
- **Build command**: `pip install -r requirements.txt`
- **Start command**: `gunicorn -w 2 -t 120 run:app`
- **Disco persistente**: Un volumen de 1 GB (`cartera-data`) montado en `/data`.
- **Variables automáticas**:
  - `DATABASE_URL: sqlite:////data/cartera.db` (base de datos persistente en disco).
  - `UPLOAD_FOLDER: /data/uploads` (documentos y comprobantes persistentes en disco).
  - `AUTH_DISABLED: false` (fuerza inicio de sesión en producción).
  - `SECRET_KEY`: generada aleatoriamente por Render.

## 3. Pasos de despliegue

### Opción A — Blueprint con Disco Persistente (Recomendada, cero configuración manual)

1. En el panel de Render, haz clic en **New +** → **Blueprint**.
2. Conecta tu repositorio `cobranza-app`.
3. Render detectará automáticamente `render.yaml`, aprovisionará el servicio web y adjuntará el disco persistente `cartera-data`.
4. Haz clic en **Apply**. El build y arranque se completarán en unos minutos.

### Opción B — Despliegue con PostgreSQL Gestionado

Si prefieres usar la base de datos PostgreSQL administrada de Render en lugar de SQLite persistente:

1. **Crear PostgreSQL**: Haz clic en **New +** → **PostgreSQL**.
2. **Crear Web Service**: Haz clic en **New +** → **Web Service** y conecta el repositorio.
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 2 -t 120 run:app`
3. En la pestaña **Environment** del Web Service:
   - Añade `DATABASE_URL` (enlazando la base de datos PostgreSQL creada).
   - Añade `SECRET_KEY` (cadena secreta de producción).
   - Añade `AUTH_DISABLED=false`.

## 4. Primer inicio de sesión

En el primer despliegue la aplicación inicializa automáticamente:
- Estructura de tablas, roles predefinidos, catálogo de permisos y parámetros del sistema.
- Usuario administrador inicial:
  - **Usuario**: `admin`
  - **Contraseña**: `admin123`

> ⚠️ **IMPORTANTE**: Cambia la contraseña del administrador inmediatamente tras el primer ingreso desde **Administración → Usuarios → Editar**.

## 5. Persistencia y Respaldo

- **Con Blueprint (`render.yaml`)**: Tanto la base de datos SQLite como la carpeta `/data/uploads` están montadas en el disco persistente `cartera-data`, manteniéndose intactas tras cada nuevo despliegue o reinicio de contenedor.
- **Copias de seguridad**: Puedes descargar respaldos integrales en formato ZIP/CSV en cualquier momento desde **Administración → Gestión de datos** (`/admin/exportar-csv`).

## 6. Verificación local con Gunicorn

Para comprobar localmente el funcionamiento con Gunicorn antes de desplegar:

```bash
pip install -r requirements.txt
gunicorn -w 2 -t 120 run:app
```

Abre <http://127.0.0.1:8000> en tu navegador.
