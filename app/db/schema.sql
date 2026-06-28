-- Схема RAG-хранилища Agent Forge: документы с эмбеддингами для hybrid search.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          bigserial PRIMARY KEY,
    source      text NOT NULL,
    content     text NOT NULL,
    -- tsvector для лексического поиска (ts_rank), генерируется из content
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED,
    -- вектор GigaChat Embeddings (размерность из settings.embedding_dim)
    embedding   vector(1024)
);

-- GIN-индекс для лексического поиска по tsvector
CREATE INDEX IF NOT EXISTS documents_content_tsv_idx
    ON documents USING gin (content_tsv);

-- HNSW-индекс для векторного поиска по косинусной близости.
-- HNSW (в отличие от IVFFlat) не требует предварительного наполнения таблицы для
-- корректной кластеризации и эффективен на малых коллекциях (десятки-сотни чанков
-- доки проекта), не требует настройки ivfflat.probes.
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
