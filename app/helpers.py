"""Helpers de fecha y lógica de periods (semanal / mensual) sin dependencias externas."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

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

    @app.context_processor
    def _inject_globals():
        return {
            "CATEGORY_META": CATEGORY_META,
            "category_meta": category_meta,
            "weekdays_short": WEEKDAYS_SHORT,
            "month_name": month_name,
            "current_year": date.today().year,
            "today": date.today(),
        }