# Despliegue en PythonAnywhere (demo funcional)

PythonAnywhere es la opción más rápida para publicar este proyecto como demo
funcional sin necesidad de PostgreSQL: en su tier gratuito **el sistema de
archivos persiste**, por lo que la base SQLite (`app/cartera.db`) y la carpeta
`app/uploads/` se mantienen entre reinicios.

## 1. Crear cuenta y entorno

1. Regístrate en [pythonanywhere.com](https://www.pythonanywhere.com).
2. Ve a la pestaña **Consoles** → abre una **Bash**.
3. Crea un entorno virtual (usa la versión de Python que aparezca, p. ej. 3.12):
   ```bash
   mkvirtualenv --python=python3.12 cartera
   ```

## 2. Subir el proyecto

Opciones:

- **Con Git** (recomendado):
  ```bash
  git clone https://github.com/tu_usuario/tu_repo.git cartera
  ```
- **Manual**: usa la pestaña **Files** → **Upload** para subir los archivos, o
  arrástralos (sin la carpeta `.venv`).

## 3. Instalar dependencias

```bash
cd ~/cartera
pip install -r requirements.txt
```

> `psycopg2-binary` se instalará sin problema; no es necesario tener PostgreSQL.
> Si prefieres no instalarlo, puedes comentar esa línea, pero no afecta el demo.

## 4. Crear la web app

1. Ve a la pestaña **Web** → **Add a new web app**.
2. Elige **Manual configuration** (no "Flask" automático, para usar tu virtualenv).
3. Selecciona la versión de Python 3.12.

## 5. Configurar el WSGI

1. En la pestaña **Web**, busca el enlace al **archivo WSGI** y ábrelo.
2. Sustituye su contenido por el de `wsgi.py` (ajusta `tu_usuario` a tu usuario):
   ```python
   import sys
   import os

   project_home = "/home/tu_usuario/cartera"
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   from run import app as application
   ```
3. Guarda el archivo.

## 6. Asignar el virtualenv

1. En la pestaña **Web**, en **Virtualenv**, escribe la ruta:
   ```
   /home/tu_usuario/.virtualenvs/cartera
   ```
2. (Si usaste `mkvirtualenv`, esa es la ruta típica.)

## 7. Mapear archivos estáticos

En la pestaña **Web**, añade un **Static Files** mapping:

| URL | Directory |
|---|---|
| `/static/` | `/home/tu_usuario/cartera/app/static/` |

## 8. Recargar y probar

1. Pulsa **Reload** en la pestaña Web.
2. Abre tu dominio: `https://tu_usuario.pythonanywhere.com`

## 9. Acceso

Por defecto, sin `DATABASE_URL`, el demo arranca **sin login** (acceso directo).
Si quieres exigir usuario/contraseña, descomenta en el WSGI:

```python
os.environ["AUTH_DISABLED"] = "false"
```

y recarga. Credenciales iniciales: `admin` / `admin123` (cámbiala al entrar).

## Notas

- La base de datos se crea sola en el primer arranque (`app/cartera.db`).
- Los documentos subidos quedan en `app/uploads/` (persiste en PythonAnywhere).
- Para actualizar el demo: haz `git pull` en la consola y pulsa **Reload**.
