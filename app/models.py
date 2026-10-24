"""Modelos SQLAlchemy: User, Task, finanzas y los del módulo de salud."""

from __future__ import annotations

import enum
import re
from datetime import date, datetime, time, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

# Letras de los días de la semana en el orden que usa `date.weekday()`
# (lunes = 0 ... domingo = 6). `Medication.days` guarda seven flags '0'/'1'.
WEEKDAY_INITIALS = "LMXJVSD"

# Factor de conversión glucemia: 1 mmol/L ≈ 18,018 mg/dL.
MGDL_PER_MMOL = 18.018


def utcnow() -> datetime:
    """Timestamp UTC *naive* para que se comporte igual en SQLite y PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    """Marca de tiempo *naive* en hora local, sin microsegundos.

    `utcnow()` se reserva para `created_at`, que es una marca de auditoría y no
    se muestra nunca. Las fechas que el usuario introduce y edita a mano
    (mediciones, tomas de medicación) se guardan en hora local para que el
    gráfico y la checklist muestren exactamente lo que escribió, sin
    desplazamientos por zona horaria.
    """
    return datetime.now().replace(microsecond=0)


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


class TransactionType(str, enum.Enum):
    SERVICIO = "servicio"
    GASTO = "gasto"
    INGRESO = "ingreso"


class GlucoseMoment(str, enum.Enum):
    """Momento de la medición de glucemia."""

    AYUNAS = "ayunas"
    ANTES_COMER = "antes_comer"
    DESPUES_COMER = "despues_comer"
    ANTES_DORMIR = "antes_dormir"
    OTRO = "otro"


class GlucoseUnit(str, enum.Enum):
    MGDL = "mgdl"
    MMOL = "mmol"


class IntakeStatus(str, enum.Enum):
    """Estado de una toma de medicación en el checklist diario."""

    PENDIENTE = "pendiente"
    TOMADO = "tomado"
    OMITIDO = "omitido"


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
    dinero_disponible = db.Column(db.Float, nullable=False, default=0.0)

    tasks = db.relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    # --- Módulo de salud ---------------------------------------------------
    # Borrar un usuario elimina también su historial clínico y su catálogo de
    # medicación (y, en cascada, las tomas registradas).
    bp_readings = db.relationship(
        "BloodPressureReading",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    glucose_readings = db.relationship(
        "GlucoseReading",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    medications = db.relationship(
        "Medication",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    medication_intakes = db.relationship(
        "MedicationIntake",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Finanzas -----------------------------------------------------------
    finance_services = db.relationship(
        "FinanceService",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Módulo de transacciones personales ----------------------------------
    expenses = db.relationship(
        "Expense",
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


# ===========================================================================
# Módulo de transacciones personales (gastos, ingresos, servicios)
# ===========================================================================
class Expense(db.Model):
    """Un gasto, ingreso o servicio registrado por un usuario."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expense_amount_positive"),
        Index("ix_expenses_user_date", "user_id", "date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = _enum_column(TransactionType, "expense_type")
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False, default=local_now)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="expenses")

    # -- Utilidades ---------------------------------------------------------
    @property
    def display_type(self) -> str:
        """Retorna 'Servicio', 'Gasto' o 'Ingreso' según el tipo."""
        return self.type.value.capitalize()

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<Expense {self.type.value} {self.amount} - {self.description or ''} @ {self.date}>"


# ===========================================================================
# Módulo de salud
# ===========================================================================
def parse_times(raw: str) -> list[time]:
    """Convierte ``"08:00, 14:30"`` en una lista de `datetime.time` ordenada.

    Devuelve una lista vacía si algún fragmento no tiene el formato ``HH:MM``
    o si la hora no existe (la validación de negocio vive en las rutas).
    """
    parsed: list[time] = []
    for chunk in (raw or "").split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            hour, minute = value.split(":")
            parsed.append(time(int(hour), int(minute)))
        except (ValueError, TypeError):
            return []
    return sorted(set(parsed))


def format_times(times: list[time]) -> str:
    """Inverso de `parse_times`: ``[time(8, 0)]`` → ``"08:00"``."""
    return ",".join(t.strftime("%H:%M") for t in sorted(times))


class BloodPressureReading(db.Model):
    """Una medición de tensión arterial."""

    __tablename__ = "blood_pressure_readings"
    __table_args__ = (
        # Rangos Ohm: por debajo de 50/30 mmHg o por encima de 300/200 es un
        # error de tecleo o una emergencia, no una medición habitual.
        CheckConstraint("systolic BETWEEN 50 AND 300", name="ck_bp_systolic_range"),
        CheckConstraint("diastolic BETWEEN 30 AND 200", name="ck_bp_diastolic_range"),
        CheckConstraint("pulse IS NULL OR pulse BETWEEN 20 AND 250", name="ck_bp_pulse_range"),
        Index("ix_bp_user_measured", "user_id", "measured_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    systolic = db.Column(db.Integer, nullable=False)
    diastolic = db.Column(db.Integer, nullable=False)
    pulse = db.Column(db.Integer, nullable=True)
    measured_at = db.Column(db.DateTime, nullable=False, default=local_now, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="bp_readings")

    @property
    def pressure(self) -> str:
        """``"120/80"``, la forma habitual de escribir una tensión."""
        return f"{self.systolic}/{self.diastolic}"

    @property
    def pulse_pressure(self) -> int | None:
        """Presión de pulso (sistólica − diastólica). Útil para ver la variabilidad."""
        if self.systolic is None or self.diastolic is None:
            return None
        return self.systolic - self.diastolic

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<BloodPressure {self.pressure} @ {self.measured_at:%Y-%m-%d %H:%M}>"


class GlucoseReading(db.Model):
    """Una medición de glucemia (azúcar en sangre)."""

    __tablename__ = "glucose_readings"
    __table_args__ = (
        CheckConstraint("value > 0", name="ck_glucose_value_positive"),
        Index("ix_glucose_user_measured", "user_id", "measured_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value = db.Column(db.Float, nullable=False)
    unit = _enum_column(GlucoseUnit, "glucose_unit")
    moment = _enum_column(GlucoseMoment, "glucose_moment")
    measured_at = db.Column(db.DateTime, nullable=False, default=local_now, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="glucose_readings")

    def value_in(self, unit: GlucoseUnit) -> float:
        """El mismo valor expresado en la unidad pedida (convierte si hace falta)."""
        if unit == self.unit:
            return self.value
        if unit == GlucoseUnit.MGDL:
            return self.value * MGDL_PER_MMOL
        return self.value / MGDL_PER_MMOL

    @property
    def value_rounded(self) -> float:
        """Un decimal en mg/dL y dos en mmol/L: suficiente y sin ruido decimal."""
        if self.unit == GlucoseUnit.MGDL:
            return round(self.value)
        return round(self.value, 1)

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<Glucose {self.value} {self.unit.value} [{self.moment.value}]>"


class Medication(db.Model):
    """Medicamento del catálogo personal, con sus horarios y días de la semana."""

    __tablename__ = "medications"
    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_medication_name_not_empty"),
        CheckConstraint("length(days) = 7", name="ck_medication_days_length"),
        # Al menos un día de la semana marcado (LIKE funciona en SQLite y PostgreSQL).
        CheckConstraint("days LIKE '%1%'", name="ck_medication_has_day"),
        CheckConstraint("length(times) > 0", name="ck_medication_times_not_empty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    dose = db.Column(db.String(60), nullable=False)
    # Siete flags '0'/'1' en el orden L M X J V S D (lunes → domingo).
    days = db.Column(db.String(7), nullable=False, default="1111111")
    # Horarios programados como "HH:MM,HH:MM,..." (ver `parse_times`).
    times = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="medications")
    intakes = db.relationship(
        "MedicationIntake",
        back_populates="medication",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # -- Utilidades ---------------------------------------------------------
    @property
    def weekdays(self) -> list[int]:
        """Índices `date.weekday()` de los días marcados (0 = lunes)."""
        return [i for i, flag in enumerate(self.days or "") if flag == "1"]

    @property
    def time_list(self) -> list[time]:
        return parse_times(self.times)

    def scheduled_on(self, day: date) -> bool:
        """¿Toca este medicamento el día de la semana de ``day``?"""
        return len(self.days or "") == 7 and self.days[day.weekday()] == "1"

    @staticmethod
    def normalize_days(raw: str | list | tuple | None) -> str:
        """Convierte lo que llegue del formulario en los siete flags '0'/'1'.

        Acepta una lista de índices de día (``[0, 2, 4]``, los checkboxes del
        formulario) o una cadena de flags ya formada.
        """
        if isinstance(raw, str):
            return raw if len(raw) == 7 and set(raw) <= {"0", "1"} else ""
        flags = ["0"] * 7
        for index in raw or []:
            try:
                number = int(index)
            except (TypeError, ValueError):
                continue
            if 0 <= number <= 6:
                flags[number] = "1"
        return "".join(flags)

    @staticmethod
    def validate_days(flags: str) -> str | None:
        """Mensaje de error o ``None`` si los días son válidos."""
        if len(flags) != 7 or set(flags) - {"0", "1"}:
            return "Selecciona al menos un día de la semana."
        if "1" not in flags:
            return "Selecciona al menos un día de la semana."
        return None

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<Medication {self.name!r} {self.dose} @ {self.times}>"


class MedicationIntake(db.Model):
    """Una toma concreta: medicamento + día + hora, con su estado de seguimiento."""

    __tablename__ = "medication_intakes"
    __table_args__ = (
        # Evita duplicados al regenerar el checklist del mismo día.
        UniqueConstraint(
            "medication_id",
            "scheduled_date",
            "scheduled_time",
            name="uq_intake_slot",
        ),
        Index("ix_intakes_user_date", "user_id", "scheduled_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medication_id = db.Column(
        db.Integer,
        db.ForeignKey("medications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_time = db.Column(db.Time, nullable=False)
    status = _enum_column(IntakeStatus, "intake_status")
    # Hora *real* de la toma; se rellena sola al marcar "Tomado".
    taken_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="medication_intakes")
    medication = db.relationship("Medication", back_populates="intakes")

    # -- Utilidades ---------------------------------------------------------
    @property
    def is_pending(self) -> bool:
        return self.status == IntakeStatus.PENDIENTE

    @property
    def minutes_late(self) -> int | None:
        """Minutos de retraso respecto al horario programado (sólo si se tomó)."""
        if self.taken_at is None or self.scheduled_time is None:
            return None
        scheduled = datetime.combine(self.scheduled_date, self.scheduled_time)
        return round((self.taken_at - scheduled).total_seconds() / 60)

    def set_status(self, status: IntakeStatus) -> None:
        """Aplica el estado y anota (o borra) la hora real de la toma."""
        self.status = status
        if status == IntakeStatus.TOMADO:
            self.taken_at = local_now()
        else:
            self.taken_at = None

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return (
            f"<Intake {self.medication_id} {self.scheduled_date} "
            f"{self.scheduled_time:%H:%M} {self.status.value}>"
        )


class FinanceService(db.Model):
    """Servicio/boleta por pagar con importe y fecha de vencimiento."""

    __tablename__ = "finance_services"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    servicio = db.Column(db.String(120), nullable=False)
    importe = db.Column(db.Float, nullable=False, default=0.0)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    pagado = db.Column(db.Boolean, nullable=False, default=False)
    fecha_pago = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="finance_services")

    # -- Utilidades ---------------------------------------------------------
    @property
    def esta_vencido(self) -> bool:
        """True si ya pasó la fecha de vencimiento y no está pagado."""
        return (
            not self.pagado
            and self.fecha_vencimiento
            and self.fecha_vencimiento < date.today()
        )

    @property
    def proximo_vencer(self) -> bool | None:
        """True si vence en los próximos 7 días y no está pagado."""
        if self.pagado or not self.fecha_vencimiento:
            return None
        delta = (self.fecha_vencimiento - date.today()).days
        return 0 <= delta <= 7

    def __repr__(self) -> str:  # pragma: no cover - ayuda en la consola
        return f"<FinanceService {self.servicio} ${self.importe} vence {self.fecha_vencimiento}>"