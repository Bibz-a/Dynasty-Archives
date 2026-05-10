-- ============================================================
--  DYNASTY ARCHIVES SYSTEM — Full PostgreSQL Schema
-- ============================================================

DROP TABLE IF EXISTS Dynasty_Territory CASCADE;
DROP TABLE IF EXISTS Person_Event    CASCADE;
DROP TABLE IF EXISTS Relation        CASCADE;
DROP TABLE IF EXISTS Parent_Child    CASCADE;
DROP TABLE IF EXISTS Succession      CASCADE;
DROP TABLE IF EXISTS Audit_Log       CASCADE;
DROP TABLE IF EXISTS Event           CASCADE;
DROP TABLE IF EXISTS Territory       CASCADE;
DROP TABLE IF EXISTS Reign           CASCADE;
DROP TABLE IF EXISTS Person          CASCADE;
DROP TABLE IF EXISTS Dynasty         CASCADE;
DROP TABLE IF EXISTS User_Account    CASCADE;

-- Drop custom types if they exist
DROP TYPE IF EXISTS succession_type CASCADE;
DROP TYPE IF EXISTS user_role        CASCADE;
DROP TYPE IF EXISTS event_type       CASCADE;


-- ============================================================
--  CUSTOM TYPES (ENUMS)
-- ============================================================

CREATE TYPE user_role       AS ENUM ('admin', 'viewer');
CREATE TYPE succession_type AS ENUM ('normal', 'disputed', 'conquest', 'abdication');
CREATE TYPE event_type      AS ENUM ('war', 'battle', 'treaty', 'coronation', 'death',
                                     'birth', 'political', 'natural_disaster', 'other');


-- ============================================================
--  STRONG ENTITIES
-- ============================================================

-- 1. Dynasty
CREATE TABLE Dynasty (
    dynasty_id   SERIAL       PRIMARY KEY,
    name         VARCHAR(150) NOT NULL UNIQUE,
    start_year   INT,
    end_year     INT,
    description  TEXT,
    image_url    TEXT,                          -- Local image path
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW(),

    CONSTRAINT chk_dynasty_years CHECK (
        end_year IS NULL OR end_year >= start_year
    )
);

-- 2. Person (Ruler / Historical Figure)
CREATE TABLE Person (
    person_id    SERIAL       PRIMARY KEY,
    full_name    VARCHAR(200) NOT NULL,
    birth_date   DATE,
    death_date   DATE,
    biography    TEXT,
    image_url    TEXT,                          -- Local image path
    dynasty_id   INT          NOT NULL REFERENCES Dynasty(dynasty_id) ON DELETE RESTRICT,
    created_at   TIMESTAMP    DEFAULT NOW(),
    updated_at   TIMESTAMP    DEFAULT NOW(),

    CONSTRAINT chk_person_dates CHECK (
        death_date IS NULL OR death_date >= birth_date
    )
);

-- 3. Reign
CREATE TABLE Reign (
    reign_id     SERIAL       PRIMARY KEY,
    person_id    INT          NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    title        VARCHAR(150),                  -- e.g. 'King', 'Emperor', 'Caliph'
    capital      VARCHAR(150),
    start_date   DATE         NOT NULL,
    end_date     DATE,                          -- NULL = still reigning
    notes        TEXT,
    created_at   TIMESTAMP    DEFAULT NOW(),

    CONSTRAINT chk_reign_dates CHECK (
        end_date IS NULL OR end_date >= start_date
    )
);

-- 4. Event
CREATE TABLE Event (
    event_id     SERIAL       PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    type         event_type   NOT NULL,
    event_date   DATE,
    end_date     DATE,                          -- for multi-day events like wars
    location     VARCHAR(200),
    description  TEXT,
    outcome      VARCHAR(50),                   -- victory / defeat / draw / unknown
    image_url    TEXT,                          -- Local image path
    dynasty_id   INT          REFERENCES Dynasty(dynasty_id) ON DELETE SET NULL,
    created_at   TIMESTAMP    DEFAULT NOW(),

    CONSTRAINT chk_event_dates CHECK (
        end_date IS NULL OR end_date >= event_date
    )
);

-- 5. Territory
CREATE TABLE Territory (
    territory_id SERIAL       PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    region       VARCHAR(200),
    modern_name  VARCHAR(200),
    description  TEXT,
    image_url    TEXT,                          -- local path e.g. /images/territories/anatolia.jpg
    created_at   TIMESTAMP    DEFAULT NOW()
);

-- 6. User_Account
CREATE TABLE User_Account (
    user_id      SERIAL       PRIMARY KEY,
    username     VARCHAR(100) NOT NULL UNIQUE,
    password     VARCHAR(255) NOT NULL,         -- store hashed (bcrypt)
    role         user_role    NOT NULL DEFAULT 'viewer',
    email        VARCHAR(200),
    is_active    BOOLEAN      DEFAULT TRUE,
    created_at   TIMESTAMP    DEFAULT NOW(),
    last_login   TIMESTAMP
);


-- ============================================================
--  WEAK ENTITY
-- ============================================================

-- Succession (weak — depends on Person and Reign)
CREATE TABLE Succession (
    succession_id   SERIAL          PRIMARY KEY,
    predecessor_id  INT             NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    successor_id    INT             NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    reign_id        INT             REFERENCES Reign(reign_id) ON DELETE SET NULL,
    type            succession_type NOT NULL DEFAULT 'normal',
    year            INT,
    notes           TEXT,
    created_at      TIMESTAMP       DEFAULT NOW(),

    CONSTRAINT chk_succession_different CHECK (
        predecessor_id <> successor_id
    )
);


-- ============================================================
--  ASSOCIATIVE ENTITIES (M:N + SELF-REFERENTIAL)
-- ============================================================

-- Parent_Child (self-referential on Person)
CREATE TABLE Parent_Child (
    relation_id  SERIAL PRIMARY KEY,
    parent_id    INT    NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    child_id     INT    NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    created_at   TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_parent_child  UNIQUE (parent_id, child_id),
    CONSTRAINT chk_no_self_rel  CHECK  (parent_id <> child_id)
);

-- Person_Event (M:N between Person and Event)
CREATE TABLE Person_Event (
    person_id    INT          NOT NULL REFERENCES Person(person_id)  ON DELETE CASCADE,
    event_id     INT          NOT NULL REFERENCES Event(event_id)    ON DELETE CASCADE,
    role         VARCHAR(100),                  -- e.g. 'commander', 'victim', 'witness'
    PRIMARY KEY (person_id, event_id)
);

CREATE TABLE Relation (
    relation_id   SERIAL PRIMARY KEY,
    person_a_id   INT NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    person_b_id   INT NOT NULL REFERENCES Person(person_id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,  -- 'spouse', 'ally', 'rival', 'vassal'
    start_year    INT,
    end_year      INT,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT NOW(),
    CONSTRAINT chk_relation_diff CHECK (person_a_id <> person_b_id)
);

CREATE TABLE Event_Relation (
    event_id          INT NOT NULL REFERENCES Event(event_id) ON DELETE CASCADE,
    related_event_id  INT NOT NULL REFERENCES Event(event_id) ON DELETE CASCADE,
    relation_type     VARCHAR(50) NOT NULL DEFAULT 'related_battle',
    PRIMARY KEY (event_id, related_event_id),
    CONSTRAINT chk_event_relation_diff CHECK (event_id <> related_event_id)
);

-- Dynasty_Territory (M:N between Dynasty and Territory)
CREATE TABLE Dynasty_Territory (
    dynasty_id   INT  NOT NULL REFERENCES Dynasty(dynasty_id)   ON DELETE CASCADE,
    territory_id INT  NOT NULL REFERENCES Territory(territory_id) ON DELETE CASCADE,
    start_year   INT,
    end_year     INT,
    PRIMARY KEY (dynasty_id, territory_id),

    CONSTRAINT chk_dt_years CHECK (
        end_year IS NULL OR end_year >= start_year
    )
);

-- Audit_Log (for trigger logging)
CREATE TABLE Audit_Log (
    log_id       SERIAL       PRIMARY KEY,
    table_name   VARCHAR(100) NOT NULL,
    operation    VARCHAR(10)  NOT NULL,         -- INSERT / UPDATE / DELETE
    record_id    INT,
    performed_by VARCHAR(100),
    performed_at TIMESTAMP    DEFAULT NOW(),
    details      TEXT
);

CREATE TABLE Edit_Request (
    request_id   SERIAL PRIMARY KEY,
    entity_type  VARCHAR(50) NOT NULL,  -- 'person' or 'dynasty'
    entity_id    INT NOT NULL,
    field_name   VARCHAR(100) NOT NULL,
    old_value    TEXT,
    new_value    TEXT NOT NULL,
    reason       TEXT,
    submitted_by VARCHAR(100),
    submitted_at TIMESTAMP DEFAULT NOW(),
    status       VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'declined'
    reviewed_by  VARCHAR(100),
    reviewed_at  TIMESTAMP
);


-- ============================================================
--  INDEXES (for common lookups)
-- ============================================================

CREATE INDEX idx_person_dynasty   ON Person(dynasty_id);
CREATE INDEX idx_reign_person     ON Reign(person_id);
CREATE INDEX idx_succession_pred  ON Succession(predecessor_id);
CREATE INDEX idx_succession_succ  ON Succession(successor_id);
CREATE INDEX idx_event_type       ON Event(type);
CREATE INDEX idx_event_date       ON Event(event_date);
CREATE INDEX idx_person_event     ON Person_Event(event_id);
CREATE INDEX idx_dynasty_terr     ON Dynasty_Territory(territory_id);


-- ============================================================
--  TRIGGERS
-- ============================================================

-- 1. Auto-update updated_at on Dynasty
CREATE OR REPLACE FUNCTION trg_update_dynasty_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dynasty_updated
BEFORE UPDATE ON Dynasty
FOR EACH ROW EXECUTE FUNCTION trg_update_dynasty_timestamp();

-- 2. Auto-update updated_at on Person
CREATE OR REPLACE FUNCTION trg_update_person_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_person_updated
BEFORE UPDATE ON Person
FOR EACH ROW EXECUTE FUNCTION trg_update_person_timestamp();

-- 3. Log all deletions from Person into Audit_Log
CREATE OR REPLACE FUNCTION trg_log_person_deletion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO Audit_Log (table_name, operation, record_id, details)
    VALUES ('Person', 'DELETE', OLD.person_id,
            'Deleted person: ' || OLD.full_name);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_person_deleted
AFTER DELETE ON Person
FOR EACH ROW EXECUTE FUNCTION trg_log_person_deletion();

-- 4. Log all deletions from Dynasty into Audit_Log
CREATE OR REPLACE FUNCTION trg_log_dynasty_deletion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO Audit_Log (table_name, operation, record_id, details)
    VALUES ('Dynasty', 'DELETE', OLD.dynasty_id,
            'Deleted dynasty: ' || OLD.name);
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_dynasty_deleted
AFTER DELETE ON Dynasty
FOR EACH ROW EXECUTE FUNCTION trg_log_dynasty_deletion();

-- 5. Validate reign dates don't exceed person's death date
CREATE OR REPLACE FUNCTION trg_validate_reign_dates()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_death_date DATE;
BEGIN
    SELECT death_date INTO v_death_date
    FROM Person WHERE person_id = NEW.person_id;

    IF v_death_date IS NOT NULL AND NEW.start_date > v_death_date THEN
        RAISE EXCEPTION 'Reign start date (%) cannot be after person death date (%)',
            NEW.start_date, v_death_date;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_reign_dates_check
BEFORE INSERT OR UPDATE ON Reign
FOR EACH ROW EXECUTE FUNCTION trg_validate_reign_dates();


-- ============================================================
--  STORED PROCEDURES
-- ============================================================

-- 1. Add a new ruler with their first reign in one call
CREATE OR REPLACE PROCEDURE sp_add_ruler(
    p_full_name   VARCHAR,
    p_birth_date  DATE,
    p_death_date  DATE,
    p_biography   TEXT,
    p_dynasty_id  INT,
    p_title       VARCHAR,
    p_capital     VARCHAR,
    p_reign_start DATE,
    p_reign_end   DATE
)
LANGUAGE plpgsql AS $$
DECLARE
    v_person_id INT;
BEGIN
    -- Insert person
    INSERT INTO Person (full_name, birth_date, death_date, biography, dynasty_id)
    VALUES (p_full_name, p_birth_date, p_death_date, p_biography, p_dynasty_id)
    RETURNING person_id INTO v_person_id;

    -- Insert reign
    INSERT INTO Reign (person_id, title, capital, start_date, end_date)
    VALUES (v_person_id, p_title, p_capital, p_reign_start, p_reign_end);

    RAISE NOTICE 'Ruler % added with person_id = %', p_full_name, v_person_id;
END;
$$;

-- 2. Record a succession between two rulers
CREATE OR REPLACE PROCEDURE sp_record_succession(
    p_predecessor_id INT,
    p_successor_id   INT,
    p_reign_id       INT,
    p_type           succession_type,
    p_year           INT,
    p_notes          TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        -- Close predecessor's reign if still open
        UPDATE Reign
        SET end_date = MAKE_DATE(p_year, 1, 1)
        WHERE person_id = p_predecessor_id AND end_date IS NULL;

        -- Insert succession record
        INSERT INTO Succession (predecessor_id, successor_id, reign_id, type, year, notes)
        VALUES (p_predecessor_id, p_successor_id, p_reign_id, p_type, p_year, p_notes);
    EXCEPTION
        WHEN OTHERS THEN
            RAISE;
    END;

    RAISE NOTICE 'Succession recorded: % → %', p_predecessor_id, p_successor_id;
END;
$$;

-- 3. Get all rulers in a dynasty using a CURSOR
CREATE OR REPLACE PROCEDURE sp_list_dynasty_rulers(p_dynasty_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    cur_rulers CURSOR FOR
        SELECT p.full_name, r.title, r.start_date, r.end_date
        FROM   Person p
        JOIN   Reign  r ON r.person_id = p.person_id
        WHERE  p.dynasty_id = p_dynasty_id
        ORDER  BY r.start_date;

    v_name   VARCHAR;
    v_title  VARCHAR;
    v_start  DATE;
    v_end    DATE;
BEGIN
    OPEN cur_rulers;
    LOOP
        FETCH cur_rulers INTO v_name, v_title, v_start, v_end;
        EXIT WHEN NOT FOUND;
        RAISE NOTICE '% (%) : % → %', v_name, v_title, v_start, COALESCE(v_end::TEXT, 'present');
    END LOOP;
    CLOSE cur_rulers;
END;
$$;


-- ============================================================
--  VIEWS (for common queries)
-- ============================================================

-- Longest reigning rulers
CREATE OR REPLACE VIEW vw_reign_durations AS
SELECT
    p.person_id,
    p.full_name,
    d.name                                              AS dynasty,
    r.title,
    r.start_date,
    COALESCE(r.end_date, CURRENT_DATE)                 AS end_date,
    (COALESCE(r.end_date, CURRENT_DATE) - r.start_date) AS reign_days
FROM Person p
JOIN Reign   r ON r.person_id   = p.person_id
JOIN Dynasty d ON d.dynasty_id  = p.dynasty_id
ORDER BY reign_days DESC;

-- Succession chains
CREATE OR REPLACE VIEW vw_succession_chain AS
SELECT
    s.succession_id,
    pred.full_name  AS predecessor,
    succ.full_name  AS successor,
    s.type,
    s.year,
    d.name          AS dynasty
FROM Succession s
JOIN Person pred ON pred.person_id = s.predecessor_id
JOIN Person succ ON succ.person_id = s.successor_id
JOIN Dynasty d   ON d.dynasty_id   = pred.dynasty_id
ORDER BY s.year;

-- Wars and battles with participants
CREATE OR REPLACE VIEW vw_wars_and_battles AS
SELECT
    e.event_id,
    e.name          AS event_name,
    e.type,
    e.event_date,
    e.end_date,
    e.location,
    p.full_name     AS participant,
    pe.role
FROM Event e
JOIN Person_Event pe ON pe.event_id  = e.event_id
JOIN Person       p  ON p.person_id  = pe.person_id
WHERE e.type IN ('war', 'battle')
ORDER BY e.event_date;

-- Territory control timeline
CREATE OR REPLACE VIEW vw_territory_timeline AS
SELECT
    d.name          AS dynasty,
    t.name          AS territory,
    t.region,
    dt.start_year,
    dt.end_year
FROM Dynasty_Territory dt
JOIN Dynasty   d ON d.dynasty_id   = dt.dynasty_id
JOIN Territory t ON t.territory_id = dt.territory_id
ORDER BY dt.start_year;


-- ============================================================
--  SEED: Default admin user  (password must be hashed in app)
-- ============================================================
INSERT INTO User_Account (username, password, role, email)
VALUES ('admin', 'CHANGE_ME_TO_BCRYPT_HASH', 'admin', 'admin@dynastyarchives.com');
