"""The append-only trigger definitions, shared by the migration, the test
harness and the maintenance command so there is exactly one copy of the SQL."""
from __future__ import annotations

# The function guards several tables, so it names the one that actually fired
# rather than assuming audit_events — a deletion blocked on electronic_signatures
# previously reported the wrong table, which sent an investigation the wrong way.
FORBID_FUNCTION = """
CREATE OR REPLACE FUNCTION dx_audit_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        '% is append-only: % is not permitted on this table', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'raise_exception',
              HINT = 'This record is immutable by regulation (21 CFR Part 11 §11.10(e)).';
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGERS = """
DROP TRIGGER IF EXISTS dx_audit_no_update ON audit_events;
DROP TRIGGER IF EXISTS dx_audit_no_delete ON audit_events;
DROP TRIGGER IF EXISTS dx_audit_no_truncate ON audit_events;

CREATE TRIGGER dx_audit_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION dx_audit_forbid_mutation();

CREATE TRIGGER dx_audit_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION dx_audit_forbid_mutation();

CREATE TRIGGER dx_audit_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION dx_audit_forbid_mutation();
"""

DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS dx_audit_no_update ON audit_events;
DROP TRIGGER IF EXISTS dx_audit_no_delete ON audit_events;
DROP TRIGGER IF EXISTS dx_audit_no_truncate ON audit_events;
"""

CREATE_SIGNATURE_TRIGGERS = """
DROP TRIGGER IF EXISTS dx_signature_no_delete ON electronic_signatures;

CREATE TRIGGER dx_signature_no_delete
    BEFORE DELETE ON electronic_signatures
    FOR EACH ROW EXECUTE FUNCTION dx_audit_forbid_mutation();
"""

DROP_SIGNATURE_TRIGGERS = """
DROP TRIGGER IF EXISTS dx_signature_no_delete ON electronic_signatures;
"""

DROP_FUNCTION = "DROP FUNCTION IF EXISTS dx_audit_forbid_mutation();"
