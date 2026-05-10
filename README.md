# Dynasty Archives

**Dynasty Archives** is a small, opinionated history catalog: browse dynasties and the people who ruled them, trace events on a timeline, map territories to empires, and (if you’re an admin) curate the database behind it. The stack is familiar—**Flask**, **PostgreSQL**, **Jinja** templates—with **Firebase** (Realtime Database + optional Google Sign-In) and **Supabase Storage** for backup files, plus a deliberate split between repo-root **`images/`** and admin uploads.

Whether you’re demoing a course project or extending the schema, this README walks you from empty clone to a running app, then calls out **known limitations** (especially around images and paths) so you don’t chase ghosts.

---

## Why this project?

- **Structured history**: Reigns, successions, wars, and family links are first-class data—not just prose pages.
- **Real database design**: Enums, triggers, views, stored procedures, and audit logging live in **`sql/schema.sql`** (see also **`erd-explanation.md`**).
- **Two audiences**: Public readers get search and filters; **admins** get CRUD, backups, and a workflow for viewer-submitted corrections.

---

## Table of contents

1. [What you can do](#what-you-can-do)
2. [What you need installed](#what-you-need-installed)
3. [Setup from zero](#setup-from-zero) — follow in order
4. [Configuration reference](#configuration-reference)
5. [First login & admin user](#first-login--admin-user)
6. [Running & URLs](#running--urls)
7. [Images & static assets](#images--static-assets)
8. [Project layout](#project-layout)
9. [Documentation & database docs](#documentation--database-docs)
10. [Running tests](#running-tests)
11. [Security](#security)
12. [Troubleshooting](#troubleshooting)
13. [Known limitations & improvements](#known-limitations--improvements)
14. [Contributing](#contributing)
15. [License](#license)

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
| Statistics | `/stats` | Highlights + succession chain (reads **`vw_succession_chain`**) |
| Search | `/search` | Rulers, dynasties, events, territories |
| Register / Login | `/register`, `/login` | Passwords stored hashed (**Werkzeug**) |

**Viewers** (after login) can suggest edits to ruler/dynasty fields; suggestions land in **`Edit_Request`** for admins to approve or decline.

### Admins (`role = admin`)

| Area | Path prefix | Capabilities |
|------|-------------|----------------|
| Dashboard | `/admin/` | Overview, backup shortcuts, recent activity |
| CRUD | `/admin/dynasties`, `/admin/persons`, `/admin/events` | Create/edit/delete; optional first reign via **`sp_add_ruler`** |
| Edit requests | `/admin/edit-requests` | Approve or decline viewer suggestions |
| Backups | `POST /admin/backup`, `/admin/backups`, `/admin/backups/firebase` | Per-table **`pg_dump`** → Firebase RTDB + Supabase (needs **`DATABASE_URL`** + **`pg_dump`**) |
| Restore | Firebase backup UI | **Destructive**: truncates data tables then loads SQL; password confirmation |
| Clear DB | `/admin/clear-db` | **Very destructive** — typed confirmation + password |

---

## What you need installed

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | App & tests (3.13 works locally) |
| **PostgreSQL** | Primary database |
| **`psql`** (optional but useful) | Apply **`sql/schema.sql`** |
| **`pg_dump`** on `PATH` | Admin **Backup Database** button |
| **Firebase project** | Startup requires web config + Realtime DB URL; **service account JSON** for Admin SDK |
| **Supabase project** | App initializes client at startup — URL, **service role** key, storage **bucket** |

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

Use URL-encoding for special characters in the password (or set a password without special chars for local dev).

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

Repo-root **`images/`** is served at **`/images/<path>`** (see [Images & static assets](#images--static-assets)).

---

## Images & static assets

Understanding where images live saves a lot of “broken portrait” debugging.

| Source | How it’s served | Typical use |
|--------|-----------------|-------------|
| **`images/`** (repo root) | Flask route **`/images/<path>`** in **`app/__init__.py`** | Curated assets checked into git; seeds and templates often reference **`/images/persons/...`** etc. |
| **Admin uploads** | **`app/uploads.py`** (`save_image_local_path`) writes under **`images/<folder>/`**, returns a **`/images/...`** URL; also mirrors into **`app/static/images/...`** as a backup copy | New ruler/dynasty/event images from the admin UI |
| **External URLs** | Stored as-is in the DB (`http...` or `data:...`) | Hotlinking or pasted URLs; no local file required |

**Normalization in admin** (`_normalize_local_image_path` in **`app/routes/admin.py`**): accepts `https://`, `data:`, paths starting with **`/images/`**, or bare filenames (resolved under the appropriate **`images/`** subfolder). Mismatched folder names in the database (e.g. typo **`dyansties`** vs **`dynasties`**) or missing files under **`images/`** will still produce **404** in the browser even though the app is “correct.”

**Practical tips**

- Prefer consistent path prefixes: **`/images/<category>/<file>`** for anything meant to be local.
- After clone, if **`images/`** is empty or gitignored locally, expect broken thumbnails until you restore assets or re-upload.
- **`app/static/uploads/`** may contain legacy or one-off uploads; not all templates may point there—check the actual `image_url` value in PostgreSQL when something doesn’t render.

---

## Project layout

```
DynastyArchives/
├── app/
│   ├── __init__.py          # Flask app, CSRF, login, /images route
│   ├── db.py                # execute_query, connections
│   ├── firebase.py          # Firebase Admin / RTDB
│   ├── supabase_client.py   # Supabase client & backup bucket
│   ├── uploads.py           # Admin image saves (images/ + static mirror)
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
| Images 404 | File exists under **`images/`**; DB path matches (**`/images/...`**); no typos in folder names; see [Images & static assets](#images--static-assets). |
| CSRF errors on POST | Forms include **`csrf_token()`**; tests use `WTF_CSRF_ENABLED=False` in **`tests/conftest.py`**. |
| Admin redirect not to `/login` | Set **`login_manager.login_view = "auth.login"`** (see [First login](#first-login--admin-user)). |

---

## Known limitations & improvements

This section is intentionally honest: it describes rough edges in the current codebase and sensible next steps if you fork or extend the project.

### Images and paths

- **Two physical locations**: Primary serving is **`/images/`** → repo **`images/`**; uploads also copy to **`app/static/images/`**. Templates and DB values may not always agree on which convention was used historically—when in doubt, inspect **`image_url`** in SQL.
- **Typos and legacy folders**: Some seeds or assets use nonstandard directory spellings (e.g. **`dyansties`**). Those paths work only if the matching folder exists; standardizing names would reduce confusion.
- **Missing assets after clone**: Large **`images/`** trees may be omitted from a clone (`.gitignore`, LFS, or manual curation). Broken images are often “data/env” issues, not Flask routing.
- **External-only images**: Rows that store full `https://` URLs depend on third-party availability and hotlinking policies; there is no automatic mirror to local storage.

### Auth and admin UX

- **`login_view` mismatch**: If `login_manager.login_view` still points at **`admin.login`** while login lives under **`auth.login`**, unauthenticated visits to admin may not redirect cleanly—aligning the blueprint name fixes it (see [First login](#first-login--admin-user)).
- **Role gates**: Ensure production **`User_Account.role`** values match what **`@role_required`** expects (`admin` vs `viewer`).

### Database and schema

- **`Edit_Request` polymorphism**: Suggestions reference ruler or dynasty (and related fields) in a flexible way; there may be no single FK graph that enforces “this row still exists” at the database level—application logic handles resolution; DB-level constraints could be tightened in a future migration.
- **Views vs templates**: **`vw_succession_chain`** is used on the stats page; other views in **`schema.sql`** (e.g. reign-duration helpers) might be duplicated or partially inlined in Python—consolidating on views or documenting “template uses X only” would clarify intent.

### Backups and restore

- **Operational deps**: Backups require **`pg_dump`** and a valid **`DATABASE_URL`**; CI or minimal containers without PostgreSQL client tools will not be able to run the same path as your laptop.
- **Restore is destructive**: Truncates configured tables before load; always verify backup provenance and use a disposable database when experimenting.
- **Cloud vs local parity**: Firebase RTDB and Supabase hold **snapshots**; they are not a substitute for migration discipline or versioned **`schema.sql`** unless you treat dumps as the source of truth on purpose.

### General polish

- **Rate limiting storage**: Default in-memory limiter is fine for a single process; multiple Gunicorn workers need shared storage (e.g. Redis) for consistent limits.
- **Production checklist**: HTTPS, `debug=False`, secret injection, and log aggregation are left to the deployer—this repo optimizes for clarity in development.

---

## Contributing

1. Use a focused branch and clear commits.
2. Run **`python -m pytest tests/ -v`** after DB-related changes.
3. Update **`sql/schema.sql`** and this README when you add migrations, env vars, or major behavior.
