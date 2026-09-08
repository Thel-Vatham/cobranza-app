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

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `SECRET_KEY` | Clave criptográfica para firmas de sesión (obligatoria en prod) | Valor de desarrollo |
| `DATABASE_URL` | Cadena de conexión (SQLite local / PostgreSQL en producción) | `sqlite:///cartera.db` |
| `UPLOAD_FOLDER` | Directorio de almacenamiento de documentos privados | `app/uploads` (o `/data/uploads`) |
| `AUTH_DISABLED` | Bypass de autenticación para modo demostración (`true` / `false`) | `false` si hay `DATABASE_URL` |

## 5. Despliegue en producción

1. **Configurar variables críticas**:
   - `AUTH_DISABLED=false`
   - `SECRET_KEY`: generar una cadena aleatoria y segura de al menos 32 caracteres.
   - `DATABASE_URL`: URI de PostgreSQL (`postgresql://usuario:pass@host:5432/bd`) o ruta persistente de SQLite (`sqlite:////data/cartera.db`).
2. **Servidor WSGI de producción**:
   Ejecutar mediante Gunicorn con timeout ajustado para operaciones intensivas (OCR / exports):
   ```bash
   gunicorn -w 2 -t 120 run:app
   # o alternativamente:
   gunicorn -w 2 -t 120 wsgi:app
   ```
3. **Persistencia de archivos y base de datos**:
   - En plataformas como **Render**, usar un **Persistent Disk** montado en `/data` (definido en `render.yaml`), apuntando `DATABASE_URL=sqlite:////data/cartera.db` y `UPLOAD_FOLDER=/data/uploads`.
4. **Habilitar HTTPS**:
   - Forzar TLS mediante proxy inverso (Nginx, Traefik o el enrutador PaaS).
5. **Estrategia de copias de seguridad**:
   - Descarga periódica de respaldos comprensibles en formato ZIP/CSV desde el panel de administración (`/admin/exportar-csv`).
   - Respaldo del directorio de subidas (`uploads`) o del disco persistente.

## 6. Pruebas y verificación

Ejecutar la suite de pruebas unitarias y de integración del sistema:

```bash
python -m unittest tests.test_smoke -v
```

La prueba valida: autenticación de usuario, ciclo de vida de clientes, creación de préstamo con cronograma de cuotas y redondeo `ROUND_HALF_UP`, aplicación transaccional de pagos, recibo oficial, consultas de reportes y auditoría.
