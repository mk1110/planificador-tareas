"""Modelos SQLAlchemy: User y Task."""

from __future__ import annotations

import enum
import re
from datetime import date, datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


def utcnow() -> datetime:
    """Timestamp UTC *naive* para que se comporte igual en SQLite y PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# --- Enumeraciones ---------------------------------------------------------
class Category(str, enum.Enum):
    LABORAL = "laboral"
    COTIDIANA = "cotidiana"
    MEDICA = "medica"


class Timeframe(str, enum.Enum):
    SEMANAL = "semanal"
    MENSUAL = "mensual"


def _enum_column(enum_cls, name: str):
    """Columna Enum que guarda el *valor* ('laboral') y no el nombre del miembro."""
    return db.Column(
        db.Enum(
            enum_cls,
            name=name,
            values_callable=lambda enum_type: [member.value for member in enum_type],
            validate_strings=True,
        ),
        nullable=False,
    )


# --- User ------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    tasks = db.relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    # -- Contraseña (nunca se almacena en texto plano) ----------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # -- Validaciones de negocio -------------------------------------------
    @staticmethod
    def validate_username(username: str) -> str | None:
        """Devuelve un mensaje de error o ``None`` si el usuario es válido."""
        username = (username or "").strip()
        if not username:
            return "El nombre de usuario es obligatorio."
        if not USERNAME_RE.match(username):
            return (
                "El nombre de usuario debe tener entre 3 y 30 caracteres "
                "y solo letras, números, punto, guion o guion bajo."
            )
        return None

    @staticmethod
    def validate_email(email: str) -> str | None:
        email = normalize_email(email)
        if not email:
            return "El correo electrónico es obligatorio."
        if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", email):
            return "Introduce un correo electrónico válido."
        return None

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<User {self.username}>"


# --- Task ------------------------------------------------------------------
class Task(db.Model):
    __tablename__ = "tasks"
    __table_args__ = (
        # `length()` existe en PostgreSQL y en SQLite (a diferencia de char_length).
        CheckConstraint("length(title) >= 1", name="ck_tasks_title_not_empty"),
        Index("ix_tasks_user_due", "user_id", "due_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = _enum_column(Category, "task_category")
    timeframe = _enum_column(Timeframe, "task_timeframe")
    due_date = db.Column(db.Date, nullable=True, index=True)
    completed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="tasks")

    # -- Utilidades ---------------------------------------------------------
    @property
    def is_overdue(self) -> bool:
        return bool(self.due_date and not self.completed and self.due_date < date.today())

    @property
    def is_due_today(self) -> bool:
        return bool(self.due_date and not self.completed and self.due_date == date.today())

    def toggle(self) -> None:
        self.completed = not self.completed

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        state = "x" if self.completed else " "
        return f"<Task {state} [{self.category.value}] {self.title!r}>"