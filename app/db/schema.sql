-- Схема RAG-хранилища Agent Forge: документы с эмбеддингами для hybrid search.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          bigserial PRIMARY KEY,
    source      text NOT NULL,
    content     text NOT NULL,
    -- tsvector для лексического поиска (ts_rank), генерируется из content
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('russian', content)) STORED,
    -- вектор GigaChat Embeddings (размерность settings.embedding_dim = 2560).
    -- Тип halfvec (а не vector): реальная размерность 2560 > 2000 — лимита HNSW для
    -- типа vector. halfvec (float16) поддерживает HNSW до 4000 измерений, занимает
    -- вдвое меньше места при незначительной потере точности.
    embedding   halfvec(2560)
);

-- GIN-индекс для лексического поиска по tsvector
CREATE INDEX IF NOT EXISTS documents_content_tsv_idx
    ON documents USING gin (content_tsv);

-- HNSW-индекс для векторного поиска по косинусной близости (halfvec_cosine_ops).
-- HNSW (в отличие от IVFFlat) не требует предварительного наполнения таблицы для
-- корректной кластеризации и эффективен на малых коллекциях (десятки-сотни чанков
-- доки проекта), не требует настройки ivfflat.probes.
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64);
