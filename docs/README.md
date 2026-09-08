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
| [06-despliegue-render.md](06-despliegue-render.md) | Guía paso a paso para publicar en Render (blueprint con disco persistente o PostgreSQL). |
| [07-despliegue-pythonanywhere.md](07-despliegue-pythonanywhere.md) | Guía para publicar el demo en PythonAnywhere (SQLite persistente). |
| [08-manual-tecnico.md](08-manual-tecnico.md) | Manual técnico exhaustivo de referencia (arquitectura, modelos, motor financiero, flujos, OCR y despliegue). |

## Referencia rápida

- **Stack**: Python 3.10+, Flask 3, Flask-SQLAlchemy 3, Flask-Login, SQLite / PostgreSQL.
- **Frontend**: Servido por backend (Jinja2) con HTML5, CSS3 y JavaScript modular.
- **Arquitectura**: Web ligera (server-rendered) con estricta separación por capas (presentación, aplicación, dominio, persistencia).
- **Persistencia**: SQLite local / persistente en disco Render (`/data/cartera.db`) o PostgreSQL en producción.
- **Motor financiero**: Amortización francesa y alemana, tasas por período, orden de imputación configurable (`interes_primero` / `capital_primero`).
- **Gestión documental y OCR**: PyMuPDF + EasyOCR con preprocesamiento adaptativo de imágenes.
- **Administración de datos**: Exportación consolidada a formato ZIP con múltiples CSVs amigables para Excel, purga segura y recarga de datos demo.
