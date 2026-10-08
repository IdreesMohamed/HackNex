create table if not exists public.usage_events (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, source_language text not null, target_language text not null, duration_seconds integer not null default 0, created_at timestamptz not null default now());
alter table public.usage_events enable row level security;
create policy usage_events_select_own on public.usage_events for select to authenticated using ((select auth.uid()) = user_id);
create policy usage_events_insert_own on public.usage_events for insert to authenticated with check ((select auth.uid()) = user_id);
create index usage_events_user_pair_idx on public.usage_events(user_id, source_language, target_language);
