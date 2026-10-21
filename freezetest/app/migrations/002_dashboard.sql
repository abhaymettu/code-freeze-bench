-- The numbers on the founder's dashboard.
create view dashboard_summary as
select
    (select count(*) from customers)                          as customers,
    (select coalesce(sum(mrr_cents), 0) from subscriptions) / 100.0 as mrr_dollars,
    (select count(*) from invoices where status = 'open')     as open_invoices;

insert into schema_migrations (version) values ('002_dashboard');
