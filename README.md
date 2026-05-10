# Dynasty Archives

Dynasty Archives is a **Flask** web application for exploring historical **dynasties**, **rulers (persons)**, **reigns**, **events**, **territories**, and relationships such as succession and family ties. Data lives in **PostgreSQL**. Optional integrations add **Google Sign-In** (Firebase Auth), **SQL backups** to **Firebase Realtime Database** and **Supabase Storage**, and local image uploads.

---

## Features

### Public site

| Area | Description |
|------|-------------|
| **Home** | High-level counts and entry points. |
| **Rulers** | List and detail with filters (dynasty, era, search, sort). |
| **Dynasties** | List and detail with linked rulers, territories, and events. |
| **Events** | List with optional `type` filter; detail pages. |
| **Timeline** | Events with filters (year range, dynasty, ruler, event type). |
| **Territories** | Regions and control timelines via dynasty–territory links. |
| **Wars & battles** | Events limited to `war` and `battle` types. |
| **Stats** | Aggregated insights (e.g. reigns, succession chain view). |
| **Search** | Unified search over rulers, dynasties, events, territories. |

### Accounts and roles

- **Register** (`/register`) and **login** (`/login`) with username and password (stored hashed with **Werkzeug**).
- **Google Sign-In** via Firebase (POST `/auth/google-login` with ID token); dedicated users may use a `GOOGLE_AUTH` password sentinel in the database.
- **`admin`**: full **admin dashboard** at `/admin/` — CRUD for dynasties, persons, events; backups; edit-request review; optional full DB clear (destructive).
- **`viewer`**: can browse the site and submit **edit suggestions** for ruler and dynasty fields (stored in `Edit_Request` for admins to approve or decline).

### Admin and data management

- CRUD for **Dynasty**, **Person** (optional first reign via `sp_add_ruler`), and **Event**, with optional image uploads and relationship syncing (spouses, parents/children, succession, person–event links, dynasty–territory, etc.).
- **Backup** (`POST /admin/backup`): per-table `pg_dump` (data-only), cleaned SQL, upload to Firebase RTDB and Supabase bucket; listing and download from the admin UI.
- **Restore** from Firebase backup metadata (multi-table or legacy format); requires admin password confirmation.
- **Audit log** and triggers for deletes/updates where defined in schema.

### Technical highlights

- **SQL schema** in `sql/schema.sql`: tables, enums, indexes, triggers, views (`vw_reign_durations`, `vw_succession_chain`, `vw_wars_and_battles`, `vw_territory_timeline`), and procedures (`sp_add_ruler`, `sp_record_succession`, etc.).
- **Images**: project-level assets under `images/` are served at **`/images/<path>`** (see `create_app` in `app/__init__.py`). Admin uploads may also write under `app/static/uploads/`.
- **CSRF** protection via **Flask-WTF**; **rate limiting** on login via **Flask-Limiter**.

---

## Requirements

- **Python** 3.11+ (3.13 is used in CI/local setups; adjust if needed).
- **PostgreSQL** (compatible with `psycopg2` / `psycopg2-binary`).
- **Firebase** project (web config + Realtime Database + optional service account for Admin SDK).
- **Supabase** project (URL, service role key, storage bucket for backups — optional if you only use Firebase for backups, but the app initializes the Supabase client at startup).

---

## Quick start

### 1. Clone and virtual environment

```bash
git clone <your-repo-url> DynastyArchives
cd DynastyArchives
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL database

1. Create a database (example name: `dynasty_db`).
2. Apply the schema:

   ```bash
   psql -h localhost -U postgres -d dynasty_db -f sql/schema.sql
   ```

3. Create at least one **admin** user. Passwords must be **Werkzeug**-compatible hashes (the login route uses `check_password_hash`). Options:
   - Use **`/register`** if enabled for your deployment, then promote the user to `admin` in SQL, or
   - Insert/update via a small Python one-liner or admin tool using `werkzeug.security.generate_password_hash`.

Example role update (after you have a `user_id`):

```sql
UPDATE user_account SET role = 'admin' WHERE username = 'yourname';
```

### 3. Environment variables and secrets folder

Copy `.env.example` to **`secrets/.env`** (preferred). Put your Firebase **`serviceAccountKey.json`** in **`secrets/`** as well (see `secrets/README.md`).

`config.py` loads env files in order: **`secrets/.env`**, then optional legacy **`/.env`** at the repo root, then **`app/.env`**. Use **`secrets/`** as the single place for passwords and keys so they stay out of the repo (the folder is gitignored except `secrets/README.md`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `DB_HOST` | Yes | PostgreSQL host. |
| `DB_NAME` | Yes | Database name. |
| `DB_USER` | Yes | DB user. |
| `DB_PASSWORD` | Yes | DB password. |
| `SECRET_KEY` | Yes | Flask session / CSRF secret; use a long random string. |
| `DATABASE_URL` | Recommended | `postgresql://...` URL used by **pg_dump** backup/restore tooling. If omitted, some code paths may build from `DB_*`; keep this aligned with your DB. |
| `FIREBASE_API_KEY` | Yes | Web API key (client config). |
| `FIREBASE_AUTH_DOMAIN` | Yes | e.g. `project.firebaseapp.com`. |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID. |
| `FIREBASE_DATABASE_URL` | Yes | Realtime Database URL (backups metadata). |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Yes* | Path relative to repo root, usually **`secrets/serviceAccountKey.json`** (default if unset). |
| `SUPABASE_URL` | Yes | Supabase project URL. |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (server-side only; never expose in the browser). |
| `SUPABASE_BACKUP_BUCKET` | Yes | Storage bucket name for SQL backup files. |

The entire **`secrets/`** directory (except its README) is listed in **`.gitignore`**.

### 4. Supabase storage

Create a **bucket** matching `SUPABASE_BACKUP_BUCKET`. The admin backup flow uploads `.sql` files into timestamped folders.

### 5. Run the application

From the repo root:

```bash
python run.py
```

Default in `run.py`: **debug** mode, port **5000** — open `http://127.0.0.1:5000`.

**Production:** use a WSGI server (e.g. Gunicorn, Waitress), set `debug=False`, and configure HTTPS and secrets via the environment (not committed files).

---

## Project layout

```
DynastyArchives/
├── app/
│   ├── __init__.py       # create_app(), login, /images route, CSRF
│   ├── db.py             # PostgreSQL helpers (execute_query, audit)
│   ├── firebase.py       # Firebase Admin / RTDB helpers
│   ├── supabase_client.py
│   ├── uploads.py        # Local image save helpers
│   ├── routes/
│   │   ├── user.py       # Public blueprint (no URL prefix)
│   │   ├── admin.py      # /admin blueprint
│   │   └── auth.py       # login, register, Google, logout
│   ├── templates/        # Jinja2 HTML
│   └── static/           # Static assets + optional uploads subtree
├── config.py             # Config dataclass; loads secrets/.env then legacy .env paths
├── secrets/              # Local-only: .env, serviceAccountKey.json (gitignored; see secrets/README.md)
├── images/               # Canonical image tree served at /images/
├── sql/
│   └── schema.sql        # Full PostgreSQL DDL + seeds (adjust seed user)
├── tests/                # pytest suite (see below)
├── run.py                # Dev entrypoint
├── requirements.txt
├── .env.example
└── README.md
```

---

## Authentication notes

- After login, **`admin`** users are redirected to **`/admin/`** (dashboard); **`viewer`** users to **`/`**.
- **`login_manager.login_view`** is currently set to **`admin.login`** in `app/__init__.py`. The actual login endpoint lives on the **`auth`** blueprint as **`auth.login`**. If unauthenticated access to admin routes does not redirect to `/login` as expected, set `login_manager.login_view = "auth.login"` (or add a named route alias) so Flask-Login resolves the correct URL.

---

## Testing

The **`tests/`** directory contains a **pytest** suite that exercises the app against a **real PostgreSQL** instance (same `DB_*` / `DATABASE_URL` as your environment). External services (**Firebase**, **Supabase**, Google Admin init) are **mocked** in `tests/conftest.py` so imports succeed without live keys.

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Tests create temporary **`User_Account`** rows and clean them up; many tests also insert/delete dynasties, persons, or events with unique names. **Do not** point tests at a production database unless you accept that risk.

Firebase **restore** runs **TRUNCATE**, replay **INSERT**s, **`INSERT` into `Audit_Log`**, and **`commit`** on one connection — so if anything fails before commit, **nothing** from that restore (including the audit row) persists. **Restore tests** intentionally **mock** the raw `psycopg2.connect` used only for restore’s positional DSN URL so the suite does not `TRUNCATE` your database. A full manual restore from the admin UI **will** wipe and reload data per the implementation — use only on backups you trust and environments you can afford to reset.

---

## Security checklist

- Never commit **`secrets/.env`**, **`secrets/*.json`**, root **`.env`**, **`app/.env`**, or **Supabase service keys**. Confirm **`secrets/`** stays ignored except **`secrets/README.md`**.
- Keep **`SECRET_KEY`** strong and unique per environment.
- Restrict **`SUPABASE_SERVICE_KEY`** to server-side code only.
- Admin actions (**backup**, **restore**, **clear database**) are destructive or sensitive; protect admin accounts and use HTTPS in production.
- Login is rate-limited; review **Flask-Limiter** storage for multi-worker deployments.

---

## Troubleshooting

| Issue | Suggestions |
|--------|-------------|
| `RuntimeError` about Firebase env vars | Set all four: `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_DATABASE_URL`. |
| DB connection errors | Verify `DB_*` and that PostgreSQL accepts TCP connections from your host. |
| Backup fails on `pg_dump` | Ensure **`DATABASE_URL`** is set and `pg_dump` is on `PATH`; URL must include host, user, and database name. |
| Images 404 | Use paths under `images/` or URLs your browser can reach; admin normalizes some paths to `/images/...`. |
| CSRF errors on forms | Ensure templates include `csrf_token()`; for API-style tests, disable CSRF in test config (see `tests/conftest.py`). |

---


## Contributing

1. Use a feature branch and keep commits focused.
2. Run **`python -m pytest tests/ -v`** before opening a PR when DB-backed behavior changes.
3. Update **`sql/schema.sql`** and this **README** when you add migrations, env vars, or major features.
