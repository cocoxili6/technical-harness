create extension if not exists pgcrypto;

create table if not exists public.threads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, id)
);
create index if not exists threads_user_updated_idx
    on public.threads(user_id, updated_at desc);

create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    thread_id uuid not null,
    role text not null check (role in ('user', 'assistant', 'system', 'tool')),
    content text not null,
    profile jsonb not null default '{}'::jsonb,
    sources jsonb not null default '[]'::jsonb,
    trace jsonb not null default '[]'::jsonb,
    sequence bigint not null,
    created_at timestamptz not null default now(),
    unique (user_id, thread_id, sequence),
    foreign key (user_id, thread_id) references public.threads(user_id, id) on delete cascade
);
create index if not exists messages_thread_sequence_idx
    on public.messages(user_id, thread_id, sequence);

create table if not exists public.memories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    text text not null,
    kind text not null check (kind in ('interest', 'background', 'goal', 'preference', 'progress', 'fact')),
    importance smallint not null check (importance between 1 and 5),
    stability double precision not null default 9,
    created_at timestamptz not null default now(),
    last_recalled_at timestamptz not null default now(),
    recall_count integer not null default 0,
    source text not null default 'auto',
    thread_id uuid,
    forgotten_at timestamptz,
    foreign key (user_id, thread_id) references public.threads(user_id, id) on delete set null (thread_id)
);
create index if not exists memories_user_kind_idx on public.memories(user_id, kind);

create table if not exists public.paper_catalog (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    thread_id uuid,
    canonical_url text not null,
    title text not null default '',
    authors jsonb not null default '[]'::jsonb,
    year integer,
    venue text,
    citation_count integer,
    summary text not null default '',
    source text not null default '',
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    unique (user_id, canonical_url),
    foreign key (user_id, thread_id) references public.threads(user_id, id) on delete set null (thread_id)
);
create index if not exists paper_catalog_user_seen_idx
    on public.paper_catalog(user_id, last_seen_at desc);

create table if not exists public.tool_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    thread_id uuid not null,
    tool_name text not null,
    input_summary text not null default '',
    result_summary text not null default '',
    status text not null default 'done',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (user_id, thread_id) references public.threads(user_id, id) on delete cascade
);
create index if not exists tool_runs_thread_created_idx
    on public.tool_runs(user_id, thread_id, created_at);

create table if not exists public.context_summaries (
    user_id uuid not null references auth.users(id) on delete cascade,
    thread_id uuid not null,
    summary text not null default '',
    paper_catalog jsonb not null default '[]'::jsonb,
    summarized_through bigint not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, thread_id),
    foreign key (user_id, thread_id) references public.threads(user_id, id) on delete cascade
);

do $$
declare table_name text;
begin
  foreach table_name in array array[
    'threads', 'messages', 'memories', 'paper_catalog', 'tool_runs', 'context_summaries'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('drop policy if exists user_isolation on public.%I', table_name);
    execute format(
      'create policy user_isolation on public.%I using (user_id = auth.uid()) with check (user_id = auth.uid())',
      table_name
    );
  end loop;
end $$;

grant select, insert, update, delete on
    public.threads,
    public.messages,
    public.memories,
    public.paper_catalog,
    public.tool_runs,
    public.context_summaries
to authenticated;
