-- Optional: wipe catalog tables only (keeps User_Account and schema).
-- Run before catalog_seed.sql if you need a clean re-import.
-- Usage: psql ... -f seed/optional_reset_catalog.sql

BEGIN;

TRUNCATE TABLE
    edit_request,
    audit_log,
    event_relation,
    relation,
    succession,
    parent_child,
    person_event,
    dynasty_territory,
    event,
    reign,
    person,
    territory,
    dynasty
RESTART IDENTITY CASCADE;

COMMIT;
