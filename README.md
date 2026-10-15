# Planificador de Tareas Multiusuario

Aplicación web adaptable con dos módulos:

- **Planificador** — gestión de tareas personales divididas en tres categorías
  (**Laboral**, **Cotidiana** y **Médica**), con vistas de planificación
  **semanal** y **mensual**.
- **Registro de salud** — control diario de **tensión arterial** y **glucemia**,
  y catálogo de medicamentos con **horarios y checklist de tomas**.

Cada usuario sólo ve y gestiona sus propios datos.

**Stack:** Flask 3 · PostgreSQL (Supabase) · SQLAlchemy · Flask-Login · Tailwind CSS

[![Licencia MIT](https://img.shields.io/badge/Licencia-MIT-blue.svg)](LICENSE)

---

## 1. Puesta en marcha

```bash
# 1. Entorno virtual
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env               # Windows: Copy-Item .env.example .env
# Edita .env: SECRET_KEY y DATABASE_URL

# 4. Esquema de la base de datos
flask --app main.py db upgrade      # la migración inicial ya está incluida

# 5. Arrancar
python main.py                      # http://127.0.0.1:5000
```

> **Sin `DATABASE_URL` la app arranca igual** con un SQLite de desarrollo en
> `instance/dev.db`, útil para trabajar sin configurar Supabase.
>
> **En producción ese respaldo está deshabilitado a propósito.** Si detecta
> Vercel (`VERCEL=1`) o `FLASK_ENV=production` y no encuentra `DATABASE_URL`, la
> aplicación **falla al arrancar** con un mensaje que indica exactamente qué
> variable falta y dónde configurarla. Sin esta protección, el sistema de
> archivos de las funciones de Vercel (solo lectura) producía un críptico
> `sqlite3.OperationalError: no se puede abrir el archivo de la base de datos`,
> y además sólo se manifestaba en la primera petición que escribiera en la base:
> `/login` y `/register` devolvían 200 y la aplicación parecía funcionar.

### Variables de entorno (`.env`)

| Variable | Obligatoria | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí | Firma las cookies de sesión. Genéralo con `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_URL` | En producción | Cadena de conexión PostgreSQL de Supabase. |
| `SESSION_COOKIE_SECURE` | No | `1` en producción (HTTPS). |
| `FLASK_DEBUG` | No | `1` para el servidor de desarrollo con recarga automática. |

---

## 2. Estructura del proyecto

```
.
├── app/
│   ├── __init__.py            # Application Factory, extensiones y config
│   ├── models.py              # User, Task y modelos de salud (SQLAlchemy)
│   ├── routes.py              # Blueprints: auth (registro/login) y main (panel/CRUD)
│   ├── health.py              # Blueprint del módulo de salud
│   ├── security.py            # Protección CSRF por sesión
│   ├── helpers.py             # Fechas, períodos, metadatos UI y rangos de referencia
│   └── templates/
│       ├── base.html          # Layout, navegación, CDN de Tailwind, modo oscuro
│       ├── login.html         # Inicio de sesión
│       ├── register.html      # Registro de usuario
│       ├── dashboard.html     # Panel: vistas semanal/mensual, filtros, modales
│       ├── _task_card.html    # Macro reutilizable de tarjeta de tarea
│       ├── health.html        # Salud: pestañas, filtros y layout
│       ├── _health_tension.html  # Pestaña de tensión arterial
│       ├── _health_glucose.html  # Pestaña de glucemia
│       ├── _health_meds.html     # Pestaña de medicamentos y checklist
│       ├── _health_js.html       # Gráfico SVG, modales y checklist interactivo
│       └── error.html         # Páginas 400 / 404
├── migrations/                # Migraciones Alembic (generadas por Flask-Migrate)
├── instance/                  # SQLite de desarrollo (ignorado por git)
├── .env / .env.example        # Configuración por entorno
├── requirements.txt
├── main.py                      # Punto de entrada
└── README.md
```

---

## 3. Esquema de la base de datos

### `users`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `username` | VARCHAR(30) | **único**, no nulo, indexado |
| `email` | VARCHAR(255) | **único**, no nulo, indexado |
| `password_hash` | VARCHAR(255) | no nulo (hash, nunca texto plano) |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

### `tasks`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `user_id` | INTEGER | FK → `users.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `title` | VARCHAR(200) | no nulo, `CHECK (length(title) >= 1)` |
| `description` | TEXT | opcional |
| `category` | ENUM `task_category` | no nulo → `'laboral'` \| `'cotidiana'` \| `'medica'` |
| `timeframe` | ENUM `task_timeframe` | no nulo → `'semanal'` \| `'mensual'` |
| `due_date` | DATE | opcional, indexado |
| `completed` | BOOLEAN | no nulo, por defecto `False`, indexado |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

Índice compuesto `ix_tasks_user_due (user_id, due_date)` para acelerar las
consultas del panel, que siempre filtran por usuario y rango de fechas.

**Diagrama:** `users 1 ──── N tasks` (borrar un usuario elimina sus tareas en cascada).

### `blood_pressure_readings`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `user_id` | INTEGER | FK → `users.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `systolic` | INTEGER | no nulo, `CHECK (50 … 300)` |
| `diastolic` | INTEGER | no nulo, `CHECK (30 … 200)` |
| `pulse` | INTEGER | opcional, `CHECK (20 … 250)` |
| `measured_at` | TIMESTAMP | no nulo (hora **local**), indexado |
| `notes` | TEXT | opcional |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

Índice `ix_bp_user_measured (user_id, measured_at)`: el histórico siempre se
consulta por usuario y ordenando por fecha.

### `glucose_readings`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `user_id` | INTEGER | FK → `users.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `value` | FLOAT | no nulo, `CHECK (value > 0)` |
| `unit` | ENUM `glucose_unit` | no nulo → `'mgdl'` \| `'mmol'` |
| `moment` | ENUM `glucose_moment` | no nulo → `'ayunas'` \| `'antes_comer'` \| `'despues_comer'` \| `'antes_dormir'` \| `'otro'` |
| `measured_at` | TIMESTAMP | no nulo (hora **local**), indexado |
| `notes` | TEXT | opcional |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

Cada medición guarda **la unidad con la que se introdujo**; el selector de la
pestaña convierte el histórico entero para poder comparar y dibujar el gráfico
en una sola escala (1 mmol/L ≈ 18,018 mg/dL).

### `medications`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `user_id` | INTEGER | FK → `users.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `name` | VARCHAR(120) | no nulo, `CHECK (length(name) >= 1)` |
| `dose` | VARCHAR(60) | no nulo |
| `days` | VARCHAR(7) | no nulo → siete flags `0`/`1` en el orden `L M X J V S D` |
| `times` | VARCHAR(255) | no nulo → `"HH:MM,HH:MM,…"` |
| `active` | BOOLEAN | no nulo, por defecto `True`, indexado |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

`active = False` **pausa** el medicamento (deja de generar tomas) sin borrar su
historial; el botón *Pausar* es la única vía para cambiar ese estado.

### `medication_intakes`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | INTEGER | PK, autoincremental |
| `user_id` | INTEGER | FK → `users.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `medication_id` | INTEGER | FK → `medications.id`, no nulo, `ON DELETE CASCADE`, indexado |
| `scheduled_date` | DATE | no nulo, indexado |
| `scheduled_time` | TIME | no nulo |
| `status` | ENUM `intake_status` | no nulo → `'pendiente'` \| `'tomado'` \| `'omitido'` |
| `taken_at` | TIMESTAMP | opcional: hora **real** de la toma |
| `created_at` | TIMESTAMP | no nulo, por defecto `utcnow()` |

Restricción única `uq_intake_slot (medication_id, scheduled_date, scheduled_time)`
e índice `ix_intakes_user_date (user_id, scheduled_date)`.

**Diagrama:**

```
users 1 ──── N blood_pressure_readings
users 1 ──── N glucose_readings
users 1 ──── N medications 1 ──── N medication_intakes
```

> **Zona horaria.** `created_at` se guarda en UTC (marca de auditoría), pero
> `measured_at` y `taken_at` se guardan en **hora local** (`local_now()`): son
> datos que el usuario escribe y edita a mano, y deben verse tal cual se
> introdujeron. Por eso el módulo no usa `utcnow()` para ellos.

---

## 4. Rutas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Redirige al panel o al login |
| `GET/POST` | `/register` | Crear cuenta |
| `GET/POST` | `/login` | Iniciar sesión (usuario **o** correo) |
| `POST` | `/logout` | Cerrar sesión |
| `GET` | `/dashboard` | Panel — parámetros: `view=semanal\|mensual`, `ancla=YYYY-MM-DD`, `categoria=laboral\|cotidiana\|medica` |
| `POST` | `/tasks` | Crear tarea |
| `POST` | `/tasks/<id>/toggle` | Marcar como completada (devuelve JSON) |
| `POST` | `/tasks/<id>/update` | Editar tarea |
| `POST` | `/tasks/<id>/delete` | Eliminar tarea |

### Módulo de salud (`app/health.py`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Página del módulo — parámetros: `tab=tension\|glucemia\|medicamentos`, `rango=7\|30\|90`, `momento`, `unidad`, `fecha` |
| `POST` | `/health/bp` | Registrar tensión arterial |
| `POST` | `/health/bp/<id>/update` | Editar medición de tensión |
| `POST` | `/health/bp/<id>/delete` | Eliminar medición de tensión |
| `POST` | `/health/glucose` | Registrar glucemia |
| `POST` | `/health/glucose/<id>/update` | Editar medición de glucemia |
| `POST` | `/health/glucose/<id>/delete` | Eliminar medición de glucemia |
| `POST` | `/health/medications` | Añadir medicamento al catálogo |
| `POST` | `/health/medications/<id>/update` | Editar medicamento |
| `POST` | `/health/medications/<id>/toggle` | Pausar / activar |
| `POST` | `/health/medications/<id>/delete` | Eliminar medicamento y sus tomas |
| `POST` | `/health/intakes/<id>` | Estado de una toma (`status=pendiente\|tomado\|omitido`); devuelve JSON si llega por `fetch` |

---

## 5. Seguridad implementada

- **Contraseñas hasheadas** con `werkzeug.security` (scrypt + salt por usuario);
  el hash nunca sale de la base de datos ni se registra en logs.
- **Aislamiento por usuario**: toda consulta filtra por `user_id = current_user.id`
  y las tareas ajenas devuelven `404` en vez de `403` (no revelan su existencia).
- **CSRF** en todos los formularios `POST` (token por sesión, comparación en
  tiempo constante, también aceptado por cabecera `X-CSRF-Token` para `fetch`).
- **Login genérico**: el mensaje de error no distingue entre usuario inexistente
  y contraseña incorrecta.
- **Validación en el servidor** de username, email, contraseña, título, categoría
  y fechas; la validación del cliente es sólo una ayuda visual.
- **Rangos clínicos verificados en dos capas**: los `CHECK` de la base de datos
  (`systolic BETWEEN 50 AND 300`, `value > 0`, `days LIKE '%1%'`…) y la
  validación de las rutas, que además rechaza fechas futuras o anteriores a 1970.
- **Checklist idempotente**: la restricción única
  `(medication_id, scheduled_date, scheduled_time)` impide que se dupliquen las
  tomas aunque se recargue la página o se visiten días antiguos.
- **Protección contra open redirect** en el parámetro `next` del login.
- **Cookies** `HttpOnly`, `SameSite=Lax` y `Secure` en producción.
- **Escape de XSS**: autoescapado de Jinja + `|tojson` al pasar datos a JavaScript.

---

## 6. Despliegue en Supabase

### 6.1 Crear la base de datos

1. Entra en [supabase.com](https://supabase.com) → **New project**.
2. Guarda la contraseña de la base de datos que te pide.
3. Ve a **Project Settings → Database → Connection string → URI** y copia el valor.

> **Usa siempre el *pooler* de Supabase**, no la conexión directa: la conexión
> directa caduca y rompe las apps serverless.
>
> - **Session pooler** (puerto `5432`) → recomendado para una app web con usuarios.
> - **Transaction pooler** (puerto `6543`) → para serverless; la app ya desactiva
>   el caché de *prepared statements* automáticamente al detectarlo.

### 6.2 Configurar las variables de entorno

En **Project Settings → API → Environment variables**:

```
DATABASE_URL = postgresql://postgres.TU_PROYECTO:TU_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
SECRET_KEY   = <32 bytes aleatorios>
SESSION_COOKIE_SECURE = 1
```

<details>
<summary>Si prefieres pegarla en <code>Shell secrets</code> en lugar de la UI</summary>

```bash
supabase secrets set \
  DATABASE_URL="postgresql://postgres.TU_PROYECTO:TU_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres" \
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  SESSION_COOKIE_SECURE=1
```
</details>

### 6.3 Ejecutar las migraciones en producción

```bash
flask --app main.py db upgrade
```

La migración inicial (`migrations/versions/aaf8492102e6_esquema_inicial.py`) crea
las tablas, los índices, los tipos `ENUM` y la clave foránea con `ON DELETE CASCADE`.
La segunda (`ba0439e5bb03_modulo_salud.py`) añade las cuatro tablas del módulo
de salud.

Comandos útiles:

```bash
flask --app main.py db current        # revisión aplicada
flask --app main.py db history        # historial
flask --app main.py db downgrade      # revertir (elimina también los tipos ENUM)
flask --app main.py db migrate -m "mensaje"   # generar migración tras editar models.py
```

### 6.4 Despliegue en Vercel

Vercel ejecuta la aplicación como una **Vercel Function**. A diferencia de Render o
Railway, **no necesita gunicorn**: Vercel carga directamente la instancia `app`.

No hace falta ningún fichero de configuración extra. Vercel busca una instancia
llamada `app` en el directorio raíz con alguno de estos nombres:

```
app.py   index.py   server.py   main.py   wsgi.py   asgi.py
```

Nuestro punto de entrada se llama **`main.py`**, así que se detecta solo.

> **Por qué no hay `pyproject.toml`.** Se puede usar `[tool.vercel] entrypoint = "run:app"`
> para apuntar a otro nombre, pero en cuanto existe un `pyproject.toml` Vercel cambia a
> `uv` para resolver las dependencias y exige una tabla `[project]` (PEP 621). Con un
> `pyproject.toml` que sólo contiene `[tool.vercel]` el build falla con
> `No 'project' table found`. Mantener `main.py` y `requirements.txt` evita ese problema.

**Pasos**

1. Sube los cambios: `git add -A && git commit -m "configuracion de Vercel" && git push`
2. Entra en [vercel.com/new](https://vercel.com/new) → **Add New → Project** →
   importa `mk1110/planificador-tareas`.
3. En **Environment Variables** añade (aplicarlas a *Production*, *Preview* y
   *Development*):

   | Nombre | Valor |
   |---|---|
   | `DATABASE_URL` | La cadena del pooler de Supabase (ver 6.2) |
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `SESSION_COOKIE_SECURE` | `1` |
   | `FLASK_DEBUG` | `0` |

4. **Deploy**. Aplica las migraciones desde tu máquina (no desde el build):

   ```bash
   flask --app main.py db upgrade
   ```

> Las migraciones se ejecutan **a mano** y no como build command a propósito: así
> ves los errores y evitas que dos despliegues simultáneos las ejecuten a la vez.

**Notas importantes**

- Vercel escala horizontalmente y abre muchas conexiones. Por eso es
  **imprescindible usar el pooler de Supabase** (`aws-0-...pooler.supabase.com`),
  nunca `db.TU_PROYECTO.supabase.co`. La conexión directa además caduca por IPv6.
- `pool_pre_ping=True` y `pool_recycle=280` ya están en `app/__init__.py` para
  sobrevivir a conexiones cerradas por el pooler.
- Los ficheros estáticos los sirve Vercel desde `public/`, **no** desde
  `app.static_folder`. Por eso la sección 7 compila Tailwind a un `static/` que
  en Vercel habría que mover a `public/`.

### 6.5 Otras plataformas

**Render / Railway / Fly.io** — estas sí necesitan gunicorn:

```bash
pip install gunicorn          # anádelo a requirements.txt
gunicorn "main:app" --chdir . --workers 2 --bind 0.0.0.0:$PORT
```

**Docker**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
ENV PORT=8080
CMD ["sh", "-c", "gunicorn 'run:app' --chdir . --workers 2 --bind 0.0.0.0:${PORT}"]
```

**Notas de producción**

- `FLASK_DEBUG=0` siempre.
- Supabase bloquea conexionesIPv6 directas al puerto `5432`: usa siempre el pooler.
- Si tu plataforma termina las conexiones, `pool_pre_ping=True` y
  `pool_recycle=280` (ya configurados en `app/__init__.py`) mantienen viva la conexión.

---

## 7. Tailwind CSS: CDN vs. build

Las plantillas usan el **Play CDN**:

```html
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
```

Es ideal para desarrollo, pero **no es apto para producción**: compila las clases
en el navegador (~100 KB extra) y ofrece ninguna garantía de rendimiento.

Para producción, compílalo:

```bash
npm install -D tailwindcss @tailwindcss/cli
npx @tailwindcss/cli -i ./static/input.css -o ./static/tailwind.css --minify
```

`static/input.css`:

```css
@import "tailwindcss";
@source "../app/templates";
/* Los badges de categoría, de nivel de tensión, de glucemia y de estado de
   toma viven en app/helpers.py como cadenas completas: sin esta línea el
   build de producción los eliminaría y los colores no aparecerían. */
@source "../app/helpers.py";
@plugin "@tailwindcss/forms";
@custom-variant dark (&:where(.dark, .dark *));
```

Y en `base.html` sustituye el `<script>` del CDN por:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='tailwind.css') }}">
```

> Las clases de Tailwind están escritas **completas** en el código (nunca
> compuestas con `{{ ... }}`) precisamente para que funcionen con ambos métodos.

---

## 8. Comandos habituales

```bash
python main.py                                   # desarrollo
flask --app main.py shell                        # consola con db/User/Task cargados
flask --app main.py routes                       # mapa de rutas
flask --app main.py db upgrade                   # aplicar migraciones
flask --app main.py db migrate -m "nueva columna"
```

Crear datos de prueba desde la consola:

```python
>>> from app.models import Task, Category, Timeframe
>>> from datetime import date, timedelta
>>> db.session.add(Task(user_id=1, title="Comprar comida",
...     category=Category.COTIDIANA, timeframe=Timeframe.SEMANAL,
...     due_date=date.today() + timedelta(days=1)))
>>> db.session.commit()
```

Y para el módulo de salud:

```python
>>> from app.models import BloodPressureReading, GlucoseReading, GlucoseMoment, GlucoseUnit
>>> from app.models import Medication, local_now
>>> db.session.add(BloodPressureReading(user_id=1, systolic=122, diastolic=78,
...     pulse=70, measured_at=local_now(), notes="Reposo"))
>>> db.session.add(GlucoseReading(user_id=1, value=92, unit=GlucoseUnit.MGDL,
...     moment=GlucoseMoment.AYUNAS, measured_at=local_now()))
>>> db.session.add(Medication(user_id=1, name="Metformina", dose="850 mg",
...     days="1111111", times="08:00,20:00"))
>>> db.session.commit()
```

> Las filas de `medication_intakes` **no se crean a mano**: se generan solas al
> abrir `/health?tab=medicamentos` por primera vez para cada día.

---

## 9. Características de la interfaz

- **Vista semanal**: los 7 días en una **tira horizontal con scroll** (no en
  columnas comprimidas), de modo que cada día conserva un ancho legible y sus
  tareas se leen **una debajo de otra**. El día actual se resalta; las flechas
  `‹` `›` desplazan la tira en escritorio.
- **Detalle de día**: al pulsar un día (su cabecera o el botón *Ver todas las
  tareas del día*) se abre un modal con **todas** las tareas de ese día en una
  rejilla de dos columnas, más un botón para añadir una tarea ya fechada.
- **Vista mensual**: rejilla calendario con los días fuera del mes atenuados y
  las tareas resumidas como chips de color.
- **Navegación de períodos**: anterior / Hoy / siguiente, por semana o mes.
- **Filtro por categoría** que se combina con la vista activa.
- **Resumen**: total, pendientes, completadas y vencidas del período.
- **Colores por categoría**: 🔵 Laboral · 🟢 Cotidiana · 🔴 Médica.
- **Modo oscuro** conmutable y persistente en `localStorage`.
- **Marcar como completada sin recargar** la página (`fetch` + JSON).
- **Modales** de creación y edición, con confirmación al eliminar.
- Diseño adaptable de móvil a escritorio.

### Módulo de salud

- **Tres pestañas** — 🫀 Tensión arterial · 🩸 Glucemia · 💊 Medicamentos —
  en la misma página, con la sección enlazada desde la navegación superior.
- **Tensión arterial**: sistólica, diastólica y pulso (opcional), fecha y hora
  con edición manual y notas. Resumen con la última medición, las medias del
  período y **clasificación por niveles** (Normal · Elevada · Grado 1 · Grado 2 ·
  Crisis) según los criterios de la AHA.
- **Glucemia**: valor en **mg/dL o mmol/L**, momento de la medición (en ayunas,
  antes de comer, 2 h después de comer, antes de dormir, otro), fecha, hora y
  notas. El **selector de unidad convierte todo el histórico** para poder
  compararlo, y cada fila muestra *en rango / alta / baja* según el momento.
- **Gráfico de evolución temporal** dibujado en SVG por el navegador (sin
  librerías externas): una línea por serie, con tooltip por punto y líneas de
  referencia en 120/80 mmHg para la tensión. Las series con huecos —el pulso
  es opcional— se dibujan en tramos separados para no unir puntos que no son
  consecutivos.
- **Filtros**: 7 / 30 / 90 días en ambas mediciones y filtro por momento del día
  en la glucemia.
- **Catálogo de medicamentos**: nombre, dosis, días de la semana (pestañas
  L M X J V S D) y horarios (`08:00, 14:00, 20:00`, con un selector de hora
  que los añade y ordena sin duplicados). Se pueden **pausar** sin perder el
  historial.
- **Checklist diario**: las tomas del día se generan solas la primera vez que se
  abre el día, agrupadas por medicamento, con tres estados — ✅ tomado,
  ⛔ omitido, ↺ pendiente — que se cambian **sin recargar** (`fetch` + JSON) y
  anotan la **hora real** de la toma y los minutos de retraso. Navegación por
  días (anterior · hoy · siguiente) y porcentaje de cumplimiento de los últimos
  7 días.
- **Aviso** en las tres pestañas: los rangos son orientativos y no sustituyen al
  profesional sanitario.

> **Editable sin saltos:** al cambiar los días u horarios de un medicamento se
> borran sus tomas **pendientes** de hoy en adelante (se recrean con el horario
> nuevo); las ya tomadas u omitidas se conservan porque son historial.