# Planificador de Tareas Multiusuario

Aplicación web adaptable para gestionar tareas personales divididas en tres
categorías — **Laboral**, **Cotidiana** y **Médica** — con vistas de planificación
**semanal** y **mensual**. Cada usuario sólo ve y gestiona sus propias tareas.

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
│   ├── models.py              # User y Task (SQLAlchemy)
│   ├── routes.py              # Blueprints: auth (registro/login) y main (panel/CRUD)
│   ├── security.py            # Protección CSRF por sesión
│   ├── helpers.py             # Formato de fechas, períodos semanal/mensual, metadatos UI
│   └── templates/
│       ├── base.html          # Layout, navegación, CDN de Tailwind, modo oscuro
│       ├── login.html         # Inicio de sesión
│       ├── register.html      # Registro de usuario
│       ├── dashboard.html     # Panel: vistas semanal/mensual, filtros, modales
│       ├── _task_card.html    # Macro reutilizable de tarjeta de tarea
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