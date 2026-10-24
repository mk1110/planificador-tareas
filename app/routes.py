"""Rutas de la aplicación: blueprint de autenticación y blueprint principal."""

from __future__ import annotations

from datetime import date, timedelta

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
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from . import db
from .helpers import build_month_grid, month_bounds, month_name, week_bounds
from .models import Category, Task, Timeframe, User, normalize_email, FinanceService

auth_bp = Blueprint("auth", __name__)
main_bp = Blueprint("main", __name__)

VIEWS = ("semanal", "mensual")


# ===========================================================================
# Utilidades
# ===========================================================================
def _parse_anchor(raw: str | None) -> date:
    """Convierte el parámetro `ancla` (ISO) en una fecha válida."""
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


def _parse_optional_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_category(raw: str | None) -> Category | None:
    try:
        return Category((raw or "").strip())
    except ValueError:
        return None


def _parse_timeframe(raw: str | None) -> Timeframe | None:
    try:
        return Timeframe((raw or "").strip())
    except ValueError:
        return None


def _back_to_dashboard() -> str:
    """Vuelve a la vista del panel conservando los filtros activos."""
    view = request.form.get("view") or request.args.get("view") or "semanal"
    anchor = request.form.get("ancla") or request.args.get("ancla") or ""
    category = request.form.get("categoria") or request.args.get("categoria") or ""
    return url_for(
        "main.dashboard",
        view=view if view in VIEWS else "semanal",
        ancla=anchor or None,
        categoria=category or None,
    )


def _owned_task_or_404(task_id: int) -> Task:
    """Devuelve la tarea solo si pertenece al usuario en sesión."""
    task = db.session.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        abort(404)
    return task


# ===========================================================================
# Autenticación
# ===========================================================================
@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        errors = []
        if error := User.validate_username(username):
            errors.append(error)
        if error := User.validate_email(email):
            errors.append(error)
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres.")
        if password != confirm:
            errors.append("Las contraseñas no coinciden.")

        if not errors:
            if db.session.scalar(db.select(User).where(User.username == username)):
                errors.append("Ese nombre de usuario ya está en uso.")
            elif db.session.scalar(db.select(User).where(User.email == email)):
                errors.append("Ese correo electrónico ya está registrado.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "register.html",
                form={"username": username, "email": email},
            ), 400

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo crear la cuenta: el usuario o el correo ya existen.", "error")
            return render_template("register.html", form={"username": username, "email": email}), 400

        login_user(user)
        flash(f"¡Bienvenido, {user.username}! Tu planificador está listo.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html", form={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        user = None
        if identifier:
            statement = db.select(User).where(
                (User.username == identifier) | (User.email == normalize_email(identifier))
            )
            user = db.session.scalar(statement)

        # Mensaje genérico: no revela si el usuario existe.
        if user is None or not user.check_password(password):
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("login.html", form={"identifier": identifier}), 401

        login_user(user, remember=bool(request.form.get("remember")))
        next_url = request.args.get("next") or ""
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("main.dashboard")
        flash(f"Hola de nuevo, {user.username}.", "success")
        return redirect(next_url)

    return render_template("login.html", form={})


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))


# ===========================================================================
# Panel de control
# ===========================================================================
@main_bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    view = request.args.get("view", "semanal")
    if view not in VIEWS:
        view = "semanal"

    anchor = _parse_anchor(request.args.get("ancla"))
    category = _parse_category(request.args.get("categoria"))

    # Rango del período visible según la vista activa.
    start, end = week_bounds(anchor) if view == "semanal" else month_bounds(anchor)

    # Consulta base: únicamente tareas del usuario en sesión.
    base_query = db.select(Task).where(Task.user_id == current_user.id)
    period_query = base_query.where(Task.due_date >= start, Task.due_date <= end)
    if category is not None:
        period_query = period_query.where(Task.category == category)

    tasks = db.session.scalars(
        period_query.order_by(Task.due_date.asc(), Task.completed.asc(), Task.id.asc())
    ).all()

    tasks_by_date: dict[date, list[Task]] = {}
    for task in tasks:
        tasks_by_date.setdefault(task.due_date, []).append(task)

    # Tareas sin fecha (no encajan en el rango, pero conviene mostrarlas).
    undated_query = base_query.where(Task.due_date.is_(None))
    if category is not None:
        undated_query = undated_query.where(Task.category == category)
    undated = db.session.scalars(
        undated_query.order_by(Task.completed.asc(), Task.id.desc())
    ).all()

    # --- Resumen global del usuario ---------------------------------------
    def count(*conditions) -> int:
        return db.session.scalar(
            db.select(func.count(Task.id)).where(Task.user_id == current_user.id, *conditions)
        ) or 0

    period_conditions = (Task.due_date >= start, Task.due_date <= end)
    stats = {
        "total": count(*period_conditions),
        "completadas": count(Task.completed.is_(True), *period_conditions),
        "pendientes": count(Task.completed.is_(False), *period_conditions),
        "vencidas": count(
            Task.completed.is_(False),
            Task.due_date.isnot(None),
            Task.due_date < today,
        ),
        "sin_fecha": count(Task.due_date.is_(None)),
    }

    # --- Navegación entre períodos ----------------------------------------
    if view == "semanal":
        previous_anchor, next_anchor = start - timedelta(days=7), end + timedelta(days=1)
    else:
        first, last = start, end
        previous_anchor = (first - timedelta(days=1)).replace(day=1)
        next_month = (last + timedelta(days=1)).replace(day=1)
        next_anchor = next_month

    # Título del período
    if view == "semanal":
        if start.month == end.month:
            period_title = f"{start.day} – {end.day} de {month_name(start)} de {start.year}"
        else:
            period_title = (
                f"{month_name(start)[:3]} – "
                f"{end.day} {month_name(end)[:3]} de {end.year}"
            )
    else:
        period_title = f"{month_name(start).capitalize()} {start.year}"

    calendar_weeks = build_month_grid(anchor, tasks_by_date) if view == "mensual" else []

    return render_template(
        "dashboard.html",
        view=view,
        anchor=anchor,
        anchor_iso=anchor.isoformat(),
        today=today,
        period_title=period_title,
        period_start=start,
        period_end=end,
        previous_anchor=previous_anchor,
        next_anchor=next_anchor,
        category=category,
        stats=stats,
        tasks_by_date=tasks_by_date,
        undated_tasks=undated,
        week_days=[
            {
                "date": start + timedelta(days=i),
                "tasks": tasks_by_date.get(start + timedelta(days=i), []),
                "is_today": start + timedelta(days=i) == today,
                "is_weekend": (start + timedelta(days=i)).weekday() >= 5,
            }
            for i in range(7)
        ],
        calendar_weeks=calendar_weeks,
        default_timeframe=Timeframe.SEMANAL if view == "semanal" else Timeframe.MENSUAL,
    )


# ===========================================================================
# Módulo de finanzas
# ===========================================================================
@main_bp.route("/finanzas")
@login_required
def finance_index():
    """Lista los servicios/boletas del usuario."""
    services = (
        db.select(FinanceService)
        .where(FinanceService.user_id == current_user.id)
        .order_by(FinanceService.fecha_vencimiento.asc(), FinanceService.id.asc())
    ).scalars().all()

    # Calcular alertas: servicios próximos a vencer (7 días)
    hoy = date.today()
    alertas = []
    for s in services:
        if not s.pagado and s.fecha_vencimiento:
            delta = (s.fecha_vencimiento - hoy).days
            if 0 <= delta <= 7:
                alertas.append({
                    "servicio": s.servicio,
                    "importe": s.importe,
                    "dias": delta,
                    "clase": "warning" if delta <= 3 else "info",
                })

    # Resumen de dinero
    total_pendiente = db.session.scalar(
        db.select(func.sum(FinanceService.importe))
        .where(FinanceService.user_id == current_user.id, FinanceService.pagado.is_(False))
    ) or 0.0

    total_pagado = db.session.scalar(
        db.select(func.sum(FinanceService.importe))
        .where(FinanceService.user_id == current_user.id, FinanceService.pagado.is_(True))
    ) or 0.0

    return render_template(
        "finanzas.html",
        view="semanal",  # vista por defecto
        services=services,
        alertas=alertas,
        total_pendiente=total_pendiente,
        total_pagado=total_pagado,
        dinero_disponible=current_user.dinero_disponible,
    )


@main_bp.post("/finanzas/agregar")
@login_required
def finance_agregar():
    """Agregar un nuevo servicio/boleta."""
    servicio = (request.form.get("servicio") or "").strip()
    importe = request.form.get("importe")
    fecha_vencimiento = request.form.get("fecha_vencimiento")

    errors = []
    if not servicio:
        errors.append("El nombre del servicio es obligatorio.")
    if not importe:
        errors.append("El importe es obligatorio.")
    else:
        try:
            importe = float(importe)
            if importe <= 0:
                errors.append("El importe debe ser mayor a 0.")
        except ValueError:
            errors.append("El importe debe ser un número válido.")
    if not fecha_vencimiento:
        errors.append("La fecha de vencimiento es obligatoria.")
    else:
        try:
            fecha_vencimiento = date.fromisoformat(fecha_vencimiento)
        except ValueError:
            errors.append("La fecha de vencimiento no tiene un formato válido.")

    if errors:
        for message in errors:
            flash(message, "error")
        return redirect(url_for("main.dashboard"))

    service = FinanceService(
        user_id=current_user.id,
        servicio=servicio,
        importe=importe,
        fecha_vencimiento=fecha_vencimiento,
    )
    db.session.add(service)
    db.session.commit()
    flash(f'Servicio "{servicio}" añadido con ${importe}.', "success")
    return redirect(url_for("main.finance_index"))


@main_bp.post("/finanzas/pagar/<int:service_id>")
@login_required
def finance_pagar(service_id: int):
    """Pagar un servicio usando el dinero disponible."""
    service = db.session.get(FinanceService, service_id)
    if service is None or service.user_id != current_user.id:
        abort(404)

    if service.pagado:
        flash("Este servicio ya está pagado.", "info")
        return redirect(url_for("main.finance_index"))

    # Descontar del dinero disponible
    disponible = current_user.dinero_disponible
    if disponible < service.importe:
        flash(
            f"No tienes suficiente dinero disponible. "
            f"Tienes ${disponible} y el servicio cuesta ${service.importe}.",
            "error",
        )
        return redirect(url_for("main.finance_index"))

    # Registrar pago
    service.pagado = True
    service.fecha_pago = date.today()
    current_user.dinero_disponible -= service.importe

    db.session.commit()
    flash(
        f'Servicio "{service.servicio}" pagado por ${service.importe}. '
        f'Queda ${current_user.dinero_disponible} disponible.',
        "success",
    )
    return redirect(url_for("main.finance_index"))


# ===========================================================================
# CRUD de tareas
# ===========================================================================
@login_required
def create_task():
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    category = _parse_category(request.form.get("category"))
    timeframe = _parse_timeframe(request.form.get("timeframe"))
    due_date = _parse_optional_date(request.form.get("due_date"))

    if not title:
        flash("La tarea necesita un título.", "error")
    elif len(title) > 200:
        flash("El título no puede superar los 200 caracteres.", "error")
    elif category is None:
        flash("Selecciona una categoría válida.", "error")
    elif timeframe is None:
        flash("Selecciona un período válido.", "error")
    else:
        task = Task(
            user_id=current_user.id,
            title=title,
            description=description,
            category=category,
            timeframe=timeframe,
            due_date=due_date,
        )
        db.session.add(task)
        db.session.commit()
        flash(f'Tarea "{title}" añadida a tu plan.', "success")

    return redirect(_back_to_dashboard())


@main_bp.post("/tasks/<int:task_id>/toggle")
@login_required
def toggle_task(task_id: int):
    task = _owned_task_or_404(task_id)
    task.toggle()
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"id": task.id, "completed": task.completed})

    flash("Tarea actualizada.", "success")
    return redirect(_back_to_dashboard())


@main_bp.post("/tasks/<int:task_id>/update")
@login_required
def update_task(task_id: int):
    task = _owned_task_or_404(task_id)

    title = (request.form.get("title") or "").strip()
    category = _parse_category(request.form.get("category"))
    timeframe = _parse_timeframe(request.form.get("timeframe"))
    due_date = _parse_optional_date(request.form.get("due_date"))
    description = (request.form.get("description") or "").strip() or None
    completed = request.form.get("completed") in {"1", "on", "true", "True"}

    if not title:
        flash("La tarea necesita un título.", "error")
    elif len(title) > 200:
        flash("El título no puede superar los 200 caracteres.", "error")
    elif category is None or timeframe is None:
        flash("Categoría o período inválidos.", "error")
    else:
        task.title = title
        task.description = description
        task.category = category
        task.timeframe = timeframe
        task.due_date = due_date
        task.completed = completed
        db.session.commit()
        flash("Tarea actualizada correctamente.", "success")

    return redirect(_back_to_dashboard())


@main_bp.post("/tasks/<int:task_id>/delete")
@login_required
def delete_task(task_id: int):
    task = _owned_task_or_404(task_id)
    title = task.title
    db.session.delete(task)
    db.session.commit()
    flash(f'Tarea "{title}" eliminada.', "info")
    return redirect(_back_to_dashboard())


# ===========================================================================
# Errores
# ===========================================================================
@main_bp.app_errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="Página no encontrada."), 404


@main_bp.app_errorhandler(400)
def bad_request(error):
    return (
        render_template(
            "error.html",
            code=400,
            message=getattr(error, "description", "Solicitud incorrecta."),
        ),
        400,
    )