# 04 · API y rutas

Todas las rutas están protegidas por `@login_required` y, cuando corresponde, por
`@permission_required("codigo.permiso")`. Los formularios usan `POST` y siguen el
patrón PRG (Post/Redirect/Get).

## 1. Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| GET/POST | `/login` | Inicio de sesión |
| GET | `/logout` | Cierre de sesión |

## 2. Panel principal

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard con indicadores |

## 3. Clientes

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/clientes/` | Listado con búsqueda |
| POST | `/clientes/ocr` | Autocompletado: recibe documento y devuelve campos sugeridos (JSON) |
| GET/POST | `/clientes/nuevo` | Crear cliente (acepta documentos de identidad y fachada) |
| GET | `/clientes/<id>` | Ficha integral |
| GET/POST | `/clientes/<id>/editar` | Editar cliente |
| POST | `/clientes/<id>/documentos` | Asociar documento al cliente |

## 4. Préstamos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/prestamos/` | Listado con filtros de estado |
| GET/POST | `/prestamos/nuevo` | Crear préstamo, amortización y subir comprobante de desembolso |
| GET | `/prestamos/<id>` | Detalle integral con cronograma de cuotas, desembolso y pagos |
| POST | `/prestamos/<id>/comprobante` | Adjuntar o actualizar el comprobante de desembolso bancario |

## 5. Pagos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/pagos/` | Listado general de pagos |
| GET/POST | `/pagos/nuevo` | Registrar y aplicar pago transaccional (acepta comprobante) |
| GET | `/pagos/<id>/recibo` | Recibo oficial ejecutivo con diseño limpio para impresión y PDF |
| POST | `/pagos/<id>/anular` | Anular pago y restaurar saldos de cuotas transaccionalmente |
| POST | `/pagos/<id>/comprobante` | Adjuntar o actualizar comprobante a un pago existente |

## 6. Cobranza

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/cobranza/` | Obligaciones vencidas con semaforización de mora |
| GET/POST | `/cobranza/gestion/<obligacion_id>` | Registrar gestión de cobro (llamada, visita, mensaje, acuerdo) |
| GET | `/cobranza/gestiones` | Historial cronológico de gestiones |

## 7. Documentos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/documentos/` | Listado general de documentos clasificados |
| GET/POST | `/documentos/subir` | Carga de archivo con nomenclatura trazable |
| GET | `/documentos/<id>/descargar` | Descarga segura del archivo |
| GET/POST | `/documentos/<id>/ocr` | Procesamiento OCR (EasyOCR / PyMuPDF) y visualización |
| POST | `/documentos/<id>/editar` | Editar metadatos (tipo de documento y entidad) |
| POST | `/documentos/<id>/reemplazar` | Reemplazar el archivo físico invalidando OCR previo |
| POST | `/documentos/<id>/eliminar` | Eliminar documento físico y su registro |

## 8. Reportes

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reportes/cartera` | Indicadores consolidados y distribución por estado |
| GET | `/reportes/score` | Panel de análisis de riesgo con tarjetas métricas y scoring |

## 9. Administración y Gestión de datos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/usuarios` | Listado de usuarios del sistema |
| GET/POST | `/admin/usuarios/nuevo` | Crear usuario con asignación de rol |
| GET/POST | `/admin/usuarios/<id>/editar` | Editar usuario, estado y contraseña |
| GET | `/admin/roles` | Matriz de roles y permisos RBAC |
| POST | `/admin/roles/<id>` | Actualizar permisos asignados a un rol |
| GET/POST | `/admin/parametros` | Parámetros del sistema y guardado masivo en caliente |
| POST | `/admin/parametros/nuevo` | Registrar nuevo parámetro de configuración |
| GET | `/admin/auditoria` | Bitácora de eventos y trazabilidad del sistema |
| GET | `/admin/datos` | Panel de exportación de copias de seguridad y purga de base de datos |
| GET | `/admin/exportar-csv` | Exportación completa a ZIP con archivos CSV amigables para Excel |
| POST | `/admin/borrar-datos` | Purga segura de datos operativos (conserva usuarios y configuración) |
| POST | `/admin/cargar-demo` | Recarga de datos de demostración limpios |

## 10. Filtros de plantilla

| Filtro | Ejemplo | Resultado |
|---|---|---|
| `money` | `{{ 1000|money }}` | `$1,000.00` |
| `d` | `{{ fecha|d }}` | `19/08/2026` |
| `pct` | `{{ 0.24|pct }}` | `24.00%` |
