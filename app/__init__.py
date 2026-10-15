"""Configuración de la aplicación y arranque de extensiones (Application Factory)."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Se carga el .env antes de leer cualquier variable de entorno.
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

BASE_DIR = Path(__file__).resolve().parent.parent


def normalize_database_url(raw_url: str) -> str:
    """Adapta una DATABASE_URL de Supabase/Heroku al formato que espera SQLAlchemy.

    - Convierte el prefijo heredado ``postgres://`` en ``postgresql://``.
    - Fuerza ``sslmode=require`` en PostgreSQL (Supabase exige TLS).
    - En el *Transaction pooler* de Supabase (puerto 6543) desactiva el cache de
      prepared statements, ya que ese pooler no las soporta.
    """
    url = (raw_url or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL no está definida en el entorno ni en el archivo .env")

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        # SQLite (desarrollo local) u otro driver: se devuelve tal cual.
        return url

    try:
        port = parsed.port
    except ValueError:  # puerto no numérico
        port = None

    query = dict(parse_qsl(parsed.query))
    query.setdefault("sslmode", "require")
    if port == 6543:
        query.setdefault("options", "-c statement_cache_size=0")

    return urlunparse(parsed._replace(query=urlencode(query)))


def _is_production() -> bool:
    return bool(os.getenv("VERCEL")) or os.getenv("FLASK_ENV") == "production"


def _default_database_uri() -> str:
    """Cadena de conexión a usar.

    Si `DATABASE_URL` no está definida **en producción**, la aplicación falla
    aquí y de forma inmediata en lugar deIntentarse conectar a nada.

    Antes caía en silencio a un SQLite local y en Vercel terminaba con un
    críptico "sqlite3.OperationalError: no se puede abrir el archivo de la
    base de datos", porque el sistema de archivos de las funciones es de solo
    lectura. Peor aún, el error sólo aparecía en la primera petición que
    escribiera en la base de datos: las páginas de login devolvían 200 y la
    aplicación parecía funcionar.

    En desarrollo se mantiene el SQLite local para no depender de PostgreSQL
    al empezar a trabajar.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return normalize_database_url(url)

    if _is_production():
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL.\n\n"
            "La aplicacion esta ejecutandose en un entorno de produccion "
            "(Vercel detectado) y necesita la cadena de conexion de "
            "PostgreSQL/Supabase.\n\n"
            "Configurala en Vercel -> Project Settings -> Environment "
            "Variables, con este formato:\n"
            "    DATABASE_URL=postgresql://usuario:contrasena@host:puerto/base\n\n"
            "El fallback a SQLite solo se permite en desarrollo local."
        )

    # Desarrollo: SQLite dentro de ./instance para no depender de PostgreSQL.
    instance_path = BASE_DIR / "instance"
    instance_path.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(instance_path / 'dev.db').as_posix()}"


def _engine_options() -> dict:
    """Ajustes del pool de SQLAlchemy.

    En un backend persistente (Railway, Fly, una VM) un pool normal va bien.
    En Vercel cada instancia es una función serverless: una app pequeña puede
    despertar decenas de instancias a la vez, y el pool por defecto de
    SQLAlchemy (5 conexiones + 10 de desbordamiento) agotaría muy rápido el
    límite de conexiones de Supabase. Por eso ahí se limita a una conexión y
    se recorta el desbordamiento a cero.

    `pool_pre_ping` y `pool_recycle` evitan además los errores de "stale
    connection", típicos cuando el runtime congela una función entre peticiones.

    Los parámetros de tamaño sólo aplican a QueuePool. SQLite usa StaticPool
    o SingletonThreadPool y rechaza `pool_size`, `max_overflow` y
    `pool_timeout`, así que se omiten si la base no es un servidor real.
    """
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    uri = os.getenv("DATABASE_URL") or ""
    is_sqlite = uri.startswith("sqlite")
    if _is_production() and not is_sqlite:
        options.update(pool_size=1, max_overflow=0, pool_timeout=10)
    return options


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    JSON_SORT_KEYS = False


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para continuar."
    login_manager.login_message_category = "info"

    # --- Blueprints -------------------------------------------------------
    from .health import health_bp
    from .routes import auth_bp, main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)

    # --- Import de modelos (necesario para Flask-Migrate y flask shell) ----
    from . import models  # noqa: F401

    # --- user_loader de Flask-Login ---------------------------------------
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # --- CSRF + helpers de plantilla --------------------------------------
    from .helpers import register_date_helpers
    from .security import register_csrf_protection

    register_csrf_protection(app)
    register_date_helpers(app)

    # --- Filtros de eventos de SQLAlchemy ---------------------------------
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover
        """Activa las foreign keys en SQLite (vienen desactivadas por defecto)."""
        if type(dbapi_connection).__module__.startswith("sqlite3"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return app