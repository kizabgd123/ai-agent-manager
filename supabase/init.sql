-- Enable pgvector extension
create extension if not exists vector;

-- Journal entries table for RAG content + embeddings
create table if not exists public.journal_entries (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  source text not null,
  content text not null,
  embedding vector(1536)
);

-- Enable Row Level Security
alter table public.journal_entries enable row level security;

-- Basic RLS policy: authenticated users can read/write
create policy if not exists "journal_entries_select_authenticated"
  on public.journal_entries
  for select
  to authenticated
  using (true);

create policy if not exists "journal_entries_insert_authenticated"
  on public.journal_entries
  for insert
  to authenticated
  with check (true);

create policy if not exists "journal_entries_update_authenticated"
  on public.journal_entries
  for update
  to authenticated
  using (true)
  with check (true);

-- Similarity search function using cosine distance
create or replace function public.match_journal_entries(
  query_embedding vector(1536),
  match_count int default 5
)
returns table (
  id bigint,
  source text,
  content text,
  similarity float
)
language sql
stable
as $$
  select
    je.id,
    je.source,
    je.content,
    1 - (je.embedding <=> query_embedding) as similarity
  from public.journal_entries je
  where je.embedding is not null
  order by je.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;
