# Dynasty Archives — Complete ERD (Advanced ER Concepts + Hand-Draw Guide)

**Source:** `sql/schema.sql`  
**Purpose:** Hand-drawn–friendly Chen-style narrative + structured catalog.

---

## Notation legend (for hand drawing)

| Symbol / convention | Meaning |
|---------------------|---------|
| `[Strong Entity]` | Single rectangle |
| `⟦Weak Entity⟧` | **Double rectangle** |
| `(Assoc)` | Associative / junction entity (often drawn as rectangle with relationship attributes inside) |
| `<◇ Relationship Name ◇>` | **Diamond** (relationship set) |
| `(attribute)` | Simple attribute oval |
| `((multivalued))` | **Double oval** — multivalued *(none as columns in this schema; see assumptions)* |
| `(- - derived - -)` | **Dashed oval** — derived *(computed view/trigger)* |
| `{Composite}` | Composite attribute *(conceptual grouping of atomic columns)* |
| **━━** double line | **Total participation** (every entity instance must participate) |
| **─** single line | **Partial participation** (optional) |
| `PK`, `FK`, `CK`, `UK` | Primary / Foreign / Composite key / Unique |

---

# 1. ERD code / diagram (flowchart-style text)

Below: clusters you can copy onto paper. Arrows show **FK direction** (child → parent). Draw Chen diamonds **on paper** between rectangles where `<◇ … ◇>` appears.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CLUSTER A — Identity & auth (ISOLATED from historical ER — no FK between clusters A–B)   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

      ┌──────────────────────────────────────────────────────────────┐
      │ User_Account                                                │
      │ ──────────────────────────────────────────────────────────── │
      │ PK  user_id                                                  │
      │ UK  username                                                 │
      │     password                                                 │
      │     role            (enum: admin | viewer)                 │
      │     email                                                  │
      │     is_active                                              │
      │     created_at                                             │
      │ (- - last_login - -)   ← derived/update semantics (login time) │
      └──────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CLUSTER B — Core historical strong entities                                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

      ┌────────────────────────────┐         ┌────────────────────────────┐
      │ Dynasty                    │         │ Territory                  │
      │ ────────────────────────── │         │ ────────────────────────── │
      │ PK  dynasty_id             │         │ PK  territory_id           │
      │ UK  name                   │         │     name                   │
      │ { temporal_span }          │         │     region                 │
      │   ├ start_year (simple)    │         │     modern_name          │
      │   └ end_year   (simple)    │         │     description          │
      │     description            │         │     image_url            │
      │     image_url              │         │     created_at           │
      │     created_at             │         └─────────────┬────────────┘
      │ (- - updated_at - -) trig  │                       │
      └─────────────┬──────────────┘                       │
                    │                                     │
                    │  <◇ BELONGS_TO ◇>    PK dynasty_id (TOTAL Person side)
                    │  <◇ CONTROLS ◇>     PK territory_id (TOTAL Dynasty_Territory both halves)
                    │         │                               │
                    │         │           ┌───────────────────┴────────────────────┐
                    │         │           │ Dynasty_Territory (ASSOCIATIVE / BRIDGE) │
                    │         │           │ CK PK (dynasty_id, territory_id)       │
                    │         │           │     start_year, end_year (rel attrs)    │
                    │         └───────────┼─────────────────────────────────────────┘
                    │                   │
                    ▼                   │
      ┌────────────────────────────┐    │
      │ Person                     │    │
      │ ────────────────────────── │    │
      │ PK  person_id              │    │
      │ FK  dynasty_id ────────────┼────┘──► Dynasty.dynasty_id   [TOTAL: every Person exactly one Dynasty]
      │     full_name              │
      │ { life_dates } optional conceptual composite → stored as: │
      │     birth_date             │
      │     death_date             │
      │     biography              │
      │     image_url              │
      │     created_at             │
      │ (- - updated_at - -) trig  │
      └─────────────┬──────────────┘
                    │
      <◇ HAS_REIGN ◇>  1:M  [TOTAL Reign: each Reign exactly one Person;
                             PARTIAL Person: person may have 0..N reigns]
                    │
                    ▼
      ┌────────────────────────────┐         ┌────────────────────────────┐
      │ Reign                      │         │ Event                      │
      │ ────────────────────────── │         │ ────────────────────────── │
      │ PK  reign_id               │         │ PK  event_id               │
      │ FK  person_id ─────────────┼────────►│     name                   │
      │     title                  │         │     type (enum)            │
      │     capital                │         │ { span } → event_date      │
      │     start_date             │         │           end_date         │
      │     end_date               │         │     location               │
      │     notes                  │         │     description            │
      │     created_at             │         │     outcome                │
      └─────────────┬──────────────┘         │     image_url              │
                    │                        │ FK  dynasty_id ────────────┼──► Dynasty.dynasty_id  [PARTIAL NULL OK]
                    │                        │     created_at             │
                    │                        └────────────────────────────┘
                    │
                    │  <◇ ANCHORS ◇> optional    Succession.reign_id → Reign.reign_id [PARTIAL]
                    │
                    ▼
      (continued in CLUSTER C)


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CLUSTER C — Weak entity + recursive Person + M:N bridges                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

      ┌──────────────────────────────────────────────────────────────────────────┐
      │ ⟦ Succession ⟧  (weak entity pattern — existence tied to Persons)       │
      │ ─────────────────────────────────────────────────────────────────────── │
      │ PK   succession_id          (surrogate — schema choice vs composite key)   │
      │ FK   predecessor_id ───────────────► Person.person_id    [TOTAL]         │
      │ FK   successor_id   ───────────────► Person.person_id    [TOTAL]         │
      │ FK   reign_id       ───────────────► Reign.reign_id      [PARTIAL NULL]    │
      │      type (enum)                                                           │
      │      year                                                                  │
      │      notes                                                                 │
      │      created_at                                                            │
      └──────────────────────────────────────────────────────────────────────────┘
           ▲ Identifying relationships (conceptually): needs Predecessor Person + Successor Person


      ┌────────────────────────────┐
      │ Person ◄───────────────────┼──────┐  RECURSIVE (same entity type, two roles)
      └─────────────┬──────────────┘      │
                    │                     │
      <◇ PARENT_OF ◇>                     │
                    │                     │
                    ▼                     │
      ┌────────────────────────────┐      │
      │ Parent_Child (ASSOCIATIVE  │      │
      │   recursive bridge)        │      │
      │ CK/effective: PK relation_id │      │
      │ FK parent_id ────────────────┼──────┘► Person.person_id  [TOTAL]
      │ FK child_id  ──────────────┼────────► Person.person_id  [TOTAL]
      │     created_at             │
      └────────────────────────────┘


      ┌──────────────┐      <◇ PARTICIPATES ◇>       ┌──────────────┐
      │ Person       │◄────────────────────────────►│ Event        │
      └──────┬───────┘                               └──────┬───────┘
             │                    ┌──────────────────────────┘
             │                    │
             │      ┌─────────────▼──────────────┐
             │      │ Person_Event (BRIDGE)    │
             │      │ CK/PK (person_id, event_id) │
             │      │ FK person_id → Person      │
             │      │ FK event_id  → Event       │
             │      │     role (relationship attr)│
             └──────┴────────────────────────────┘
                        Cardinality: M:N


      ┌──────────────┐      <◇ LINKED ◇>           ┌──────────────┐
      │ Person       │◄──────────────────────────►│ Person       │
      └──────┬───────┘    (two roles A,B)          └──────┬───────┘
             │                    ┌───────────────────────┘
             │      ┌─────────────▼──────────────┐
             │      │ Relation (ASSOCIATIVE)    │
             │      │ PK relation_id             │
             │      │ FK person_a_id → Person    │
             │      │ FK person_b_id → Person    │
             │      │     relation_type          │
             │      │     start_year, end_year   │
             └──────┴────────────────────────────┘
                        Cardinality: M:N (recursive on Person)


      ┌──────────────┐      <◇ RELATED_EVENT ◇>    ┌──────────────┐
      │ Event        │◄────────────────────────────►│ Event        │
      └──────┬───────┘                               └──────┬───────┘
             │                    ┌──────────────────────────┘
             │      ┌─────────────▼──────────────┐
             │      │ Event_Relation (BRIDGE)    │
             │      │ CK/PK (event_id, related_event_id) │
             │      │ FK both → Event.event_id │
             │      │     relation_type          │
             └──────┴────────────────────────────┘
                        Cardinality: M:N (recursive on Event)


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CLUSTER D — Operational / workflow (no FK to historical entities in DDL)               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

      ┌────────────────────────────┐
      │ Audit_Log                  │
      │ PK  log_id                 │
      │     table_name             │
      │     operation              │
      │     record_id              │
      │     performed_by           │
      │ (- - performed_at - -) default now                           │
      │     details                │
      └────────────────────────────┘

      ┌────────────────────────────┐
      │ Edit_Request               │
      │ PK  request_id             │
      │     entity_type + entity_id  (logical pointer — NOT FK in DDL) │
      │     field_name             │
      │     old_value              │
      │     new_value              │
      │     reason                 │
      │     submitted_by           │
      │     submitted_at           │
      │     status                 │
      │     reviewed_by / reviewed_at                               │
      └────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CLUSTER E — Derived virtual entities (VIEWS — not stored tables, hand-draw as dashed)   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

      (- - vw_reign_durations.reign_days - -)  = (COALESCE(end_date,CURRENT_DATE) - start_date)
      (- - vw_succession_chain columns - -)    = joins + labels
      (- - vw_wars_and_battles - -)            = filter + joins
      (- - vw_territory_timeline - -)          = Dynasty_Territory + names
```

---

# 2. Relationship explanations

| # | Relationship (Chen diamond name) | Entities | Type | Bridge / FK columns |
|---|----------------------------------|----------|------|---------------------|
| R1 | **BELONGS_TO** | Dynasty ← Person | **1:M** | `Person.dynasty_id` → `Dynasty.dynasty_id` |
| R2 | **HAS_REIGN** | Person ← Reign | **1:M** | `Reign.person_id` → `Person.person_id` |
| R3 | **IN_CONTEXT_OF** | Dynasty ← Event | **1:M** *(optional)* | `Event.dynasty_id` → `Dynasty.dynasty_id` *(nullable)* |
| R4 | **CONTROLS** | Dynasty ↔ Territory | **M:N** | **`Dynasty_Territory`**: `(dynasty_id, territory_id)` PK + FKs; attrs `start_year`, `end_year` |
| R5 | **PARTICIPATES** | Person ↔ Event | **M:N** | **`Person_Event`**: PK `(person_id, event_id)`; attr `role` |
| R6 | **PARENT_OF** | Person ↔ Person | **M:N recursive** | **`Parent_Child`**: surrogate PK `relation_id`; FKs `parent_id`, `child_id` → `Person` |
| R7 | **SOCIAL_LINK** | Person ↔ Person | **M:N recursive** | **`Relation`**: FKs `person_a_id`, `person_b_id`; attrs type, years |
| R8 | **RELATED_BATTLE / LINK** | Event ↔ Event | **M:N recursive** | **`Event_Relation`**: PK `(event_id, related_event_id)` |
| R9 | **SUCCESSION** | Person, Person, Reign → Succession | **Binary + optional third** | `Succession`: `predecessor_id`, `successor_id` (required); `reign_id` (optional) |

**Weak entity:** **Succession** depends on **Person** (two identifying participant roles). Optional link to **Reign**. Implementation uses surrogate `succession_id` instead of a composite identifier `(predecessor_id, successor_id, year)`.

**No 1:1 mandatory relationships** in the base schema (optional `Event.dynasty_id` keeps Event–Dynasty as M side of 1:M from Dynasty’s viewpoint only).

**Assumptions (inferred):**

1. **Edit_Request** `(entity_type, entity_id)` targets **Person** or **Dynasty** per application rules — **no FK** in DDL (polymorphic reference).
2. **Composite conceptual attributes** `{ temporal_span }` on Dynasty and `{ life_dates }` on Person group atomic integers/dates for modeling clarity; the database stores **simple atomic** columns.
3. **Multivalued attributes** (Chen double oval): **none** as normalized columns; repeating facts would require extra tables (not present).
4. **Derived attributes:** base tables store **trigger-updated** `updated_at`; **views** expose **reign_days** and joined labels — classify as **derived** at read time.

---

# 3. Participation + cardinality summary

Legend for drawing: **E━━◇──R** = Entity side **total**; **E─◇──R** = **partial**.

| Relationship | Side A | Side B | Cardinality | Participation A | Participation B |
|--------------|--------|--------|-------------|-------------------|-------------------|
| Dynasty–Person | Dynasty | Person | **1:M** | Partial (dynasty may have 0 persons) | **Total** (every person has one dynasty) |
| Person–Reign | Person | Reign | **1:M** | Partial (person may have 0 reigns) | **Total** (every reign has one person) |
| Dynasty–Event | Dynasty | Event | **1:M** | Partial | **Partial** (event may lack dynasty) |
| Dynasty–Territory | Dynasty | Territory | **M:N** via bridge | Partial | Partial |
| Person–Event | Person | Event | **M:N** via **Person_Event** | Partial | Partial |
| Person–Person (parent) | Person | Person | **M:N** via **Parent_Child** | Partial | Partial |
| Person–Person (relation) | Person | Person | **M:N** via **Relation** | Partial | Partial |
| Event–Event | Event | Event | **M:N** via **Event_Relation** | Partial | Partial |
| Succession–Person (pred) | Person | Succession | **1:N** | Partial | **Total** (every succession has predecessor) |
| Succession–Person (succ) | Person | Succession | **1:N** | Partial | **Total** (every succession has successor) |
| Succession–Reign | Reign | Succession | **1:N** | Partial | **Partial** (`reign_id` nullable) |

**Composite keys (explicit):**

| Table | Composite key |
|-------|----------------|
| **Person_Event** | `(person_id, event_id)` PK |
| **Event_Relation** | `(event_id, related_event_id)` PK |
| **Dynasty_Territory** | `(dynasty_id, territory_id)` PK |

**Unique simple attributes:** `Dynasty.name`, `User_Account.username`.

---

## Attribute classification quick reference

| Entity | Simple | Composite (conceptual) | Multivalued | Derived / stored-derived |
|--------|--------|------------------------|-------------|---------------------------|
| Dynasty | name, description, image_url, years | `{temporal_span}` | — | `updated_at` (trigger) |
| Person | full_name, biography, image_url, FK | `{life_dates}` → birth/death | — | `updated_at` (trigger) |
| Reign | title, capital, notes, dates | — | — | — |
| Event | name, location, description, … | span as two dates | — | — |
| Territory | name, region, … | — | — | — |
| User_Account | username, password, … | — | — | `last_login` (updated on login) |
| Bridges | FKs + descriptive attrs | — | — | — |
| Views | — | — | — | `reign_days`, joined names (virtual) |

---

*End of document — align hand-drawn Chen diagram with `sql/schema.sql` for column-level accuracy.*
