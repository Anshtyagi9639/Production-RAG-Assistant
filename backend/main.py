"""ASGI entry point for Vercel (`"entrypoint": "main:app"` in the root vercel.json).

Vercel loads a module-level `app` variable. `app.main` builds its app lazily so importing it
needs no configuration (tests rely on that); this module builds it eagerly instead. Local
development keeps using `uvicorn app.main:app`.
"""

from app.main import create_app

app = create_app()
