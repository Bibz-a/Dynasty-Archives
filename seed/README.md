# Seed data

SQL in this folder loads the **catalog** tables (dynasties, rulers, reigns, territories, events, links) with the same narrative content as the reference dataset.

## Prerequisites

1. Apply the full schema first (creates enums, tables, triggers, procedures):

   ```bash
   psql -h HOST -U USER -d DATABASE -f sql/schema.sql
   ```

2. Replace the placeholder admin password (see root **`README.md`**) or use **`create_admin.py`**.

## Load catalog seed (empty catalog)

From the repository root:

```bash
psql -h HOST -U USER -d DATABASE -f seed/catalog_seed.sql
```

Runs inside a single transaction (`BEGIN` / `COMMIT`). If any statement fails, nothing is committed.

## Reload catalog on a database that already has this data

You will hit **unique** violations (e.g. dynasty names) unless you clear catalog tables first. Optionally run:

```bash
psql -h HOST -U USER -d DATABASE -f seed/optional_reset_catalog.sql
psql -h HOST -U USER -d DATABASE -f seed/catalog_seed.sql
```

**`optional_reset_catalog.sql`** truncates only catalog + related rows (not **`User_Account`**). It uses **`RESTART IDENTITY CASCADE`** like the app’s restore path.

## Date literals

Ancient Roman and similar rows use PostgreSQL **`BC`** date literals (e.g. `DATE '0031-09-02 BC'`) so **`Reign`** and **`Person`** checks (`end_date >= start_date`, `death_date >= birth_date`) and the **`trg_validate_reign_dates`** trigger stay valid.

## Image paths (`image_url`)

**`catalog_seed.sql`** sets **`image_url`** on **`Dynasty`**, **`Person`**, **`Territory`**, and **`Event`**. Values are absolute web paths like **`/images/persons/augustus_caesar.jpg`**, resolved by Flask from the repo’s **`images/`** directory (see **`app/__init__.py`** — route **`/images/<path>`**).

Place files so paths exist on disk, for example:

| Folder under `images/` | Used for |
|------------------------|----------|
| **`dynasty.jpg`** (file at `images/` root) | Roman Empire dynasty banner |
| **`dyansties/`** | Ottoman, Mongol, Byzantine, Abbasid dynasty images (folder name matches bundled assets) |
| **`persons/`** | Ruler portraits (`augustus_caesar.jpg`, `julius_caesar.jpg`, …) |
| **`events/`** | Event art (`battle_of_actium.jpg`, …) |
| **`territories/`** | Territory images (`anatolia.jpg`, `constantinople.png`, …) |

If a file is missing, the UI may show a broken image until you add the asset or change the path in SQL.

## What is not seeded here

- **`User_Account`** — still from **`sql/schema.sql`** + **`create_admin.py`** / register flow.
- **`Relation`** / **`Event_Relation`** — empty in the reference set; add another SQL file if you extend the demo graph.
