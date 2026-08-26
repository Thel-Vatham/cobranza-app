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
| GET | `/prestamos/` | Listado con filtros |
| GET/POST | `/prestamos/nuevo` | Crear préstamo y generar obligaciones |
| GET | `/prestamos/<id>` | Detalle con cuotas y pagos |

## 5. Pagos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/pagos/` | Listado |
| GET/POST | `/pagos/nuevo` | Registrar y aplicar pago (acepta comprobante) |
| GET | `/pagos/<id>/recibo` | Recibo imprimible |
| POST | `/pagos/<id>/anular` | Anular pago y restaurar saldos |
| POST | `/pagos/<id>/comprobante` | Adjuntar comprobante a un pago existente |

## 6. Cobranza

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/cobranza/` | Obligaciones vencidas |
| GET/POST | `/cobranza/gestion/<obligacion_id>` | Registrar gestión |
| GET | `/cobranza/gestiones` | Historial |

## 7. Documentos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/documentos/` | Listado |
| GET/POST | `/documentos/subir` | Carga de archivo |
| GET | `/documentos/<id>/descargar` | Descarga |
| GET/POST | `/documentos/<id>/ocr` | OCR y validación |
| POST | `/documentos/<id>/editar` | Editar metadatos (tipo y entidad) |
| POST | `/documentos/<id>/reemplazar` | Reemplazar el archivo |
| POST | `/documentos/<id>/eliminar` | Eliminar el documento |

## 8. Reportes

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reportes/cartera` | Indicadores y distribución |
| GET | `/reportes/score` | Score por cliente |

## 9. Administración

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/usuarios` | Listado de usuarios |
| GET/POST | `/admin/usuarios/nuevo` | Crear usuario |
| GET/POST | `/admin/usuarios/<id>/editar` | Editar usuario |
| GET | `/admin/roles` | Roles y permisos |
| POST | `/admin/roles/<id>` | Guardar permisos de un rol |
| GET | `/admin/parametros` | Parámetros del sistema (agrupados por categoría) |
| POST | `/admin/parametros/nuevo` | Crear parámetro |
| GET | `/admin/auditoria` | Registro de auditoría |

## 10. Filtros de plantilla

| Filtro | Ejemplo | Resultado |
|---|---|---|
| `money` | `{{ 1000|money }}` | `$1,000.00` |
| `d` | `{{ fecha|d }}` | `19/08/2026` |
| `pct` | `{{ 0.24|pct }}` | `24.00%` |
