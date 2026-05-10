# Dynasty Archives

A **Flask** web app for exploring historical **dynasties**, **rulers**, **reigns**, **events**, **territories**, and relationships (succession, family, wars). All catalog data lives in **PostgreSQL**. The app can use **Firebase** (Google Sign-In + Realtime Database backups) and **Supabase Storage** (backup files), plus local images under `/images/`.

---

## Table of contents

1. [What you can do](#what-you-can-do)
2. [What you need installed](#what-you-need-installed)
3. [Setup from zero](#setup-from-zero) — follow in order  
4. [Configuration reference](#configuration-reference)
5. [First login & admin user](#first-login--admin-user)
6. [Running & URLs](#running--urls)
7. [Project layout](#project-layout)
8. [Documentation & database docs](#documentation--database-docs)
9. [Running tests](#running-tests)
10. [Security](#security)
11. [Troubleshooting](#troubleshooting)
12. [Contributing](#contributing)

---

## What you can do

### Visitors & viewers

| Page | Path | Notes |
|------|------|--------|
| Home | `/` | Summary stats |
| Rulers | `/rulers` | Filters: search, dynasty, era, sort; **`?no_events=1`** = rulers with no event participation |
| Ruler detail | `/rulers/<id>` | Reigns, family, events, succession |
| Dynasties | `/dynasties`, `/dynasties/<id>` | Linked rulers, territories, events |
| Events | `/events`, `/events/<id>` | Filter by **`?type=`** (war, battle, treaty, …) |
| Timeline | `/timeline` | Year filters, dynasty, ruler, event type |
| Territories | `/territories`, `/territories/<id>` | Control timelines |
| Wars & battles | `/wars`, `/wars/<id>` | Only **war** / **battle** events |
| Statistics | `/stats` | Highlights + succession chain (uses **`vw_succession_chain`**) |
| Search | `/search` | Rulers, dynasties, events, territories |
| Register / Login | `/register`, `/login` | Passwords stored hashed (**Werkzeug**) |

**Viewers** (after login) can suggest edits to ruler/dynasty fields; suggestions go to **`Edit_Request`** for admins.

### Admins (`role = admin`)

| Area | Path prefix | Capabilities |
|------|----------------|--------------|
| Dashboard | `/admin/` | Overview, links to CRUD and backups |
| CRUD | `/admin/dynasties`, `/admin/persons`, `/admin/events` | Create/edit/delete; optional **first reign** via stored procedure **`sp_add_ruler`** |
| Edit requests | `/admin/edit-requests` | Approve or decline viewer suggestions |
| Backups | `/admin/backup` (POST), `/admin/backups`, Firebase archive | **`pg_dump`** per table → Firebase RTDB + Supabase bucket (needs **`DATABASE_URL`** + CLI tools) |
| Restore | Firebase backup UI | **Destructive**: truncates data tables then loads SQL; confirm with account password |
| Clear DB | `/admin/clear-db` | **Very destructive** — requires typed confirmation + password |

---

## What you need installed

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | App & tests (3.13 works locally) |
| **PostgreSQL** | Primary database |
| **`psql`** (optional but useful) | Apply `sql/schema.sql` |
| **`pg_dump`** on `PATH` | Admin **backup** button (`DATABASE_URL`) |
| **Firebase project** | Required at startup: web API fields + Realtime DB URL; **service account JSON** for Admin SDK (backups / optional Google login server-side) |
| **Supabase project** | App initializes client at startup — URL, **service role** key, storage **bucket** name |

---

## Setup from zero

Work through these steps once per machine.

### Step 1 — Get the code and a virtual environment

```bash
git clone <your-repo-url> DynastyArchives
cd DynastyArchives
python -m venv .venv
```

Activate and install dependencies:

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — Create the PostgreSQL database

Create an empty database (name is up to you; examples use `dynasty_db`):

```bash
createdb -h localhost -U postgres dynasty_db
# or use pgAdmin / any SQL client
```

Apply the schema (creates tables, enums, triggers, views, procedures):

```bash
psql -h localhost -U postgres -d dynasty_db -f sql/schema.sql
```

The seed line inserts a placeholder admin row — replace its password with a real hash before relying on it (see [First login & admin user](#first-login--admin-user)).

### Step 3 — Secrets and environment variables

1. Copy **`.env.example`** to **`secrets/.env`** (create the `secrets` folder if needed).
2. Download your Firebase **service account** JSON from the Firebase console → Project settings → Service accounts → Generate new private key.
3. Save it as **`secrets/serviceAccountKey.json`** (or another path and set **`FIREBASE_SERVICE_ACCOUNT_JSON`** accordingly).

Fill **`secrets/.env`** with real values. Minimum:

- **`DB_HOST`**, **`DB_NAME`**, **`DB_USER`**, **`DB_PASSWORD`** — match the database you created.
- **`SECRET_KEY`** — long random string (sessions & CSRF).
- All **`FIREBASE_*`** and **`SUPABASE_*`** variables listed in [.env.example](.env.example).

**`DATABASE_URL`** for backups should be a proper libpq URL, for example:

```text
postgresql://USER:PASSWORD@HOST:5432/dynasty_db
```

Use URL-encoding for special characters in the password (or set password without special chars for local dev).

Load order (first file wins per variable if not already in the OS environment):

1. **`secrets/.env`**
2. **`.env`** at repo root (optional legacy)
3. **`app/.env`** (optional legacy)

See **`secrets/README.md`** for details.

### Step 4 — Supabase storage bucket

In the Supabase dashboard → Storage, create a bucket whose name matches **`SUPABASE_BACKUP_BUCKET`** (e.g. `dynasty-backups`). The backup job uploads `.sql` files there.

### Step 5 — Run the app

From the repository root:

```bash
python run.py
```

Open **http://127.0.0.1:5000** — default is **debug** on port **5000**.

---

## Configuration reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Yes | PostgreSQL connection (`config.Config`). |
| `SECRET_KEY` | Yes | Flask sessions and CSRF. |
| `DATABASE_URL` | Strongly recommended | **`pg_dump`** / restore URL; must match your DB for backups to work. |
| `FIREBASE_API_KEY` | Yes | Client/web config. |
| `FIREBASE_AUTH_DOMAIN` | Yes | e.g. `your-project.firebaseapp.com`. |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID. |
| `FIREBASE_DATABASE_URL` | Yes | Realtime Database URL (backup metadata). |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Yes* | Path from repo root; default **`secrets/serviceAccountKey.json`**. |
| `SUPABASE_URL` | Yes | Supabase project URL. |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key — **server only**, never commit. |
| `SUPABASE_BACKUP_BUCKET` | Yes | Storage bucket name for SQL backup files. |

\*The app imports Firebase Admin using this file path.

---

## First login & admin user

Passwords in **`User_Account`** must be **Werkzeug** hashes (`generate_password_hash` / `check_password_hash`).

**Option A — Register then promote (if `/register` is enabled)**

1. Register at **`/register`**.
2. In PostgreSQL:

```sql
UPDATE user_account SET role = 'admin' WHERE username = 'your_username';
```

**Option B — Insert or update with Python** (run from repo root with venv activated):

```python
from werkzeug.security import generate_password_hash
hash = generate_password_hash("YourSecurePassword123")
print(hash)
```

Paste the hash into SQL:

```sql
INSERT INTO user_account (username, password, role, email, is_active)
VALUES ('admin', '<paste_hash_here>', 'admin', 'you@example.com', TRUE);
```

Or update the seeded `admin` user from `schema.sql` (replace `CHANGE_ME_TO_BCRYPT_HASH`).

**Roles**

- **`admin`** → after login, redirect to **`/admin/`**.
- **`viewer`** → redirect to **`/`**.

**Note:** `login_manager.login_view` in **`app/__init__.py`** may still say `admin.login` while the real route is **`auth.login`**. If admin pages do not send you to `/login`, set `login_manager.login_view = "auth.login"` in `create_app`.

---

## Running & URLs

| Environment | Command | URL |
|-------------|---------|-----|
| Development | `python run.py` | http://127.0.0.1:5000 |

**Production:** run behind a production WSGI server (e.g. Gunicorn, Waitress), `debug=False`, HTTPS, and inject secrets via the environment — never rely on committed files.

### Quick route map

| Audience | Prefix | Examples |
|----------|--------|----------|
| Public | *(none)* | `/`, `/dynasties`, `/events`, `/timeline` |
| Auth | | `/login`, `/logout`, `/register` |
| Admin | `/admin` | `/admin/`, `/admin/dynasties`, `/admin/persons`, `/admin/events` |

Static images from the repo **`images/`** folder are served at **`/images/<path>`**.

---

## Project layout

```
DynastyArchives/
├── app/
│   ├── __init__.py          # Flask app, CSRF, login, /images
│   ├── db.py                # execute_query, connections
│   ├── firebase.py          # Firebase Admin / RTDB
│   ├── supabase_client.py   # Supabase client & backup bucket
│   ├── uploads.py           # Admin image saves
│   ├── routes/
│   │   ├── user.py          # Public pages
│   │   ├── admin.py         # Admin CRUD, backup, restore
│   │   └── auth.py          # Login, register, Google, logout
│   ├── templates/
│   └── static/
├── config.py                # Loads secrets/.env then legacy .env paths
├── secrets/                 # Local only — .env, serviceAccountKey.json (see secrets/README.md)
├── images/                  # Served at /images/
├── sql/
│   └── schema.sql           # Full DDL: enums, triggers, views, procedures
├── tests/                   # pytest (real PostgreSQL)
├── run.py
├── requirements.txt
├── .env.example
├── README.md
├── database-schema-diagram.md
├── erd-explanation.md
└── erd-complete-advanced.md
```

---

## Documentation & database docs

| File | Contents |
|------|----------|
| **`sql/schema.sql`** | Source of truth for tables, constraints, triggers, views, procedures |
| **`database-schema-diagram.md`** | Tables, columns, FK arrows, Mermaid diagram |
| **`erd-explanation.md`** | Conceptual ER: cardinality, participation, weak entities |
| **`erd-complete-advanced.md`** | Chen-style hand-draw guide |

---

## Running tests

Tests use a **real PostgreSQL** database (same **`DB_*`** / **`DATABASE_URL`** as your env). Firebase and Supabase clients are **mocked** in **`tests/conftest.py`** so tests run without live cloud keys.

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

**Important**

- Tests insert/delete test rows (including temporary users). Use a **dev database**, not production.
- Restore-related tests **mock** `psycopg2.connect` for the restore URL so your DB is not truncated. A **manual restore** from the admin UI still **wipes** configured tables — only use trusted backups and disposable environments.

Firebase restore runs **TRUNCATE**, replay **INSERT**s, **`Audit_Log`** insert, and a single **`commit`** on one connection — if anything fails before commit, **nothing** from that restore persists.

---

## Security

- Never commit **`secrets/.env`**, **`secrets/*.json`**, root **`.env`**, **`app/.env`**, or keys in screenshots.
- Rotate **`SECRET_KEY`** if it leaks.
- **`SUPABASE_SERVICE_KEY`** and Firebase service account JSON are **server secrets** only.
- Protect **admin** accounts; backup / restore / clear-db are high-impact.
- Login is **rate-limited**; for multiple workers configure Flask-Limiter storage appropriately.

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `RuntimeError` about Firebase env vars | All four must be set: `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_DATABASE_URL`. |
| Cannot connect to PostgreSQL | `DB_*`, firewall, `pg_hba.conf`, database exists. |
| Backup fails | **`DATABASE_URL`** set correctly; **`pg_dump`** on PATH; user can connect to that database. |
| Images 404 | Paths under **`images/`** or URLs that resolve; admin may normalize to **`/images/...`**. |
| CSRF errors on POST | Forms include **`csrf_token()`**; tests use `WTF_CSRF_ENABLED=False` in **`tests/conftest.py`**. |
| Admin redirect not to `/login` | Set **`login_manager.login_view = "auth.login"`** (see [First login](#first-login--admin-user)). |

---

## Contributing

1. Use a focused branch and clear commits.
2. Run **`python -m pytest tests/ -v`** after DB-related changes.
3. Update **`sql/schema.sql`** and this README when you add migrations, env vars, or major behavior.

---

## License

Add your license here (e.g. MIT) or your course attribution if required.
