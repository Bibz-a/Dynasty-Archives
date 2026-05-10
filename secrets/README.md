# Secrets (local only)

Put **private** files here. Only **`README.md`** and **`.gitignore`** here are meant for Git; everything else is blocked by `secrets/.gitignore` (`*` with narrow exceptions).

## What goes here

| File | Purpose |
|------|---------|
| **`.env`** | Database URL, `SECRET_KEY`, Supabase keys, Firebase web config strings, paths, etc. Copy from the repo root `.env.example` and fill in real values. |
| **`serviceAccountKey.json`** | Firebase **Admin SDK** service account (download from Firebase console → Project settings → Service accounts). |

You may use other filenames if you set `FIREBASE_SERVICE_ACCOUNT_JSON` in `.env` to a path relative to the repo root (e.g. `secrets/my-firebase.json`).

## Load order

`config.py` loads env files in this order (first file wins per variable if not already in the process environment):

1. `secrets/.env`
2. `.env` (repository root, optional legacy)
3. `app/.env` (optional legacy)

After moving secrets here, remove duplicate `.env` files from the repo root or `app/` if you no longer need them.
