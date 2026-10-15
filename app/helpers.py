"""Helpers de fecha, períodos y metadatos de UI, sin dependencias externas."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

# --- Nombres en español ----------------------------------------------------
WEEKDAYS_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
WEEKDAYS_LONG = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# --- Metadatos de las categorías (etiqueta + estilos de Tailwind) -----------
# IMPORTANTE: las clases de Tailwind se escriben siempre completas (nunca se
# componen con `{{ ... }}`) para que el escáner del CDN y un futuro build de
# producción las puedan detectar.
CATEGORY_META = {
    "laboral": {
        "label": "Laboral",
        "icon": "💼",
        "accent": "blue",
        "badge": "bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-500/15 dark:text-blue-300 dark:ring-blue-500/30",
        "dot": "bg-blue-500",
        "bar": "border-l-blue-500",
        "chip": "bg-blue-50 dark:bg-blue-500/10",
        "radio_ring": "peer-checked:ring-blue-500 peer-checked:bg-blue-50 dark:peer-checked:bg-blue-500/10",
    },
    "cotidiana": {
        "label": "Cotidiana",
        "icon": "🏠",
        "accent": "emerald",
        "badge": "bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30",
        "dot": "bg-emerald-500",
        "bar": "border-l-emerald-500",
        "chip": "bg-emerald-50 dark:bg-emerald-500/10",
        "radio_ring": "peer-checked:ring-emerald-500 peer-checked:bg-emerald-50 dark:peer-checked:bg-emerald-500/10",
    },
    "medica": {
        "label": "Médica",
        "icon": "🩺",
        "accent": "rose",
        "badge": "bg-rose-100 text-rose-700 ring-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:ring-rose-500/30",
        "dot": "bg-rose-500",
        "bar": "border-l-rose-500",
        "chip": "bg-rose-50 dark:bg-rose-500/10",
        "radio_ring": "peer-checked:ring-rose-500 peer-checked:bg-rose-50 dark:peer-checked:bg-rose-500/10",
    },
}

DEFAULT_CATEGORY_META = {
    "label": "Sin categoría",
    "icon": "•",
    "accent": "slate",
    "badge": "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:ring-slate-500/30",
    "dot": "bg-slate-400",
    "bar": "border-l-slate-400",
    "chip": "bg-slate-50 dark:bg-slate-500/10",
    "radio_ring": "peer-checked:ring-slate-500",
}


def category_meta(value: str | None) -> dict:
    return CATEGORY_META.get(value or "", DEFAULT_CATEGORY_META)


# ===========================================================================
# Módulo de salud
# ===========================================================================
# IMPORTANTE: las clases de Tailwind se escriben siempre completas para que el
# escáner del CDN y un futuro build de producción las puedan detectar.

# --- Momentos de la medición de glucemia ------------------------------------
MOMENT_META = {
    "ayunas": {
        "label": "En ayunas",
        "short": "Ayunas",
        "icon": "🌅",
        "badge": "bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-500/30",
        "dot": "bg-sky-500",
    },
    "antes_comer": {
        "label": "Antes de comer",
        "short": "Antes de comer",
        "icon": "🍽️",
        "badge": "bg-violet-100 text-violet-700 ring-violet-200 dark:bg-violet-500/15 dark:text-violet-300 dark:ring-violet-500/30",
        "dot": "bg-violet-500",
    },
    "despues_comer": {
        "label": "2 h después de comer",
        "short": "Después de comer",
        "icon": "🍎",
        "badge": "bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30",
        "dot": "bg-amber-500",
    },
    "antes_dormir": {
        "label": "Antes de dormir",
        "short": "Antes de dormir",
        "icon": "🌙",
        "badge": "bg-indigo-100 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/15 dark:text-indigo-300 dark:ring-indigo-500/30",
        "dot": "bg-indigo-500",
    },
    "otro": {
        "label": "Otro momento",
        "short": "Otro",
        "icon": "•",
        "badge": "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:ring-slate-500/30",
        "dot": "bg-slate-400",
    },
}

# --- Unidades de glucemia ---------------------------------------------------
GLUCOSE_UNITS = {
    "mgdl": {"label": "mg/dL", "step": "1", "min": 20, "max": 800, "suffix": " mg/dL"},
    "mmol": {"label": "mmol/L", "step": "0.1", "min": "1", "max": "44", "suffix": " mmol/L"},
}

# Rangos de referencia orientativos por momento de la medición (en mg/dL).
# Son únicamente una ayuda visual: no son un diagnóstico.
GLUCOSE_RANGES = {
    "ayunas": (70, 99),
    "antes_comer": (70, 99),
    "despues_comer": (70, 140),
    "antes_dormir": (70, 99),
    "otro": (70, 140),
}

# --- Clasificación de la tensión arterial (criterios AHA) -------------------
BP_LEVELS = {
    "normal": {
        "label": "Normal",
        "badge": "bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30",
    },
    "elevada": {
        "label": "Elevada",
        "badge": "bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-500/30",
    },
    "fase1": {
        "label": "Grado 1",
        "badge": "bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30",
    },
    "fase2": {
        "label": "Grado 2",
        "badge": "bg-rose-100 text-rose-700 ring-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:ring-rose-500/30",
    },
    "crisis": {
        "label": "Crisis",
        "badge": "bg-red-100 text-red-700 ring-red-200 dark:bg-red-500/15 dark:text-red-300 dark:ring-red-500/30",
    },
}

# --- Estados de la toma de medicación ---------------------------------------
INTAKE_META = {
    "pendiente": {
        "label": "Pendiente",
        "icon": "🕒",
        "badge": "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:ring-slate-500/30",
        "dot": "bg-slate-400",
    },
    "tomado": {
        "label": "Tomado",
        "icon": "✅",
        "badge": "bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30",
        "dot": "bg-emerald-500",
    },
    "omitido": {
        "label": "Omitido",
        "icon": "⛔",
        "badge": "bg-rose-100 text-rose-700 ring-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:ring-rose-500/30",
        "dot": "bg-rose-500",
    },
}

HEALTH_DISCLAIMER = (
    "Los rangos mostrados son orientativos y no sustituyen el consejo de tu "
    "profesional sanitario."
)


def moment_meta(value: str | None) -> dict:
    return MOMENT_META.get(value or "", MOMENT_META["otro"])


def intake_meta(value: str | None) -> dict:
    return INTAKE_META.get(value or "", INTAKE_META["pendiente"])


def glucose_unit_meta(value: str | None) -> dict:
    return GLUCOSE_UNITS.get(value or "", GLUCOSE_UNITS["mgdl"])


def classify_bp(systolic: int, diastolic: int) -> str:
    """Devuelve la clave de `BP_LEVELS` para una pareja sistólica/diastólica."""
    if systolic >= 180 or diastolic >= 120:
        return "crisis"
    if systolic >= 140 or diastolic >= 90:
        return "fase2"
    if systolic >= 130 or diastolic >= 80:
        return "fase1"
    if systolic >= 120:
        return "elevada"
    return "normal"


def bp_meta(systolic: int, diastolic: int) -> dict:
    return BP_LEVELS[classify_bp(systolic, diastolic)]


def glucose_level(value: float, moment: str | None, unit: str = "mgdl") -> dict:
    """Traduce un valor de glucemia a una etiqueta con su estilo.

    Convierte a mg/dL antes de comparar, de modo que el resultado es el mismo
    exprese la medición en mg/dL o en mmol/L.
    """
    from .models import MGDL_PER_MMOL

    mgdl = value * MGDL_PER_MMOL if unit == "mmol" else value
    low, high = GLUCOSE_RANGES.get(moment or "otro", GLUCOSE_RANGES["otro"])
    if mgdl < low:
        return {
            "label": "Baja",
            "badge": "bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-500/30",
        }
    if mgdl > high:
        return {
            "label": "Alta",
            "badge": "bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30",
        }
    return {
        "label": "En rango",
        "badge": "bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30",
    }


# --- Formato ---------------------------------------------------------------
def format_date(value: date | None) -> str:
    """Ej.: 12 oct 2026"""
    if value is None:
        return "—"
    return f"{value.day} {MONTHS[value.month - 1][:3]} {value.year}"


def weekday_short(value: date) -> str:
    return WEEKDAYS_SHORT[value.weekday()]


def weekday_long(value: date) -> str:
    return WEEKDAYS_LONG[value.weekday()]


def month_name(value: date) -> str:
    return MONTHS[value.month - 1]


def format_datetime(value: datetime | None) -> str:
    """Ej.: 12 oct 2026, 14:30"""
    if value is None:
        return "—"
    return f"{value.day} {MONTHS[value.month - 1][:3]} {value.year}, {value:%H:%M}"


def format_time(value: time | None) -> str:
    """Ej.: 08:05"""
    return value.strftime("%H:%M") if value is not None else "—"


def format_number(value: float | int | None) -> str:
    """Sin decimales sueltos: 120.0 → "120", 6.94 → "6,9"."""
    if value is None:
        return "—"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.1f}".replace(".", ",")
    return str(round(value))


# --- Períodos --------------------------------------------------------------
def week_bounds(anchor: date) -> tuple[date, date]:
    """Lunes y domingo de la semana que contiene ``anchor``."""
    start = anchor - timedelta(days=anchor.weekday())
    return start, start + timedelta(days=6)


def month_bounds(anchor: date) -> tuple[date, date]:
    """Primer y último día del mes que contiene ``anchor``."""
    start = anchor.replace(day=1)
    last_day = calendar.monthrange(anchor.year, anchor.month)[1]
    return start, date(anchor.year, anchor.month, last_day)


def build_month_grid(anchor: date, tasks_by_date: dict[date, list]) -> list[list[dict]]:
    """Rejilla del mes en filas de 7, rellenando con días del mes anterior/siguiente."""
    first, last = month_bounds(anchor)
    grid_start = first - timedelta(days=first.weekday())
    total_days = (last - grid_start).days + 1
    weeks = (total_days + 6) // 7

    rows = []
    for week_index in range(weeks):
        row = []
        for day_offset in range(7):
            day = grid_start + timedelta(days=week_index * 7 + day_offset)
            row.append(
                {
                    "date": day,
                    "day": day.day,
                    "in_month": day.month == anchor.month,
                    "tasks": tasks_by_date.get(day, []),
                    "is_today": day == date.today(),
                }
            )
        rows.append(row)
    return rows


def register_date_helpers(app) -> None:
    """Expone los helpers anteriores como filtros y globales de Jinja."""

    @app.template_filter("dformat")
    def _dformat(value):
        return format_date(value)

    @app.template_filter("datetimeformat")
    def _datetimeformat(value):
        return format_datetime(value)

    @app.template_filter("timeformat")
    def _timeformat(value):
        return format_time(value)

    @app.template_filter("numformat")
    def _numformat(value):
        return format_number(value)

    @app.context_processor
    def _inject_globals():
        return {
            "CATEGORY_META": CATEGORY_META,
            "category_meta": category_meta,
            "weekdays_short": WEEKDAYS_SHORT,
            "weekdays_long": WEEKDAYS_LONG,
            "month_name": month_name,
            "current_year": date.today().year,
            "today": date.today(),
            # --- Módulo de salud ---
            "MOMENT_META": MOMENT_META,
            "moment_meta": moment_meta,
            "INTAKE_META": INTAKE_META,
            "intake_meta": intake_meta,
            "GLUCOSE_UNITS": GLUCOSE_UNITS,
            "glucose_unit_meta": glucose_unit_meta,
            "glucose_level": glucose_level,
            "bp_meta": bp_meta,
            "classify_bp": classify_bp,
            "HEALTH_DISCLAIMER": HEALTH_DISCLAIMER,
        }