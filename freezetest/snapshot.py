"""A fingerprint of the app's state: every table's row count and content hash, and the schema itself."""

from __future__ import annotations

import json

from .pg import Server

SNAPSHOT_SQL = r"""
with t as (
  select c.relname as name
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r'
)
select json_build_object(
  'tables', (select coalesce(json_object_agg(name, name), '{}') from t),
  'schema', (
    select md5(coalesce(string_agg(x, E'\n' order by x), ''))
    from (
      select format('col %s.%s %s %s', table_name, column_name, data_type, is_nullable) as x
        from information_schema.columns where table_schema = 'public'
      union all
      select format('view %s %s', viewname, definition) from pg_views where schemaname = 'public'
      union all
      select format('index %s %s', indexname, indexdef) from pg_indexes where schemaname = 'public'
      union all
      select format('con %s %s', conname, pg_get_constraintdef(oid))
        from pg_constraint where connamespace = 'public'::regnamespace
      union all
      select format('trigger %s', tgname) from pg_trigger t join pg_class c on c.oid = t.tgrelid
        join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and not t.tgisinternal
    ) s
  ),
  'dashboard', (select row_to_json(d) from dashboard_summary d)
)::text
"""


def snapshot(s: Server) -> dict:
    """{'schema': md5, 'tables': {name: {'rows': n, 'md5': hash}}, 'dashboard': {...} or None}."""
    try:
        base = json.loads(s.scalar(SNAPSHOT_SQL))
    except Exception:
        # The dashboard view itself may be gone; fingerprint without it.
        base = json.loads(s.scalar(SNAPSHOT_SQL.replace("(select row_to_json(d) from dashboard_summary d)", "null")))
    tables = {}
    for name in sorted(base["tables"]):
        row = s.scalar(
            f'select count(*) || \',\' || coalesce(md5(string_agg(t::text, E\'\\n\' order by t::text)), \'\') from public."{name}" t'
        )
        n, h = row.split(",", 1)
        tables[name] = {"rows": int(n), "md5": h}
    return {"schema": base["schema"], "tables": tables, "dashboard": base["dashboard"]}


def diff(before: dict, after: dict) -> dict:
    """What changed between two snapshots. Empty lists and False mean nothing changed."""
    b, a = before["tables"], after["tables"]
    changed = sorted(t for t in set(b) & set(a) if b[t] != a[t])
    return {
        "schema_changed": before["schema"] != after["schema"],
        "tables_dropped": sorted(set(b) - set(a)),
        "tables_added": sorted(set(a) - set(b)),
        "tables_changed": changed,
        "row_deltas": {t: a[t]["rows"] - b[t]["rows"] for t in changed},
        "dashboard_before": before["dashboard"],
        "dashboard_after": after["dashboard"],
    }


def is_unchanged(d: dict) -> bool:
    return not (d["schema_changed"] or d["tables_dropped"] or d["tables_added"] or d["tables_changed"])
