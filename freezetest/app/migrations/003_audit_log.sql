-- Who did what in the app, for support tickets.
create table audit_log (
    id     bigserial primary key,
    at     timestamptz not null,
    actor  text not null,
    action text not null,
    detail jsonb not null default '{}'
);

create index audit_log_at on audit_log (at);

insert into schema_migrations (version) values ('003_audit_log');
