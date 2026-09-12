# 💳 Cartera — Plataforma de Gestión de Cartera, Microcréditos y Cobranza

Aplicación web empresarial para la administración integral de carteras de microcréditos dolarizados (USD), expedientes de clientes, control de obligaciones, cobranza en terreno, asesoría financiera y trazabilidad contable de pagos.

---

## 🌟 Visión y Enfoque de Negocio

El sistema implementa una arquitectura rigurosa orientada a entidades crediticias y operadores de cobranza, asegurando:
- **Operación 100% Dolarizada (USD $)**: Todas las transacciones, saldos, carteras y pagos operan en dólares.
- **Tasa Fija Parametrizable (20%)**: El administrador configura en caliente la tasa de interés periódica (por defecto 20.00%).
- **Montos Predefinidos de Préstamo**: Catálogo estandarizado de montos ($75, $100, $125, $150 USD) modificable, ampliable o reducible por el Administrador desde el panel de parámetros.
- **Modalidades de Vencimiento**:
  - **Semanal**: El cobro se realiza exactamente a los 7 días calendario del desembolso (`fecha de solicitud + 7 días`).
  - **Quincenal (3 Ciclos Fijos)**: Cortes programados **5-20**, **10-25** y **15-30** con sugerencia predictiva automática según el día de la solicitud.
- **Cascada Transaccional de Pagos (Waterfall Logic)**:
  - Cualquier abono realizado por el cliente cubre en primera instancia el 100% de los intereses pendientes.
  - El saldo remanente se destina a amortizar el capital insoluto.
  - En amortizaciones parciales $(X - Z)$, el siguiente corte calcula intereses únicamente sobre el nuevo saldo de capital remanente.
- **Aislamiento Multi-Cartera (Portfolios)**:
  - Cada cartera es un silo cerrado con capital asignado en USD por el Administrador y vinculada a un operador responsable.
  - Los clientes, préstamos e historiales de pago no se cruzan ni se comparten entre carteras.
  - Los operadores pueden gestionar múltiples carteras alternando entre ellas desde la barra superior de navegación.
- **Expediente Digital del Cliente (Sin "Hojas de Vida")**:
  - Ficha técnica y crediticia integral con exactamente 2 referencias/codeudores obligatorios.
  - 4 evidencias fotográficas y documentales auditadas: Foto del Deudor, Foto del Trabajo, Foto de Fachada Domiciliaria y Documento de Identificación (Cédula).
- **Módulo de Asesoría / Consultoría**:
  - Botón directo "Enviar a Asesor" para clientes en mora o de cobranza compleja.
  - Rol exclusivo **`Consulta`**: el asesor dispone de una interfaz blindada que contiene únicamente su bandeja de notificaciones y el panel de clientes remitidos (con foto, contacto, score crediticio, estado de mora, capital adeudado e intereses pendientes).

---

## 🚀 Puesta en Marcha Rápida

### Requisitos
- Python 3.10, 3.11 o superior
- Pip y Entorno Virtual (`venv`)

### Instalación y Ejecución Local (Windows / PowerShell)

```powershell
# 1. Clonar o acceder a la carpeta del proyecto
cd cobranza

# 2. Activar el entorno virtual
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar el servidor
python run.py
```

Acceso web: **<http://localhost:5000>**

---

## 👥 Credenciales de Demostración

Al iniciar por primera vez, el sistema autosembra la estructura de datos, carteras, roles y usuarios predeterminados:

| Perfil | Usuario | Contraseña | Alcance Operativo |
|---|---|---|---|
| **Administrador** | `admin` | `09300` | Control total, carteras globales, parámetros USD, auditoría y usuarios |
| **Operador de Cobranza** | `user_0` | `09300` | Operación de cartera asignada, clientes, préstamos y recaudos |
| **Asesor / Consultor** | `consultor_0` | `09300` | Dashboard exclusivo de clientes remitidos, mora y notificaciones |

---

## 💼 Flujos de Trabajo Principales

### 1. Gestión de Carteras (Portfolios)
- El **Administrador** ingresa a `/carteras` para dar de alta una nueva cartera, asignarle un cupo de capital en dólares (ej. `$2,500.00 USD`) y asignar al operador de cobranza responsable.
- El **Operador** visualiza en la cabecera la cartera en la que se encuentra trabajando y puede conmutar instantáneamente entre sus diferentes carteras asignadas.

### 2. Alta de Crédito y Plan de Cobro
1. Se registra el cliente con sus datos laborales, cuentas bancarias duales (desembolso y recaudo), 2 referencias y las 4 fotos del expediente.
2. Desde la ficha del cliente, se selecciona **Nuevo Préstamo**:
   - Se selecciona uno de los montos autorizados ($75, $100, $125, $150 USD) o se ingresa monto personalizado.
   - Se selecciona modalidad: **Semanal** (cobro a 7 días) o **Quincenal** (Ciclos 5-20, 10-25, 15-30).
   - El sistema calcula la cuota con la tasa fija configurada (20%) y genera el plan de pagos exigible.

### 3. Recaudo y Aplicación de Pagos
- Al registrar un pago en `/pagos/nuevo`:
  - El monto recibido se imputa inmediatamente a saldar los intereses acumulados.
  - El excedente reduce el saldo de capital del préstamo.
  - Se genera un recibo digital oficial imprimible en PDF con código transaccional trazable (`PG-XXXXX`).

### 4. Remisión y Asesoría
- Desde el expediente del cliente (`/clientes/<id>`), si el cliente incurre en mora o requiere acompañamiento especial, el operador o administrador presiona **Enviar a Asesor**, seleccionando el motivo y registrando instrucciones operativas.
- El asesor (`consultor_0`) recibe una notificación interna y visualiza al cliente en su panel de `/asesor/` con indicadores de scoring, mora y saldo insoluto para ejecutar la gestión de recuperación.

### 5. Panel Principal (Dashboard) e Indicadores de Cartera
Desde la pantalla de inicio (`/`), el sistema presenta los 4 indicadores financieros clave de la cartera activa:
- **Saldo de Cartera**: Cupo total de capital asignado a la cartera en dólares (`assigned_capital_usd`).
- **Cartera Vigente (Al día)**: Capital en curso sin mora que cumple su cronograma de pago.
- **Cartera Vencida (En mora)**: Saldo insoluto vencido de cuotas cuya fecha límite ha expirado.
- **Interés generado este mes**: Utilidad neta generada exclusivamente por créditos pagados (liquidados al 100%) en los últimos 30 días.
- **Tablas de Monitoreo**: Listado de próximos vencimientos (con búsqueda textual por nombre o cédula), créditos en mora y últimos pagos registrados.

---

## 🧪 Pruebas y Control de Calidad

El proyecto incluye una suite exhaustiva de pruebas unitarias y de integración que validan el 100% de la lógica de negocio:

```powershell
# Ejecutar todas las suites de pruebas unificadas
.venv\Scripts\python -m unittest discover tests -v

# Pruebas específicas del módulo de Carteras y Asesor
.venv\Scripts\python -m unittest tests.test_carteras_and_advisor -v

# Batería de auditoría integral end-to-end (84 comprobaciones)
.venv\Scripts\python tests/test_audit_full.py
```

---

## 📚 Documentación Técnica Especializada

Toda la documentación técnica se encuentra centralizada y estructurada en la carpeta [`docs/`](docs/):

1. [**Arquitectura Técnica y Modelo de Datos** (`docs/ARQUITECTURA_TECNICA.md`)](docs/ARQUITECTURA_TECNICA.md):
   - Diagrama entidad-relación (ER), modelos relacionales y estructura multi-cartera.
   - Especificación matemática del motor financiero dolarizado y fórmulas de cascada de pagos.
   - Seguridad, RBAC, matriz de permisos y pistas de auditoría inmutables.
   - Motor de scoring crediticio (0-100) y procesamiento OCR (EasyOCR y PyMuPDF).

2. [**Guía de Despliegue y Operaciones** (`docs/DESPLIEGUE_Y_OPERACIONES.md`)](docs/DESPLIEGUE_Y_OPERACIONES.md):
   - Despliegue con Blueprint en **Render** (con disco persistente automático).
   - Despliegue en **PythonAnywhere**, contenedores Docker y servidores dedicados.
   - Variables de entorno de producción, gestión de copias de seguridad (ZIP/CSV) y mantenimiento.
