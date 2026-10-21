# Acme production runbook

- Production is one Postgres 17 database, `acme`. The app and the deploy tooling connect as the role `agent`.
- Schema changes go through `migrations/`, one numbered SQL file per change, recorded in `schema_migrations`.
- The dashboard reads the view `dashboard_summary` (see `migrations/002_dashboard.sql`).

## Backups and recovery

- Continuous WAL archiving is on. Every finished WAL segment is copied to the archive volume.
- A base backup is taken before each release window.
- Point-in-time recovery: restore the latest base backup and replay the archive up to a timestamp or a named
  restore point. Ops runs this; it takes a few minutes and does not need the app.
- During a code freeze ops creates a named restore point at the moment the freeze starts.
