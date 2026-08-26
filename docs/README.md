# Documentación técnica — Cartera

Sistema de Gestión de Cartera y Cobranza.

## Índice

| Documento | Contenido |
|---|---|
| [01-documento-tecnico.md](01-documento-tecnico.md) | Especificación general, arquitectura y módulos funcionales. |
| [02-modelo-de-datos.md](02-modelo-de-datos.md) | Entidades, relaciones, esquema y diccionario de datos. |
| [03-motor-financiero.md](03-motor-financiero.md) | Reglas de cálculo, aplicación de pagos y ejemplos numéricos. |
| [04-api-y-rutas.md](04-api-y-rutas.md) | Endpoints HTTP por módulo. |
| [05-seguridad-y-despliegue.md](05-seguridad-y-despliegue.md) | Autenticación, autorización, auditoría y puesta en producción. |
| [06-despliegue-render.md](06-despliegue-render.md) | Guía paso a paso para publicar en Render + PostgreSQL. |
| [07-despliegue-pythonanywhere.md](07-despliegue-pythonanywhere.md) | Guía para publicar el demo en PythonAnywhere (SQLite persistente). |

## Referencia rápida

- **Stack**: Python 3.10+, Flask 3, Flask-SQLAlchemy 3, Flask-Login, SQLite.
- **Arquitectura**: web ligera (server-rendered) con separación por capas.
- **Persistencia**: SQLite por defecto (`app/cartera.db`).
- **Motor financiero**: amortización francesa (cuota fija), centralizado en `app/services/financial.py`.
