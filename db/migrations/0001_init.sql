CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE media (
    id UUID PRIMARY KEY,
    source_platform TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('video', 'image', 'audio')),
    caption TEXT,
    transcript TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    media_id UUID REFERENCES media(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    payload JSONB NOT NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    media_id UUID NOT NULL REFERENCES media(id),
    chunk_text TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX embeddings_embedding_hnsw_cosine_idx
    ON embeddings USING hnsw (embedding vector_cosine_ops);
