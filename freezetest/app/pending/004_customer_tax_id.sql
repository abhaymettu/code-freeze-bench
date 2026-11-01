-- Tax ids on invoices (needed by the invoice PDF job). Merged Friday.
alter table customers add column tax_id text;

update customers set tax_id = '' where tax_id is null;

insert into schema_migrations (version) values ('004_customer_tax_id');
