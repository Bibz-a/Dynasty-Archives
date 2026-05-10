# Database schema diagram (Dynasty Archives)

Source: `sql/schema.sql`

---

## Mermaid ER diagram

```mermaid
erDiagram
    Dynasty {
        serial dynasty_id PK
        varchar name UK "NOT NULL"
        int start_year "NULL"
        int end_year "NULL"
        text description "NULL"
        text image_url "NULL"
        timestamp created_at
        timestamp updated_at
    }

    Person {
        serial person_id PK
        varchar full_name "NOT NULL"
        date birth_date "NULL"
        date death_date "NULL"
        text biography "NULL"
        text image_url "NULL"
        int dynasty_id FK "NOT NULL"
        timestamp created_at
        timestamp updated_at
    }

    Reign {
        serial reign_id PK
        int person_id FK "NOT NULL"
        varchar title "NULL"
        varchar capital "NULL"
        date start_date "NOT NULL"
        date end_date "NULL"
        text notes "NULL"
        timestamp created_at
    }

    Event {
        serial event_id PK
        varchar name "NOT NULL"
        event_type type "NOT NULL"
        date event_date "NULL"
        date end_date "NULL"
        varchar location "NULL"
        text description "NULL"
        varchar outcome "NULL"
        text image_url "NULL"
        int dynasty_id FK "NULL optional"
        timestamp created_at
    }

    Territory {
        serial territory_id PK
        varchar name "NOT NULL"
        varchar region "NULL"
        varchar modern_name "NULL"
        text description "NULL"
        text image_url "NULL"
        timestamp created_at
    }

    User_Account {
        serial user_id PK
        varchar username UK "NOT NULL"
        varchar password "NOT NULL"
        user_role role "NOT NULL"
        varchar email "NULL"
        boolean is_active
        timestamp created_at
        timestamp last_login "NULL"
    }

    Succession {
        serial succession_id PK
        int predecessor_id FK "NOT NULL"
        int successor_id FK "NOT NULL"
        int reign_id FK "NULL optional"
        succession_type type "NOT NULL"
        int year "NULL"
        text notes "NULL"
        timestamp created_at
    }

    Parent_Child {
        serial relation_id PK
        int parent_id FK "NOT NULL"
        int child_id FK "NOT NULL"
        timestamp created_at
    }

    Person_Event {
        int person_id FK "PK NOT NULL"
        int event_id FK "PK NOT NULL"
        varchar role "NULL"
    }

    Relation {
        serial relation_id PK
        int person_a_id FK "NOT NULL"
        int person_b_id FK "NOT NULL"
        varchar relation_type "NOT NULL"
        int start_year "NULL"
        int end_year "NULL"
        text notes "NULL"
        timestamp created_at
    }

    Event_Relation {
        int event_id FK "PK NOT NULL"
        int related_event_id FK "PK NOT NULL"
        varchar relation_type "NOT NULL"
    }

    Dynasty_Territory {
        int dynasty_id FK "PK NOT NULL"
        int territory_id FK "PK NOT NULL"
        int start_year "NULL"
        int end_year "NULL"
    }

    Audit_Log {
        serial log_id PK
        varchar table_name "NOT NULL"
        varchar operation "NOT NULL"
        int record_id "NULL"
        varchar performed_by "NULL"
        timestamp performed_at
        text details "NULL"
    }

    Edit_Request {
        serial request_id PK
        varchar entity_type "NOT NULL"
        int entity_id "NOT NULL"
        varchar field_name "NOT NULL"
        text old_value "NULL"
        text new_value "NOT NULL"
        text reason "NULL"
        varchar submitted_by "NULL"
        timestamp submitted_at
        varchar status
        varchar reviewed_by "NULL"
        timestamp reviewed_at "NULL"
    }

    Dynasty ||--o{ Person : "1:N"
    Dynasty ||--o{ Event : "1:N optional FK"
    Dynasty ||--o{ Dynasty_Territory : "1:N"
    Territory ||--o{ Dynasty_Territory : "1:N"

    Person ||--o{ Reign : "1:N"
    Person ||--o{ Succession : "predecessor N:1"
    Person ||--o{ Succession : "successor N:1"
    Reign ||--o{ Succession : "1:N optional FK"

    Person ||--o{ Parent_Child : "parent N:1"
    Person ||--o{ Parent_Child : "child N:1"

    Person ||--o{ Person_Event : "M:N junction"
    Event ||--o{ Person_Event : "M:N junction"

    Person ||--o{ Relation : "endpoint A N:1"
    Person ||--o{ Relation : "endpoint B N:1"

    Event ||--o{ Event_Relation : "from event M:N"
    Event ||--o{ Event_Relation : "to event M:N"
```

---

## Foreign keys (explicit references)

| From | → To |
|------|------|
| `Person.dynasty_id` | `Dynasty.dynasty_id` |
| `Reign.person_id` | `Person.person_id` |
| `Event.dynasty_id` | `Dynasty.dynasty_id` *(nullable)* |
| `Succession.predecessor_id` | `Person.person_id` |
| `Succession.successor_id` | `Person.person_id` |
| `Succession.reign_id` | `Reign.reign_id` *(nullable)* |
| `Parent_Child.parent_id` | `Person.person_id` |
| `Parent_Child.child_id` | `Person.person_id` |
| `Person_Event.person_id` | `Person.person_id` |
| `Person_Event.event_id` | `Event.event_id` |
| `Relation.person_a_id` | `Person.person_id` |
| `Relation.person_b_id` | `Person.person_id` |
| `Event_Relation.event_id` | `Event.event_id` |
| `Event_Relation.related_event_id` | `Event.event_id` |
| `Dynasty_Territory.dynasty_id` | `Dynasty.dynasty_id` |
| `Dynasty_Territory.territory_id` | `Territory.territory_id` |

---

## Relationship summary

| Relationship | Cardinality | Bridge / notes |
|--------------|-------------|----------------|
| Dynasty — Person | **1:N** | `Person.dynasty_id` required |
| Dynasty — Event | **1:N** | optional: `Event.dynasty_id` |
| Person — Reign | **1:N** | |
| Person — Event | **M:N** | **`Person_Event`** (`person_id`, `event_id`) |
| Dynasty — Territory | **M:N** | **`Dynasty_Territory`** (`dynasty_id`, `territory_id`) |
| Person — Person (parent/child) | **M:N** | **`Parent_Child`** |
| Person — Person (typed link) | **M:N** | **`Relation`** |
| Event — Event | **M:N** | **`Event_Relation`** |
| Person — Succession (predecessor) | **1:N** | `Succession.predecessor_id` |
| Person — Succession (successor) | **1:N** | `Succession.successor_id` |
| Reign — Succession | **1:N** | optional `Succession.reign_id` |

**Isolated (no FK):** `User_Account`, `Audit_Log`, `Edit_Request` *(logical refs only via `entity_type` + `entity_id`)*.

---

## Hand-drawn conversion hint

Draw **14 boxes**: the entities above. Use arrows labeled with the FK column name. Mark **PK** under column lists and circle **FK** columns. Junction tables get a diamond or bridge notation between the two parents.
