-- protocol_chunks: the pgvector retrieval store for the MK-6482-005 protocol Q&A bot.
-- Applied by backend/setup_supabase.py using the OWNER connection.
-- Column set mirrors data/extracted/chunks.json, plus the embedding vector.

create extension if not exists vector;

create table if not exists protocol_chunks (
    chunk_id             text primary key,
    section_number       text        not null,
    section_title        text        not null,
    breadcrumb           text        not null,
    page_start           integer     not null,
    page_end             integer     not null,
    text                 text        not null,
    char_count           integer     not null,
    is_partial_redaction boolean     not null default false,
    sub_chunk_index      integer,               -- null unless the section was split
    n_sub_chunks         integer     not null default 1,
    source               text        not null,  -- 'pymupdf' | 'pdfplumber'
    merged_from          text[],                -- section numbers folded into this chunk, else null
    embedding            vector(384)            -- BAAI/bge-small-en-v1.5, cosine
);

-- HNSW index, cosine distance.
-- NOT load-bearing at this scale: with 219 rows pgvector brute-forces a
-- nearest-neighbour scan in well under a millisecond, index or no index. It is
-- here to demonstrate the production pattern; an HNSW index only starts to earn
-- its keep in the tens-of-thousands-of-rows range (and it trades a little recall
-- for a lot of speed there).
create index if not exists protocol_chunks_embedding_hnsw
    on protocol_chunks using hnsw (embedding vector_cosine_ops);
