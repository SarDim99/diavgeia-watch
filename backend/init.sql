-- ============================================================
-- Diavgeia-Watch: Database Schema
-- PostgreSQL 16 + pgvector
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- for fuzzy text search

-- -----------------------------------------------------------
-- Core table: one row per expenditure decision
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS decisions (
    id              BIGSERIAL PRIMARY KEY,
    ada             TEXT UNIQUE NOT NULL,          -- unique Diavgeia ID (e.g. "Ψ4Ε2ΟΡΗ8-ΦΒ7")
    subject         TEXT,                          -- decision subject / description
    decision_type   TEXT NOT NULL DEFAULT 'Β.2.1', -- decision type code
    status          TEXT,                          -- PUBLISHED, etc.
    issue_date      DATE,
    submission_ts   TIMESTAMPTZ,
    publish_ts      TIMESTAMPTZ,

    -- Organization (who spends)
    org_id          TEXT,                          -- Diavgeia organization UID
    org_name        TEXT,
    org_afm         TEXT,                          -- organization tax ID

    -- URL to the original document
    document_url    TEXT,

    -- Raw JSON from the API (for future re-parsing)
    raw_json        JSONB,

    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Expense lines: one decision can have multiple contractors
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS expense_items (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     BIGINT REFERENCES decisions(id) ON DELETE CASCADE,
    ada             TEXT NOT NULL,

    -- Contractor (who receives money)
    contractor_afm  TEXT,                          -- tax ID of contractor
    contractor_name TEXT,

    -- Financial
    amount          NUMERIC(15, 2),
    currency        TEXT DEFAULT 'EUR',

    -- Classification
    cpv_code        TEXT,                          -- Common Procurement Vocabulary
    kae_code        TEXT,                          -- Greek budget code (ΚΑΕ/ΑΛΕ)

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Organizations cache (so we don't re-fetch names)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    uid             TEXT PRIMARY KEY,              -- Diavgeia org UID
    label           TEXT,
    abbreviation    TEXT,
    parent_uid      TEXT,
    category        TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Embeddings for semantic search (Phase 2 prep)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_embeddings (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     BIGINT REFERENCES decisions(id) ON DELETE CASCADE,
    ada             TEXT NOT NULL,
    text_chunk      TEXT,                          -- the text that was embedded
    embedding       vector(384),                   -- dimension matches all-MiniLM-L6-v2
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Harvesting state: track what we've already fetched
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest_log (
    id              BIGSERIAL PRIMARY KEY,
    harvest_date    DATE NOT NULL,                 -- which day we harvested
    decision_type   TEXT NOT NULL,
    decisions_found INTEGER DEFAULT 0,
    decisions_saved INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT DEFAULT 'RUNNING'         -- RUNNING, COMPLETED, FAILED
);

-- -----------------------------------------------------------
-- Indexes for fast queries
-- -----------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_decisions_ada        ON decisions(ada);
CREATE INDEX IF NOT EXISTS idx_decisions_org_id     ON decisions(org_id);
CREATE INDEX IF NOT EXISTS idx_decisions_issue_date ON decisions(issue_date);
CREATE INDEX IF NOT EXISTS idx_decisions_type       ON decisions(decision_type);

CREATE INDEX IF NOT EXISTS idx_expense_ada          ON expense_items(ada);
CREATE INDEX IF NOT EXISTS idx_expense_contractor   ON expense_items(contractor_afm);
CREATE INDEX IF NOT EXISTS idx_expense_cpv          ON expense_items(cpv_code);
CREATE INDEX IF NOT EXISTS idx_expense_amount       ON expense_items(amount);
CREATE INDEX IF NOT EXISTS idx_expense_decision_id  ON expense_items(decision_id);

-- Trigram index for fuzzy search on subject text
CREATE INDEX IF NOT EXISTS idx_decisions_subject_trgm
    ON decisions USING gin (subject gin_trgm_ops);

-- Vector index for semantic search (will be populated in Phase 2)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
    ON decision_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- -----------------------------------------------------------
-- Helper views
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_spending_summary AS
SELECT
    d.org_id,
    d.org_name,
    EXTRACT(YEAR FROM d.issue_date)  AS year,
    EXTRACT(MONTH FROM d.issue_date) AS month,
    e.cpv_code,
    e.contractor_afm,
    e.contractor_name,
    COUNT(DISTINCT d.ada)            AS num_decisions,
    SUM(e.amount)                    AS total_amount
FROM decisions d
JOIN expense_items e ON e.decision_id = d.id
GROUP BY d.org_id, d.org_name,
         EXTRACT(YEAR FROM d.issue_date),
         EXTRACT(MONTH FROM d.issue_date),
         e.cpv_code, e.contractor_afm, e.contractor_name;


-- View for anomaly detection: contracts just under thresholds
CREATE OR REPLACE VIEW v_near_threshold_contracts AS
SELECT
    e.contractor_afm,
    e.contractor_name,
    d.org_id,
    d.org_name,
    COUNT(*)        AS contract_count,
    AVG(e.amount)   AS avg_amount,
    MIN(e.amount)   AS min_amount,
    MAX(e.amount)   AS max_amount
FROM expense_items e
JOIN decisions d ON d.id = e.decision_id
WHERE e.amount BETWEEN 20000 AND 30000  -- just under €30k open tender limit
GROUP BY e.contractor_afm, e.contractor_name, d.org_id, d.org_name
HAVING COUNT(*) >= 3
ORDER BY contract_count DESC;