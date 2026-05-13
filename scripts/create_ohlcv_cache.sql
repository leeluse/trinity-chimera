create table if not exists public.ohlcv_cache (
    symbol text not null,
    timeframe text not null,
    timestamp_ms bigint not null,
    open double precision not null,
    high double precision not null,
    low double precision not null,
    close double precision not null,
    volume double precision not null default 0,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint ohlcv_cache_pkey primary key (symbol, timeframe, timestamp_ms)
);

create index if not exists ohlcv_cache_symbol_timeframe_ts_idx
    on public.ohlcv_cache (symbol, timeframe, timestamp_ms desc);

create or replace function public.set_ohlcv_cache_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists trg_ohlcv_cache_updated_at on public.ohlcv_cache;

create trigger trg_ohlcv_cache_updated_at
before update on public.ohlcv_cache
for each row
execute function public.set_ohlcv_cache_updated_at();

alter table public.ohlcv_cache enable row level security;

drop policy if exists "service_role_all_ohlcv_cache" on public.ohlcv_cache;

create policy "service_role_all_ohlcv_cache"
on public.ohlcv_cache
for all
to service_role
using (true)
with check (true);
