-- Core tables for the Acme billing app.
create table schema_migrations (
    version    text primary key,
    applied_at timestamptz not null default now()
);

create table customers (
    id         serial primary key,
    email      text not null unique,
    name       text not null,
    plan       text not null check (plan in ('starter', 'growth', 'scale')),
    created_at timestamptz not null
);

create table subscriptions (
    id           serial primary key,
    customer_id  integer not null references customers (id),
    plan         text not null,
    mrr_cents    integer not null check (mrr_cents >= 0),
    status       text not null check (status in ('active', 'trialing', 'cancelled')),
    started_at   timestamptz not null,
    cancelled_at timestamptz
);

create table invoices (
    id           serial primary key,
    customer_id  integer not null references customers (id),
    amount_cents integer not null,
    status       text not null check (status in ('paid', 'open', 'void')),
    issued_at    timestamptz not null
);

insert into schema_migrations (version) values ('001_init');
