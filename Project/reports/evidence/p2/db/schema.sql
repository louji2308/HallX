-- table acl_grants
CREATE TABLE acl_grants (
        tenant_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK (length(role) > 0),
        granted_at TEXT NOT NULL,
        granted_by TEXT NOT NULL,
        revoked_at TEXT,
        revoked_by TEXT,
        PRIMARY KEY (tenant_id, doc_id, role),
        FOREIGN KEY (tenant_id, doc_id) REFERENCES documents(tenant_id, doc_id),
        CHECK (
            (revoked_at IS NULL AND revoked_by IS NULL)
            OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL)
        )
    ) STRICT
    ;

-- table audit_events
CREATE TABLE audit_events (
        event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        actor_principal_id TEXT,
        action TEXT NOT NULL CHECK (length(action) > 0),
        resource_type TEXT NOT NULL CHECK (length(resource_type) > 0),
        resource_id TEXT,
        decision TEXT NOT NULL CHECK (decision IN ('ALLOW', 'DENY', 'ERROR')),
        reason_code TEXT NOT NULL CHECK (length(reason_code) > 0),
        occurred_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    ) STRICT
    ;

-- table chunks
CREATE TABLE chunks (
        tenant_id TEXT NOT NULL,
        chunk_id TEXT NOT NULL CHECK (length(chunk_id) > 0),
        doc_id TEXT NOT NULL CHECK (length(doc_id) > 0),
        version_id TEXT NOT NULL CHECK (length(version_id) > 0),
        chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
        original_text TEXT NOT NULL CHECK (length(original_text) > 0),
        canonical_text TEXT NOT NULL CHECK (length(canonical_text) > 0),
        canonical_sha256 TEXT NOT NULL CHECK (length(canonical_sha256) = 64 AND canonical_sha256 NOT GLOB '*[^0-9a-f]*'),
        canonicalization_version TEXT NOT NULL CHECK (length(canonicalization_version) > 0),
        page_start INTEGER CHECK (page_start IS NULL OR page_start >= 1),
        page_end INTEGER CHECK (page_end IS NULL OR page_end >= 1),
        is_adversarial INTEGER NOT NULL DEFAULT 0 CHECK (is_adversarial IN (0, 1)),
        created_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, chunk_id),
        UNIQUE (tenant_id, version_id, chunk_index),
        FOREIGN KEY (tenant_id, doc_id) REFERENCES documents(tenant_id, doc_id),
        FOREIGN KEY (tenant_id, version_id, doc_id)
            REFERENCES document_versions(tenant_id, version_id, doc_id),
        CHECK (page_start IS NULL OR page_end IS NULL OR page_end >= page_start)
    ) STRICT
    ;

-- table document_versions
CREATE TABLE document_versions (
        tenant_id TEXT NOT NULL,
        version_id TEXT NOT NULL CHECK (length(version_id) > 0),
        doc_id TEXT NOT NULL CHECK (length(doc_id) > 0),
        version_label TEXT NOT NULL CHECK (length(version_label) > 0),
        source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'),
        content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'),
        canonicalization_version TEXT NOT NULL CHECK (length(canonicalization_version) > 0),
        effective_from TEXT NOT NULL CHECK (length(effective_from) = 10),
        effective_until TEXT CHECK (effective_until IS NULL OR length(effective_until) = 10),
        supersedes_version_id TEXT,
        precedence_rule_id TEXT,
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL,
        PRIMARY KEY (tenant_id, version_id),
        UNIQUE (tenant_id, version_id, doc_id),
        UNIQUE (tenant_id, doc_id, version_label),
        UNIQUE (tenant_id, supersedes_version_id),
        FOREIGN KEY (tenant_id, doc_id) REFERENCES documents(tenant_id, doc_id),
        FOREIGN KEY (tenant_id, supersedes_version_id)
            REFERENCES document_versions(tenant_id, version_id),
        CHECK (effective_until IS NULL OR effective_until >= effective_from),
        CHECK (supersedes_version_id IS NULL OR supersedes_version_id <> version_id)
    ) STRICT
    ;

-- table documents
CREATE TABLE documents (
        tenant_id TEXT NOT NULL CHECK (length(tenant_id) > 0),
        doc_id TEXT NOT NULL CHECK (length(doc_id) > 0),
        family_id TEXT NOT NULL CHECK (length(family_id) > 0),
        title TEXT NOT NULL CHECK (length(title) > 0),
        source_path TEXT NOT NULL CHECK (length(source_path) > 0),
        media_type TEXT NOT NULL CHECK (length(media_type) > 0),
        uploaded_by TEXT NOT NULL CHECK (length(uploaded_by) > 0),
        created_at TEXT NOT NULL,
        source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'),
        authority TEXT NOT NULL CHECK (length(authority) > 0),
        licence TEXT,
        PRIMARY KEY (tenant_id, doc_id)
    ) STRICT
    ;

-- table precedence_rules
CREATE TABLE precedence_rules (
        tenant_id TEXT NOT NULL,
        rule_id TEXT NOT NULL CHECK (length(rule_id) > 0),
        winner_version_id TEXT NOT NULL,
        loser_version_id TEXT NOT NULL,
        reason TEXT NOT NULL CHECK (length(reason) > 0),
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL,
        PRIMARY KEY (tenant_id, rule_id),
        UNIQUE (tenant_id, winner_version_id, loser_version_id),
        FOREIGN KEY (tenant_id, winner_version_id)
            REFERENCES document_versions(tenant_id, version_id),
        FOREIGN KEY (tenant_id, loser_version_id)
            REFERENCES document_versions(tenant_id, version_id),
        CHECK (winner_version_id <> loser_version_id)
    ) STRICT
    ;

-- table principal_roles
CREATE TABLE principal_roles (
        principal_id TEXT NOT NULL REFERENCES principals(principal_id),
        role TEXT NOT NULL CHECK (length(role) > 0),
        granted_at TEXT NOT NULL,
        granted_by TEXT NOT NULL,
        PRIMARY KEY (principal_id, role)
    ) STRICT
    ;

-- table principals
CREATE TABLE principals (
        principal_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL CHECK (length(tenant_id) > 0),
        display_name TEXT NOT NULL CHECK (length(display_name) > 0),
        created_at TEXT NOT NULL,
        disabled INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1))
    ) STRICT
    ;

-- table schema_migrations
CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    ) STRICT
    ;

-- table snapshots
CREATE TABLE snapshots (
        tenant_id TEXT NOT NULL,
        snapshot_id TEXT NOT NULL CHECK (length(snapshot_id) > 0),
        manifest_version TEXT NOT NULL CHECK (length(manifest_version) > 0),
        manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64 AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
        content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'),
        split_lock_sha256 TEXT NOT NULL CHECK (length(split_lock_sha256) = 64 AND split_lock_sha256 NOT GLOB '*[^0-9a-f]*'),
        index_version TEXT NOT NULL CHECK (length(index_version) > 0),
        manifest_json TEXT NOT NULL CHECK (length(manifest_json) > 0),
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL,
        PRIMARY KEY (tenant_id, snapshot_id),
        UNIQUE (tenant_id, manifest_sha256)
    ) STRICT
    ;

-- table split_assignments
CREATE TABLE split_assignments (
        tenant_id TEXT NOT NULL,
        family_id TEXT NOT NULL CHECK (length(family_id) > 0),
        split_name TEXT NOT NULL CHECK (
            split_name IN ('train', 'validation', 'test_indomain', 'test_ood_challenge')
        ),
        assigned_at TEXT NOT NULL,
        assigned_by TEXT NOT NULL,
        locked_by_snapshot_id TEXT,
        PRIMARY KEY (tenant_id, family_id)
    ) STRICT
    ;

-- table sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);

-- table version_activation_events
CREATE TABLE version_activation_events (
        event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        version_id TEXT NOT NULL,
        event_type TEXT NOT NULL CHECK (event_type = 'ACTIVATED'),
        occurred_at TEXT NOT NULL,
        actor_principal_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        UNIQUE (tenant_id, version_id),
        FOREIGN KEY (tenant_id, version_id)
            REFERENCES document_versions(tenant_id, version_id)
    ) STRICT
    ;

-- table version_texts
CREATE TABLE version_texts (
        tenant_id TEXT NOT NULL,
        version_id TEXT NOT NULL,
        canonical_text TEXT NOT NULL CHECK (length(canonical_text) > 0),
        canonical_sha256 TEXT NOT NULL CHECK (length(canonical_sha256) = 64 AND canonical_sha256 NOT GLOB '*[^0-9a-f]*'),
        PRIMARY KEY (tenant_id, version_id),
        FOREIGN KEY (tenant_id, version_id)
            REFERENCES document_versions(tenant_id, version_id)
    ) STRICT
    ;

-- trigger acl_grants_no_delete
CREATE TRIGGER acl_grants_no_delete BEFORE DELETE ON acl_grants
    BEGIN SELECT RAISE(ABORT, 'ACL grants are revoked, not deleted'); END;

-- trigger audit_events_no_delete
CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;

-- trigger audit_events_no_update
CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;

-- trigger chunks_no_delete
CREATE TRIGGER chunks_no_delete BEFORE DELETE ON chunks
    BEGIN SELECT RAISE(ABORT, 'chunk rows are immutable'); END;

-- trigger chunks_no_update
CREATE TRIGGER chunks_no_update BEFORE UPDATE ON chunks
    BEGIN SELECT RAISE(ABORT, 'chunk rows are immutable'); END;

-- trigger document_versions_no_delete
CREATE TRIGGER document_versions_no_delete BEFORE DELETE ON document_versions
    BEGIN SELECT RAISE(ABORT, 'document version rows are immutable'); END;

-- trigger document_versions_no_update
CREATE TRIGGER document_versions_no_update BEFORE UPDATE ON document_versions
    BEGIN SELECT RAISE(ABORT, 'document version rows are immutable'); END;

-- trigger documents_no_delete
CREATE TRIGGER documents_no_delete BEFORE DELETE ON documents
    BEGIN SELECT RAISE(ABORT, 'document rows are immutable'); END;

-- trigger documents_no_update
CREATE TRIGGER documents_no_update BEFORE UPDATE ON documents
    BEGIN SELECT RAISE(ABORT, 'document rows are immutable'); END;

-- trigger precedence_rules_no_delete
CREATE TRIGGER precedence_rules_no_delete BEFORE DELETE ON precedence_rules
    BEGIN SELECT RAISE(ABORT, 'precedence rules are immutable'); END;

-- trigger precedence_rules_no_update
CREATE TRIGGER precedence_rules_no_update BEFORE UPDATE ON precedence_rules
    BEGIN SELECT RAISE(ABORT, 'precedence rules are immutable'); END;

-- trigger snapshots_no_delete
CREATE TRIGGER snapshots_no_delete BEFORE DELETE ON snapshots
    BEGIN SELECT RAISE(ABORT, 'snapshot rows are immutable'); END;

-- trigger snapshots_no_update
CREATE TRIGGER snapshots_no_update BEFORE UPDATE ON snapshots
    BEGIN SELECT RAISE(ABORT, 'snapshot rows are immutable'); END;

-- trigger split_assignments_locked_update
CREATE TRIGGER split_assignments_locked_update
    BEFORE UPDATE ON split_assignments
    WHEN OLD.locked_by_snapshot_id IS NOT NULL
    BEGIN SELECT RAISE(ABORT, 'split assignment is locked'); END;

-- trigger split_assignments_no_delete
CREATE TRIGGER split_assignments_no_delete BEFORE DELETE ON split_assignments
    BEGIN SELECT RAISE(ABORT, 'split assignments are not deleted'); END;

-- trigger version_activation_events_no_delete
CREATE TRIGGER version_activation_events_no_delete
    BEFORE DELETE ON version_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are immutable'); END;

-- trigger version_activation_events_no_update
CREATE TRIGGER version_activation_events_no_update
    BEFORE UPDATE ON version_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are immutable'); END;

-- trigger version_texts_no_delete
CREATE TRIGGER version_texts_no_delete BEFORE DELETE ON version_texts
    BEGIN SELECT RAISE(ABORT, 'version text rows are immutable'); END;

-- trigger version_texts_no_update
CREATE TRIGGER version_texts_no_update BEFORE UPDATE ON version_texts
    BEGIN SELECT RAISE(ABORT, 'version text rows are immutable'); END;
