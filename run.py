"""Punto de entrada de la aplicación.

Uso en desarrollo:
    python run.py

Producción (behind a un servidor WSGI como gunicorn uvicorn):
    gunicorn "run:app" --bind 0.0.0.0:$PORT
"""

import os

from app import create_app

app = create_app()


@app.shell_context_processor
def shell_context():
    from app import db
    from app.models import Task, User

    return {"db": db, "User": User, "Task": Task}


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )