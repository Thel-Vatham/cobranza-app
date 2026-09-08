# Cartera — Sistema de Gestión de Cartera y Cobranza

Prototipo final de un aplicativo web para la administración de clientes, préstamos,
obligaciones de pago, cartera, cobranza, recepción de pagos, gestión documental,
generación de comprobantes y análisis de comportamiento financiero.

Arquitectura ligera: **backend Python (Flask)** + **HTML/CSS/JavaScript**, con
separación de capas (presentación / aplicación / dominio / persistencia).

## Requisitos

- Python 3.10 o superior
- pip

## Instalación

```powershell
cd ruta\al\proyecto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Abre en el navegador: <http://localhost:5000>

## Credenciales de demostración

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | Administrador (acceso total) |

En la primera ejecución el sistema crea automáticamente la base de datos SQLite
(`app/cartera.db`), los roles, los permisos y el usuario administrador.

## Módulos implementados

- **Autenticación**: login/logout, sesiones seguras (Flask-Login), hash de contraseñas (Werkzeug).
- **Panel principal**: indicadores de cartera, obligaciones por vencer y vencidas, pagos recientes y filtros rápidos.
- **Clientes**: CRUD completo, referencias personales y codeudores, información bancaria para transferencias/desembolsos (banco, tipo de cuenta, número y titular), localización (ciudad/país), ficha integral con score crediticio.
- **Préstamos / Créditos**: creación con valor principal, tasa de interés por período parametrizable, cuotas y periodicidad; generación automática del plan de pagos y soporte de comprobante de desembolso (en alta o posterior).
- **Cuotas / Obligaciones**: amortización francesa (cuota fija) o alemana (capital fijo), control de capital, interés, saldo pendiente, días de mora y estado en tiempo real.
- **Pagos**: registro transaccional, orden de aplicación configurable (interés primero o capital primero), recibo ejecutivo con diseño oficial optimizado para impresión limpia y exportación a PDF, anulación y reversión transaccional completa.
- **Cobranza**: panel de obligaciones vencidas, semaforización de morosidad y registro cronológico de gestiones de cobro con próxima fecha de contacto.
- **Gestión documental**: almacenamiento seguro con nomenclatura física trazable (`{entidad}/{id}/{entidad}-{id}-{tipo}-{fecha}-{hash}`), clasificación, reemplazo, descarga y motor OCR (EasyOCR + PyMuPDF) para autocompletar clientes desde documento de identidad.
- **Cartera y analítica**: panel interactivo con métricas de capital colocado, recaudado, saldos pendientes y distribución por estado de crédito.
- **Score de comportamiento**: motor de calificación (0–100) basado en puntualidad, cumplimiento y días de mora, con panel de análisis de riesgo visual (tarjetas de métricas, barras de progreso y bandas de riesgo).
- **Administración y Gestión de Datos**:
  - Gestión de usuarios, roles (RBAC) y matriz de permisos granulares.
  - Parámetros del sistema editables en caliente (tasas, días de alerta, orden de pago, etc.).
  - Bitácora completa de auditoría de eventos sensibles.
  - **Exportación comprensible de base de datos**: descarga en archivo ZIP con múltiples archivos CSV limpios, formateados y legibles para Excel (clientes, préstamos, cronogramas, pagos, gestiones, etc.).
  - **Herramientas de datos**: purga segura de información transaccional de prueba y recarga de datos demo limpios.

## Motor financiero

El cálculo de cuotas soporta amortización francesa (cuota fija) y alemana (capital fijo), con operaciones exactas mediante `Decimal` (`ROUND_HALF_UP` a 2 decimales):

- **Amortización francesa**:
  ```
  cuota = principal * i / (1 - (1 + i)^-n)
  ```
- **Amortización alemana**:
  ```
  capital_fijo = principal / n
  cuota_k = capital_fijo + (saldo_{k-1} * i)
  ```

Reglas centralizadas en `app/services/financial.py`:
- **Tasa periódica**: parametrizable globalmente (`tasa_interes_periodo`), aplicada de forma determinística por cuota.
- **Orden de imputación transaccional**: configurable vía parámetro `orden_aplicacion_pago` entre **Interés primero** (`interes_primero`, estándar) y **Capital primero** (`capital_primero`).
- En la última cuota se absorbe cualquier residuo por redondeo para liquidar exactamente el saldo.

## Estructura del proyecto

```
app/
  routes/         # Controladores HTTP y Blueprints por módulo
  services/       # Lógica pura de negocio (financiera, scoring, OCR, documentos)
  models.py       # Entidades SQLAlchemy y relaciones del modelo
  templates/      # Plantillas Jinja2 y componentes visuales
  static/         # Hojas de estilo CSS, scripts JS y recursos
  seed.py         # Datos iniciales (roles, permisos, usuario admin, parámetros)
  config.py       # Configuración por entorno y variables
run.py            # Punto de entrada para desarrollo
wsgi.py           # Punto de entrada WSGI para servidores de producción
requirements.txt  # Dependencias del proyecto
render.yaml       # Configuración de despliegue con disco persistente en Render
Procfile          # Comando de ejecución en plataformas PaaS
docs/             # Documentación técnica exhaustiva
```

## Documentación técnica

La documentación formal y detallada del sistema se encuentra en [`docs/`](docs/):

- [`docs/01-documento-tecnico.md`](docs/01-documento-tecnico.md) — Especificación funcional, arquitectura y módulos.
- [`docs/02-modelo-de-datos.md`](docs/02-modelo-de-datos.md) — Entidades, relaciones, diccionario de datos y nomenclatura física.
- [`docs/03-motor-financiero.md`](docs/03-motor-financiero.md) — Reglas de cálculo, amortización, aplicación de pagos y scoring.
- [`docs/04-api-y-rutas.md`](docs/04-api-y-rutas.md) — Catálogo de endpoints HTTP por módulo y filtros de plantilla.
- [`docs/05-seguridad-y-despliegue.md`](docs/05-seguridad-y-despliegue.md) — Seguridad RBAC, auditoría y puesta en producción.
- [`docs/06-despliegue-render.md`](docs/06-despliegue-render.md) — Despliegue en Render con disco persistente y/o PostgreSQL.
- [`docs/07-despliegue-pythonanywhere.md`](docs/07-despliegue-pythonanywhere.md) — Despliegue del demo en PythonAnywhere con SQLite persistente.
- [`docs/08-manual-tecnico.md`](docs/08-manual-tecnico.md) — Manual técnico integral consolidado (referencia definitiva).

## Despliegue y notas de producción

- **Servidor WSGI**: Usar `gunicorn -w 2 -t 120 run:app` o `gunicorn wsgi:app`.
- **Render**: `render.yaml` preconfigura un disco persistente montado en `/data` para persistir tanto la base de datos SQLite (`sqlite:////data/cartera.db`) como los documentos cargados (`/data/uploads`).
- **Seguridad**:
  - Define `SECRET_KEY` segura y no predeterminada.
  - Desactiva el modo demo configurando `AUTH_DISABLED=false`.
  - Cambia la contraseña del usuario `admin` inmediatamente tras el primer despliegue.
  - Los archivos subidos se almacenan en `UPLOAD_FOLDER` de manera privada y solo se acceden mediante endpoints con control de permisos.
