"""Blueprint del módulo de salud: constantes vitales y control de medicación.

Las rutas devuelven `404` (no `403`) cuando un registro pertenece a otro
usuario, igual que hace el CRUD de tareas: no se revela la existencia de datos
ajenos.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from . import db
from .helpers import GLUCOSE_RANGES
from .models import (
    BloodPressureReading,
    GlucoseMoment,
    GlucoseReading,
    GlucoseUnit,
    IntakeStatus,
    Medication,
    MedicationIntake,
    format_times,
    local_now,
    parse_times,
)

health_bp = Blueprint("health", __name__)

TABS = ("tension", "glucemia", "medicamentos")
RANGES = {"7": 7, "30": 30, "90": 90}
MAX_NOTES = 1000
#: Límite de registros que se pintan en la tabla (el gráfico usa los mismos).
MAX_LISTED = 120


# ===========================================================================
# Utilidades de parseo y validación
# ===========================================================================
def _parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Interpreta el `datetime-local` del formulario (``2026-10-14T14:30``)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        # Algunos navegadores envían `2026-10-14T14:30:00` o con espacio.
        try:
            value = datetime.strptime(raw[:16], "%Y-%m-%dT%H:%M")
        except ValueError:
            return None
    return value.replace(microsecond=0)


def _validated_datetime(raw: str | None) -> tuple[datetime | None, str | None]:
    """Devuelve `(valor, error)`: la fecha del formulario o la hora actual.

    Un campo vacío (o ausente) significa "ahora": es el registro automático que
    ofrece el formulario, y el usuario puede corregirlo antes de enviarlo.
    """
    value = _parse_datetime(raw)
    if value is None:
        if (raw or "").strip():
            return None, "La fecha y la hora no son válidas."
        value = local_now()
    if value.year < 1970:
        return None, "La fecha es demasiado antigua."
    if value > local_now() + timedelta(days=1):
        return None, "La fecha no puede estar en el futuro."
    return value, None


def _parse_int(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw.replace(",", "."))
    except ValueError:
        return None


def _parse_float(raw: str | None) -> float | None:
    """Acepta el separador decimal español (`6,9`) y el inglés (`6.9`)."""
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_glucose_unit(raw: str | None) -> GlucoseUnit | None:
    try:
        return GlucoseUnit((raw or "").strip())
    except ValueError:
        return None


def _parse_moment(raw: str | None) -> GlucoseMoment | None:
    try:
        return GlucoseMoment((raw or "").strip())
    except ValueError:
        return None


def _parse_intake_status(raw: str | None) -> IntakeStatus | None:
    try:
        return IntakeStatus((raw or "").strip())
    except ValueError:
        return None


def _clean_notes(raw: str | None) -> str | None:
    notes = (raw or "").strip()
    return notes[:MAX_NOTES] or None


def _now_input() -> str:
    """Valor por defecto de los `datetime-local`: ahora, en formato ISO local."""
    return local_now().strftime("%Y-%m-%dT%H:%M")


def _back_to_health(tab: str, **extra) -> str:
    """Vuelve a la sección de salud conservando los filtros de la petición."""
    params = {"tab": tab if tab in TABS else "tension"}
    for key in ("rango", "fecha", "momento", "unidad"):
        value = request.form.get(key) or request.args.get(key) or extra.get(key)
        if value:
            params[key] = value
    return url_for("health.index", **params)


def _owned_or_404(model, record_id: int):
    """Devuelve el registro sólo si pertenece al usuario en sesión."""
    record = db.session.get(model, record_id)
    if record is None or record.user_id != current_user.id:
        abort(404)
    return record


# ===========================================================================
# Resumen (tarjetas de estadísticas de cada pestaña)
# ===========================================================================
def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _bp_stats(readings: list[BloodPressureReading]) -> dict:
    systolic = [r.systolic for r in readings if r.systolic]
    diastolic = [r.diastolic for r in readings if r.diastolic]
    pulse = [r.pulse for r in readings if r.pulse]
    return {
        "total": len(readings),
        "sistolica_media": _average(systolic),
        "diastolica_media": _average(diastolic),
        "pulso_medio": _average(pulse),
        "ultima": readings[-1] if readings else None,
    }


def _glucose_stats(readings: list[GlucoseReading], unit: GlucoseUnit) -> dict:
    values = [r.value_in(unit) for r in readings if r.value]
    return {
        "total": len(readings),
        "media": _average(values),
        "min": round(min(values)) if values else None,
        "max": round(max(values)) if values else None,
        "ultima": readings[-1] if readings else None,
        "en_rango": sum(1 for r in readings if _in_reference(r)),
    }


def _in_reference(reading: GlucoseReading) -> bool:
    """¿La medición está dentro del rango orientativo de su momento?"""
    low, high = GLUCOSE_RANGES.get(reading.moment.value, GLUCOSE_RANGES["otro"])
    return low <= reading.value_in(GlucoseUnit.MGDL) <= high


def _intake_stats(intakes: list[MedicationIntake]) -> dict:
    total = len(intakes)
    taken = sum(1 for i in intakes if i.status == IntakeStatus.TOMADO)
    skipped = sum(1 for i in intakes if i.status == IntakeStatus.OMITIDO)
    pending = total - taken - skipped
    return {
        "total": total,
        "tomadas": taken,
        "omitidas": skipped,
        "pendientes": pending,
        "cumplimiento": round(taken / total * 100) if total else None,
    }


# ===========================================================================
# Checklist diario: se materializa bajo demanda
# ===========================================================================
def _ensure_intakes(day: date) -> list[MedicationIntake]:
    """Crea las filas de toma de ``day`` que falten y devuelve las del día.

    No se generan todas por adelantado al añadir un medicamento (habría que
    recorrer meses hacia adelante); se crean la primera vez que el usuario
    visita un día, y la restricción única evita duplicados.
    """
    medications = db.session.scalars(
        db.select(Medication).where(
            Medication.user_id == current_user.id,
            Medication.active.is_(True),
        )
    ).all()

    scheduled = [
        (medication, slot)
        for medication in medications
        if medication.scheduled_on(day)
        for slot in medication.time_list
    ]
    if not scheduled:
        return db.session.scalars(
            db.select(MedicationIntake).where(
                MedicationIntake.user_id == current_user.id,
                MedicationIntake.scheduled_date == day,
            )
        ).all()

    existing = {
        (intake.medication_id, intake.scheduled_time)
        for intake in db.session.scalars(
            db.select(MedicationIntake).where(
                MedicationIntake.user_id == current_user.id,
                MedicationIntake.scheduled_date == day,
            )
        ).all()
    }

    created = False
    for medication, slot in scheduled:
        if (medication.id, slot) in existing:
            continue
        db.session.add(
            MedicationIntake(
                user_id=current_user.id,
                medication_id=medication.id,
                scheduled_date=day,
                scheduled_time=slot,
                status=IntakeStatus.PENDIENTE,
            )
        )
        created = True

    if created:
        db.session.commit()

    return db.session.scalars(
        db.select(MedicationIntake)
        .where(
            MedicationIntake.user_id == current_user.id,
            MedicationIntake.scheduled_date == day,
        )
        .order_by(MedicationIntake.scheduled_time.asc(), MedicationIntake.id.asc())
    ).all()


# ===========================================================================
# Página principal
# ===========================================================================
@health_bp.route("/health")
@login_required
def index():
    tab = request.args.get("tab", "tension")
    if tab not in TABS:
        tab = "tension"

    context = {"tab": tab, "range_keys": sorted(RANGES, key=int)}

    if tab == "tension":
        context.update(_tension_context())
    elif tab == "glucemia":
        context.update(_glucose_context())
    else:
        context.update(_medication_context())

    return render_template("health.html", **context)


def _tension_context() -> dict:
    days = RANGES.get(request.args.get("rango", "30"), 30)
    today = date.today()
    start = today - timedelta(days=days - 1)

    readings = db.session.scalars(
        db.select(BloodPressureReading)
        .where(
            BloodPressureReading.user_id == current_user.id,
            BloodPressureReading.measured_at >= datetime.combine(start, time.min),
        )
        .order_by(BloodPressureReading.measured_at.desc())
        .limit(MAX_LISTED)
    ).all()

    ordered = list(reversed(readings))
    return {
        "days": days,
        "start": start,
        "end": today,
        "now_input": _now_input(),
        "readings": ordered,
        "stats": _bp_stats(ordered),
        "chart": {
            "labels": [r.measured_at.strftime("%d/%m") for r in ordered],
            "series": [
                {
                    "name": "Sistólica",
                    "color": "#e11d48",
                    "data": [r.systolic for r in ordered],
                },
                {
                    "name": "Diastólica",
                    "color": "#0ea5e9",
                    "data": [r.diastolic for r in ordered],
                },
                {
                    "name": "Pulso",
                    "color": "#8b5cf6",
                    "data": [r.pulse for r in ordered],
                },
            ],
            "reference": [
                {"label": "120", "value": 120},
                {"label": "80", "value": 80},
            ],
        },
    }


def _glucose_context() -> dict:
    days = RANGES.get(request.args.get("rango", "30"), 30)
    today = date.today()
    start = today - timedelta(days=days - 1)

    moment = _parse_moment(request.args.get("momento"))
    query = db.select(GlucoseReading).where(
        GlucoseReading.user_id == current_user.id,
        GlucoseReading.measured_at >= datetime.combine(start, time.min),
    )
    if moment is not None:
        query = query.where(GlucoseReading.moment == moment)

    readings = list(
        reversed(
            db.session.scalars(
                query.order_by(GlucoseReading.measured_at.desc()).limit(MAX_LISTED)
            ).all()
        )
    )

    # El histórico guarda cada medición en su unidad original; la del selector
    # decide cómo se muestran y comparan todas (el gráfico necesita una escala).
    unit = _parse_glucose_unit(request.args.get("unidad")) or GlucoseUnit.MGDL
    values = [round(reading.value_in(unit), 1) for reading in readings]

    return {
        "days": days,
        "start": start,
        "end": today,
        "now_input": _now_input(),
        "moment": moment,
        "unit": unit,
        "readings": readings,
        "stats": _glucose_stats(readings, unit),
        "chart": {
            "labels": [r.measured_at.strftime("%d/%m") for r in readings],
            "series": [{"name": "Glucemia", "color": "#f59e0b", "data": values}],
        },
    }


def _medication_context() -> dict:
    day = _parse_date(request.args.get("fecha")) or date.today()
    today = date.today()

    intakes = _ensure_intakes(day)

    medications = db.session.scalars(
        db.select(Medication)
        .where(Medication.user_id == current_user.id)
        .order_by(Medication.active.desc(), Medication.name.asc())
    ).all()

    by_medication = {}
    for intake in intakes:
        by_medication.setdefault(intake.medication_id, []).append(intake)

    # Cumplimiento de los últimos 7 días (incluye el día mostrado si es pasado).
    week_start = min(today, day) - timedelta(days=6)
    week_intakes = db.session.scalars(
        db.select(MedicationIntake).where(
            MedicationIntake.user_id == current_user.id,
            MedicationIntake.scheduled_date >= week_start,
            MedicationIntake.scheduled_date <= today,
        )
    ).all()

    return {
        "day": day,
        "day_iso": day.isoformat(),
        "fecha": day.isoformat(),
        "previous_day": (day - timedelta(days=1)).isoformat(),
        "next_day": (day + timedelta(days=1)).isoformat(),
        "is_today": day == today,
        "medications": medications,
        "active_medications": [m for m in medications if m.active],
        "intakes": intakes,
        "intakes_by_medication": by_medication,
        "stats": _intake_stats(intakes),
        "week_stats": _intake_stats(list(week_intakes)),
    }


# ===========================================================================
# Tensión arterial
# ===========================================================================
def _read_bp_form() -> tuple[dict, str | None]:
    systolic = _parse_int(request.form.get("systolic"))
    diastolic = _parse_int(request.form.get("diastolic"))
    pulse = _parse_int(request.form.get("pulse"))

    if systolic is None:
        return {}, "Introduce la presión sistólica."
    if not 50 <= systolic <= 300:
        return {}, "La presión sistólica debe estar entre 50 y 300 mmHg."
    if diastolic is None:
        return {}, "Introduce la presión diastólica."
    if not 30 <= diastolic <= 200:
        return {}, "La presión diastólica debe estar entre 30 y 200 mmHg."
    if pulse is not None and not 20 <= pulse <= 250:
        return {}, "El pulso debe estar entre 20 y 250 lpm."

    measured_at, error = _validated_datetime(request.form.get("measured_at"))
    if error:
        return {}, error

    return {
        "systolic": systolic,
        "diastolic": diastolic,
        "pulse": pulse,
        "measured_at": measured_at,
        "notes": _clean_notes(request.form.get("notes")),
    }, None


@health_bp.post("/health/bp")
@login_required
def create_bp():
    values, error = _read_bp_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("tension"))

    db.session.add(BloodPressureReading(user_id=current_user.id, **values))
    db.session.commit()
    flash(
        f'Tensión {values["systolic"]}/{values["diastolic"]} registrada.',
        "success",
    )
    return redirect(_back_to_health("tension"))


@health_bp.post("/health/bp/<int:reading_id>/update")
@login_required
def update_bp(reading_id: int):
    reading = _owned_or_404(BloodPressureReading, reading_id)
    values, error = _read_bp_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("tension"))

    for key, value in values.items():
        setattr(reading, key, value)
    db.session.commit()
    flash(f'Tensión actualizada a {reading.pressure} mmHg.', "success")
    return redirect(_back_to_health("tension"))


@health_bp.post("/health/bp/<int:reading_id>/delete")
@login_required
def delete_bp(reading_id: int):
    reading = _owned_or_404(BloodPressureReading, reading_id)
    pressure = reading.pressure
    db.session.delete(reading)
    db.session.commit()
    flash(f"Medición de tensión {pressure} eliminada.", "info")
    return redirect(_back_to_health("tension"))


# ===========================================================================
# Glucemia
# ===========================================================================
def _read_glucose_form() -> tuple[dict, str | None]:
    value = _parse_float(request.form.get("value"))
    unit = _parse_glucose_unit(request.form.get("unit"))
    moment = _parse_moment(request.form.get("moment"))

    if unit is None:
        return {}, "Selecciona una unidad válida (mg/dL o mmol/L)."
    if moment is None:
        return {}, "Selecciona el momento de la medición."
    if value is None:
        return {}, "Introduce el valor de glucemia."
    if value <= 0:
        return {}, "El valor de glucemia debe ser mayor que cero."
    # Rangos amplias a propósito: incluyen las glucemias de cetosis y las
    # hiperglucemias severas sin dejar pasar valores absurdos (500 mmol/L).
    limit = 800 if unit == GlucoseUnit.MGDL else 44
    if value > limit:
        return {}, f"El valor no puede superar los {limit} {unit.value}."

    measured_at, error = _validated_datetime(request.form.get("measured_at"))
    if error:
        return {}, error

    return {
        "value": value,
        "unit": unit,
        "moment": moment,
        "measured_at": measured_at,
        "notes": _clean_notes(request.form.get("notes")),
    }, None


@health_bp.post("/health/glucose")
@login_required
def create_glucose():
    values, error = _read_glucose_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("glucemia"))

    db.session.add(GlucoseReading(user_id=current_user.id, **values))
    db.session.commit()
    flash(f"Glucemia de {values['value']} {values['unit'].value} registrada.", "success")
    return redirect(_back_to_health("glucemia"))


@health_bp.post("/health/glucose/<int:reading_id>/update")
@login_required
def update_glucose(reading_id: int):
    reading = _owned_or_404(GlucoseReading, reading_id)
    values, error = _read_glucose_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("glucemia"))

    for key, value in values.items():
        setattr(reading, key, value)
    db.session.commit()
    flash("Medición de glucemia actualizada.", "success")
    return redirect(_back_to_health("glucemia"))


@health_bp.post("/health/glucose/<int:reading_id>/delete")
@login_required
def delete_glucose(reading_id: int):
    reading = _owned_or_404(GlucoseReading, reading_id)
    value, unit = reading.value_rounded, reading.unit.value
    db.session.delete(reading)
    db.session.commit()
    flash(f"Medición de glucemia de {value} {unit} eliminada.", "info")
    return redirect(_back_to_health("glucemia"))


# ===========================================================================
# Catálogo de medicamentos
# ===========================================================================
def _read_medication_form() -> tuple[dict, str | None]:
    name = (request.form.get("name") or "").strip()
    dose = (request.form.get("dose") or "").strip()
    days = Medication.normalize_days(request.form.getlist("days"))
    times = parse_times(request.form.get("times") or "")

    if not name:
        return {}, "El medicamento necesita un nombre."
    if len(name) > 120:
        return {}, "El nombre no puede superar los 120 caracteres."
    if not dose:
        return {}, "Indica la dosis (por ejemplo, 500 mg o 1 pastilla)."
    if len(dose) > 60:
        return {}, "La dosis no puede superar los 60 caracteres."
    if error := Medication.validate_days(days):
        return {}, error
    if not times:
        return {}, "Indica al menos un horario con el formato 08:00 o 08:00, 14:00, 20:00."
    if len(times) > 12:
        return {}, "No se admiten más de 12 horarios diarios."

    return {
        "name": name,
        "dose": dose,
        "days": days,
        "times": format_times(times),
    }, None


@health_bp.post("/health/medications")
@login_required
def create_medication():
    values, error = _read_medication_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("medicamentos"))

    # Un medicamento recién creado se activa siempre: si el usuario lo añade al
    # catálogo quiere empezar a tomarlo. El estado sólo se cambia con "Pausar".
    db.session.add(Medication(user_id=current_user.id, active=True, **values))
    db.session.commit()
    flash(f'{values["name"]} añadido a tu catálogo.', "success")
    return redirect(_back_to_health("medicamentos"))


@health_bp.post("/health/medications/<int:medication_id>/update")
@login_required
def update_medication(medication_id: int):
    medication = _owned_or_404(Medication, medication_id)
    values, error = _read_medication_form()
    if error:
        flash(error, "error")
        return redirect(_back_to_health("medicamentos"))

    # Si cambian los días o los horarios, las tomas ya materializadas para hoy
    # en adelante dejarían de cuadrar. Se borran las que siguen pendientes; las
    # ya tomadas u omitidas se conservan porque son historial, y las pendientes
    # se vuelven a crear al abrir el día con el horario nuevo.
    db.session.execute(
        db.delete(MedicationIntake).where(
            MedicationIntake.medication_id == medication.id,
            MedicationIntake.scheduled_date >= date.today(),
            MedicationIntake.status == IntakeStatus.PENDIENTE,
        )
    )

    for key, value in values.items():
        setattr(medication, key, value)
    db.session.commit()

    flash(f'{values["name"]} actualizado.', "success")
    return redirect(_back_to_health("medicamentos"))


@health_bp.post("/health/medications/<int:medication_id>/toggle")
@login_required
def toggle_medication(medication_id: int):
    medication = _owned_or_404(Medication, medication_id)
    medication.active = not medication.active
    db.session.commit()
    state = "activado" if medication.active else "pausado"
    flash(f'{medication.name}: {state}.', "info")
    return redirect(_back_to_health("medicamentos"))


@health_bp.post("/health/medications/<int:medication_id>/delete")
@login_required
def delete_medication(medication_id: int):
    medication = _owned_or_404(Medication, medication_id)
    name = medication.name
    db.session.delete(medication)
    db.session.commit()
    flash(f"{name} eliminado del catálogo.", "info")
    return redirect(_back_to_health("medicamentos"))


# ===========================================================================
# Checklist diario de tomas
# ===========================================================================
@health_bp.post("/health/intakes/<int:intake_id>")
@login_required
def set_intake_status(intake_id: int):
    intake = _owned_or_404(MedicationIntake, intake_id)
    status = _parse_intake_status(request.form.get("status"))
    if status is None:
        flash("Estado de toma no válido.", "error")
        return redirect(_back_to_health("medicamentos", fecha=intake.scheduled_date.isoformat()))

    intake.set_status(status)
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return jsonify(
            {
                "id": intake.id,
                "status": intake.status.value,
                "taken_at": intake.taken_at.isoformat() if intake.taken_at else None,
                "minutes_late": intake.minutes_late,
            }
        )

    messages = {
        IntakeStatus.TOMADO: "Toma registrada.",
        IntakeStatus.OMITIDO: "Toma marcada como omitida.",
        IntakeStatus.PENDIENTE: "Toma devuelta a pendiente.",
    }
    flash(messages[intake.status], "success")
    return redirect(_back_to_health("medicamentos", fecha=intake.scheduled_date.isoformat()))