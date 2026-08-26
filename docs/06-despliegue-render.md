# Despliegue en Render + PostgreSQL

Este documento explica cómo publicar **Cartera** en Render con una base de datos
PostgreSQL persistente.

## 1. Requisitos previos

- Cuenta en [Render](https://render.com).
- Repositorio del proyecto subido a GitHub/GitLab.
- Los archivos `Procfile`, `render.yaml` y `requirements.txt` ya están en el proyecto.

## 2. Configuración ya aplicada

- `app/config.py` lee la conexión desde la variable de entorno `DATABASE_URL`.
  Si no existe, usa SQLite local (ideal para desarrollo).
- Si `DATABASE_URL` está definida (producción), el acceso directo sin login se
  desactiva automáticamente (`AUTH_DISABLED=false`). Se puede forzar con la
  variable `AUTH_DISABLED`.
- `render.yaml` declara el servicio y genera una `SECRET_KEY` automáticamente.

## 3. Pasos de despliegue

### Opción A — Blueprint (recomendada, usa `render.yaml`)

1. En Render, ve a **New → Blueprint**.
2. Conecta tu repositorio.
3. Render detecta `render.yaml` y crea el servicio web.
4. Cuando el servicio esté creado, ve a su pestaña **Environment** y crea la
   base de datos PostgreSQL (botón **Create PostgreSQL**). Render enlazará la
   variable `DATABASE_URL` automáticamente.

### Opción B — Creación manual

1. **New → Web Service** y conecta el repositorio.
2. Configura:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn run:app`
3. **New → PostgreSQL** y crea la instancia.
4. En el web service, agrega la variable `DATABASE_URL` (Render la autocompleta
   al enlazar la instancia) y `SECRET_KEY` (valor largo y aleatorio).

## 4. Primer inicio de sesión

En el primer despliegue la aplicación crea automáticamente:

- Las tablas (roles, permisos, usuarios, etc.).
- El usuario administrador:
  - Usuario: `admin`
  - Contraseña: `admin123`

> ⚠️ **Cambia la contraseña del administrador inmediatamente** después de entrar
> (Administración → Usuarios → Editar).

## 5. Limitaciones a tener en cuenta

- **Archivos cargados**: `app/uploads/` es efímero en Render (se pierde en cada
  deploy). Para producción se recomienda almacenamiento en la nube (S3, Cloudinary,
  u otro). La base de datos (metadatos) sí persiste.
- **SQLite local**: en tu máquina sigue funcionando sin cambios.
- **Vercel**: no es recomendable para este proyecto (serverless + Flask de larga
  duración). Render es la opción adecuada.

## 6. Verificación local

Para comprobar que la app arranca con gunicorn localmente:

```bash
pip install -r requirements.txt
gunicorn run:app
```

Abre http://127.0.0.1:8000 (puerto por defecto de gunicorn).
