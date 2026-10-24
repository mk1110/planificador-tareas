# AGENTS.md — Planificador de Tareas Multiusuario

> Archivo de instrucciones compacto para futuras sesiones de OpenCode. Cada línea responde:
> "¿Se perdería esto sin ayuda para el agente?"

## 1. Quickstart (todo en uno)

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Windows: Copy-Item .env.example .env
# Edita .env: set SECRET_KEY y DATABASE_URL (requerido para producción)
flask --app main.py db upgrade      # aplicar migraciones iniciales
python main.py                        # http://127.0.0.1:5000
```

> **Sin `DATABASE_URL` la app arranca bien** con una base de datos SQLite de desarrollo local en `instance/dev.db`. En producción (`VERCEL=1` o `FLASK_ENV=production`) **fallará al arrancar** si falta `DATABASE_URL` — esto es intencional.

## 2. Estructura del proyecto (directorios clave)

```
.
├ app/              # Factory de Flask, extensiones, modelos, routes, blueprints
│   ├── __init__.py  # Factory de aplicación, configuración de db/migrate/login
│   ├── models.py    # Modelos: User, Task, Category, Timeframe, BP/Glucose/Medication
│   ├── routes.py    # Blueprints: auth (register/login) + main (panel/CRUD)
│   ├── health.py    # Blueprint del módulo de salud
│   ├── security.py  # Protección CSRF
│   ├── helpers.py   # Ayudantes de fechas, metadatos UI, rangos
│   └── templates/   # Plantillas Jinja + CDN de Tailwind
├ migrations/       # Migraciones Alembic (inicial + módulo salud)
├ instance/         # SQLite de desarrollo (gitignorado)
├ .env / .env.example  # Configuración por entorno
├ main.py           # Punto de entrada: crea app via create_app(), inicia servidor dev
├ requirements.txt
└ README.md
```

## 3. Comandos (exactos — no adivines)

| Finalidad | Comando |
|---|---|
| Servidor de desarrollo | `python main.py` |
| Shell de Flask con contexto | `flask --app main.py shell` |
| Listar rutas | `flask --app main.py routes` |
| Aplicar migraciones | `flask --app main.py db upgrade` |
| Generar nueva migración | `flask --app main.py db migrate -m "descripción"` |
| Estado de migraciones | `flask --app main.py db current` / `flask --app main.py db history` |
| Revertir migración | `flask --app main.py db downgrade` |

> **Todas las órdenes de Flask usan `--app main.py`.** Omitir `--app` no funcionará.

## 4. Variables de entorno (`.env`)

| Variable | ¿Obligatoria? | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí | Firma de cookies. Generar: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Solo producción | Cadena de conexión PostgreSQL/Supabase. **Usar siempre el pooler de sesiones** (puerto 5432), nUNCA conexión directa. |
| `SESSION_COOKIE_SECURE` | No | `1` en producción (HTTPS). |
| `FLASK_DEBUG` | No | `1` para modo desarrollo con recarga automática. **Nunca `1` en producción.** |

> La app **fallará al iniciar** en producción sin `DATABASE_URL`. En desarrollo usa silenciosamente SQLite.

## 5. Despliegue en producción

### Vercel (el objetivo principal)

1. Hacer push — Vercel auto-detecta `main.py` como punto de entrada (busca `app` en la raíz).
2. Añadir variables de entorno en el dashboard de Vercel (Project → Settings → Environment Variables):

| Nombre | Valor |
|---|---|
| `DATABASE_URL` | URI del pooler de Supabase |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SESSION_COOKIE_SECURE` | `1` |
| `FLASK_DEBUG` | `0` |

3. **Ejecutar migraciones manualmente después del despliegue**:

```bash
flask --app main.py db upgrade
```

> Las migraciones **NO** se ejecutan como comando de build — hacerlo automáticamente ocultaría errores y arriesgaría que dos despliegues simultáneos las ejecuten a la vez.

### Render / Railway / Fly.io

```bash
pip install gunicorn          # añadir a requirements.txt si no está presente
gunicorn "main:app" --chdir . --workers 2 --bind 0.0.0.0:$PORT
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY .
ENV PORT=8080
CMD ["sh", "-c", "gunicorn 'run:app' --chdir . --workers 2 --bind 0.0.0.0:${PORT}"]
```

> **Siempre usar el pooler de Supabase** (`aws-0-...pooler.supabase.com:5432`), nUNCA una conexión directa. Las conexiones directas caducan y rompen en serverless.

## 6. Tailwind CSS: CDN vs build

### Desarrollo (por defecto)

Las plantillas usan el Play CDN — no se necesita paso de build:

```html
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
```

### Producción

Compilar Tailwind manualmente (o paso de CI):

```bash
npm install -D tailwindcss @tailwindcss-cli
npx @tailwindcss-cli -i ./static/input.css -o ./static/tailwind.css --minify
```

`static/input.css`:

```css
@import "tailwindcss";
@source "../app/templates";
@source "../app/helpers.py";
@plugin "@tailwindcss/forms";
@custom-variant dark (&:where(.dark, .dark *));
```

En `base.html`, reemplazar el tag `<script>` del CDN por:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='tailwind.css') }}">
```

> Las clases de Tailwind están escritas **completamente** en el código (nunca con `{{ ... }}`) precisamente para que funcionen con ambos métodos.

## 7. Testing / verificación

No hay suite de tests configurada en este repositorio aún. Pasos de verificación:

```bash
# Humo rápido: crear un usuario vía shell
flask --app main.py shell
>>> from app.models import User, db
>>> user = User(username="test", email="test@example.com", password_hash="dummy")
>>> db.session.add(user)
>>> db.session.commit()
```

> Para añadir tests reales: añadir configuración de `pytest`, colocar tests bajo `tests/` y ejecutar `pytest`. No existe configuración CI/tests actualmente.

## 8. Quirks y gotchas conocidos

- **`DATABASE_URL` faltando en producción = fallo duro.** La app no hace fallback silencioso.
- **`FLASK_DEBUG=0` en producción** — el código lo obliga; poner `1` expone el debugger públicamente.
- **Solo pooler de Supabase** — conexiones directas a la DB (`db.TU_PROYECTO.supabase.co`) fallarán o caducarán. Siempre usar la URI del pooler.
- **Foreign keys de SQLite vienen desactivadas por defecto** — la app las habilita mediante un listener de SQLAlchemy (ver `app/__init__.py`).
- **`medication_intakes` se auto-crean** al abrir por primera vez la pestaña de salud `/medicaciones` — no se crean manualmente.
- **`measured_at` y `taken_at` guardan hora local**, mientras que `created_at` guarda UTC. Importante al cruzar fusos horarios al consultar.
- **El orden de migraciones importa** — la segunda migración (`ba0439e5bb03_modulo_salud.py`) añade las tablas de salud. `db upgrade` aplica ambas; `db downgrade` las quita incluyendo los tipos ENUM.

## 9. Módulo de finanzas (nuevo)

### Comandos financieros

| Finalidad | Comando |
|---|---|
| Ver finanzas (dashboard) | Acceder desde el menú superior "Finanzas" |
| Agregar servicio/boleta | En la página de finanzas, completar formulario y submit |
| Pagar servicio | En la página de finanzas, hacer clic en "Pagar" sobre el servicio |
| Ver dinero disponible | Mostrado en el resumen superior de la página de finanzas |

### Modelo `FinanceService` (tabla `finance_services`)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK a users, ON DELETE CASCADE |
| `servicio` | VARCHAR(120) | Nombre del servicio (ej. "Luz", "Agua", "Internet") |
| `importe` | FLOAT | Monto a pagar |
| `fecha_vencimiento` | DATE | Fecha de vencimiento |
| `pagado` | BOOLEAN | `False` por defecto, `True` cuando se paga |
| `fecha_pago` | DATE | Fecha en que se marcó como pagado |
| `created_at` | TIMESTAMP | Marca de creación |

### Flujo de trabajo

1. **Desde el menú dashboard** → hacer clic en "Finanzas" para abrir la página
2. **Añadir servicio** → completar: nombre del servicio, importe y fecha de vencimiento
3. **Alerta automática** → si al cargar la página hay algún servicio que vence en los próximos 7 días, se mostrará una alerta en rojo con el número de días restantes
4. **Pagar servicio** → hacer clic en "Pagar": se descuenta el importe del `dinero_disponible` del usuario y marca el servicio como pagado
5. **Resumen** → en la parte superior de la página se muestran:
   - Dinero disponible actual
   - Total pendiente (suma de servicios no pagados)
   - Total pagado (suma de servicios pagados)

### Variables de entorno adicionales (opcionales)

No se requieren variables de entorno adicionales para el módulo de finanzas. El `dinero_disponible` se almacena en la tabla `users` y se inicializa en `0.0`. Para establecer un monto inicial, se puede crear un servicio de "carga" o agregarlo manualmente en la base de datos.

### Verificación rápida

```bash
# Desde el shell de Flask, verificar finanzas del usuario
flask --app main.py shell
>>> from app.models import User, FinanceService
>>> user = db.session.get(User, 1)
>>> user.dinero_disponible
0.0
>>> len(user.finance_services)
0
```