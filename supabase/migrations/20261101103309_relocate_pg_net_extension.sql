-- pg_net is non-relocatable. Supabase recommends dropping and recreating it
-- in the non-exposed extensions schema. The queue was checked empty before this
-- live migration; refuse to drop it if pending HTTP requests exist.
do $$
declare
  pending_count bigint;
begin
  if exists (
    select 1
    from pg_extension
    where extname = 'pg_net'
      and extnamespace = 'public'::regnamespace
  ) then
    execute 'select count(*) from net.http_request_queue' into pending_count;
    if pending_count > 0 then
      raise exception 'pg_net relocation stopped: pending HTTP requests exist in net.http_request_queue';
    end if;

    create schema if not exists extensions;
    drop extension pg_net;
    create extension pg_net with schema extensions;
  end if;
end
$$;
