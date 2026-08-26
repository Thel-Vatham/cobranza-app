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

- **Autenticación**: login/logout, sesiones, hash de contraseñas (Werkzeug).
- **Panel principal**: indicadores de cartera, obligaciones por vencer y vencidas, pagos recientes.
- **Clientes**: CRUD, referencias y codeudores, ficha integral con score.
- **Préstamos**: creación con valor, interés, cuotas y fecha; generación de obligaciones.
- **Cuotas / obligaciones**: capital, interés, saldo pendiente, días de mora, estado.
- **Pagos**: registro transaccional, aplicación (interés primero, luego capital), recibo imprimible, anulación.
- **Cobranza**: reporte de vencidos y registro de gestiones.
- **Documentos**: carga segura con nomenclatura interna trazable (por cliente/entidad, tipo y fecha), clasificación, descarga y OCR (EasyOCR + PyMuPDF) para autocompletar datos del cliente.
- **Cartera y analítica**: indicadores y distribución por estado.
- **Score de comportamiento**: puntualidad, cumplimiento y mora (pesos parametrizables).
- **Administración**: usuarios, roles, permisos, parámetros y auditoría.

## Motor financiero

El cálculo de cuotas usa **amortización francesa (cuota fija)**:

```
i = tasa_anual / 12
cuota = principal * i / (1 - (1 + i)^-n)
```

Reglas centralizadas en `app/services/financial.py`, listas para pruebas
(ver `tests/`). El orden de aplicación del pago es: interés pendiente primero,
luego capital, de la obligación más antigua a la más reciente.

## Estructura

```
app/
  routes/         # controladores HTTP por módulo
  services/       # lógica de negocio (financiera, scoring, permisos)
  models.py       # entidades y relaciones
  templates/      # vistas HTML
  static/         # CSS y JavaScript
  seed.py         # datos iniciales (roles, permisos, admin)
run.py
requirements.txt
```

## Documentación técnica

Documentación formal del sistema en [`docs/`](docs/):

- `docs/01-documento-tecnico.md` — especificación, arquitectura y módulos.
- `docs/02-modelo-de-datos.md` — entidades, relaciones y esquema.
- `docs/03-motor-financiero.md` — reglas de cálculo y ejemplos.
- `docs/04-api-y-rutas.md` — endpoints por módulo.
- `docs/05-seguridad-y-despliegue.md` — seguridad, auditoría y puesta en producción.

## Notas de seguridad

- Cambia `SECRET_KEY` y la contraseña del admin antes de producción.
- Usa HTTPS en producción.
- Los archivos cargados se almacenan en `app/uploads/` (privados, no se sirven directamente).
