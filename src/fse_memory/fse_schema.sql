CREATE TABLE IF NOT EXISTS student_profiles (
    user_id TEXT PRIMARY KEY,
    major TEXT,
    catalog_year INTEGER,
    minor TEXT,
    additional_program_asked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE student_profiles
    ADD COLUMN IF NOT EXISTS additional_program_asked BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS citations (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    collection TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citations_session ON citations(session_id, message_index);
