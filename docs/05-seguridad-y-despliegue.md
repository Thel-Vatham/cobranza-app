# 05 · Seguridad y despliegue

## 1. Autenticación y autorización

- Autenticación mediante **Flask-Login** con sesiones del lado del servidor.
- Contraseñas con hash seguro (**Werkzeug**, PBKDF2). Nunca se almacenan en claro.
- Autorización por **roles y permisos**:

| Rol | Descripción |
|---|---|
| Administrador | Acceso total a todos los módulos |
| Operador de cobranza | Operación completa de clientes, préstamos, pagos, cobranza y documentos |
| Consulta | Solo lectura |

- Los permisos se validan por código (ej. `clients.create`) mediante el decorador
  `@permission_required`.

### 1.1 Modo sin autenticación (desarrollo)

`app/config.py` expone `AUTH_DISABLED = True`, que auto-conecta al usuario
administrador para facilitar el desarrollo del prototipo. **Debe fijarse en
`False` antes de producción.**

## 2. Protección de la información

- Archivos cargados en `app/uploads/`, fuera del árbol de archivos estáticos.
  Nunca se sirven directamente; solo a través de la ruta de descarga protegida.
- Validación de extensión (`ALLOWED_EXTENSIONS`) y tamaño máximo (15 MB por defecto).
- Separación entre archivos públicos (`static/`) y privados (`uploads/`).
- Nombre de archivo aleatorio (`uuid4`) para evitar colisiones y path traversal.

## 3. Auditoría

Cada operación crítica registra en la tabla `audit`:

- Fecha/hora
- Usuario
- Acción
- Entidad afectada y referencia
- Detalle

Operaciones auditadas: inicio/cierre de sesión, creación/edición de clientes,
préstamos, registro y anulación de pagos, gestiones de cobranza, carga de
documentos, cambios de roles y parámetros.

## 4. Configuración por ambiente

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave de sesión (obligatoria en producción) |
| `SQLALCHEMY_DATABASE_URI` | Cadena de conexión a base de datos |
| `UPLOAD_FOLDER` | Carpeta de archivos privados |

## 5. Despliegue en producción

1. Establecer `AUTH_DISABLED = False` y cambiar la contraseña del administrador.
2. Configurar `SECRET_KEY` mediante variable de entorno.
3. Migrar la base de datos a **PostgreSQL** o **MySQL** (SQLAlchemy lo soporta sin
   cambios en el modelo).
4. Servir con un WSGI de producción (p. ej. **Gunicorn** en Linux):
   ```bash
   gunicorn -w 4 run:app
   ```
5. Habilitar **HTTPS** (proxy inverso o certificado TLS).
6. Configurar **copias de seguridad** de la base de datos y de `app/uploads/`.

## 6. Pruebas

Ejecutar la prueba integral:

```bash
python -m unittest tests.test_smoke -v
```

La prueba cubre: autenticación, creación de cliente, préstamo con 12 cuotas,
aplicación de pago, generación de recibo y consulta de reportes y administración.
