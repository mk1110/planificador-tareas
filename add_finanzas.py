import re

path = r'C:\Users\mk111\OneDrive\Escritorio\programando\new\app\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the position after dashboard and before CRUD tasks
old = """@main_bp.post("/tasks")
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
        flash(f'Tarea "{title}" añadida a tu plan., "success")

    return redirect(_back_to_dashboard())"""

new = """@main_bp.post("/tasks")
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
        flash(f'Tarea "{title}" añadida a tu plan., "success")

    return redirect(_back_to_dashboard())


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
# ==========================================================================="""

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Éxito al insertar finanzas")
else:
    print("No se encontró el string viejo")
    # Show what's around line 303
    lines = content.split('\n')
    for i in range(298, 315):
        print(f"{i+1}: {repr(lines[i])}")