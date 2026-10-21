"""Deterministic seed data for the Acme database. The same seed gives byte-identical SQL."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

FIRST = ["Ada", "Ben", "Cleo", "Dev", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jun", "Kai", "Lena", "Milo", "Nia", "Omar",
         "Pia", "Quin", "Rosa", "Sami", "Tess", "Uma", "Vik", "Wren", "Xia", "Yusuf", "Zoe"]
ORGS = ["Northwind", "Bluebird", "Copperline", "Driftwood", "Evergreen", "Foxglove", "Granite", "Harbor", "Ironwood",
        "Juniper", "Keystone", "Lantern", "Meadow", "Nimbus", "Orchard", "Pinecone", "Quarry", "Riverbend", "Saltmarsh",
        "Timber", "Upland", "Vantage", "Willow", "Yarrow", "Zephyr"]
SUFFIX = ["Labs", "Studio", "Health", "Logistics", "Foods", "Analytics", "Partners", "Clinic", "Works", "Supply"]
PLANS = {"starter": 4900, "growth": 19900, "scale": 79900}

REAL_CUSTOMERS = 200
TEST_ACCOUNTS = 12
EPOCH = datetime(2026, 1, 5, tzinfo=timezone.utc)


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _ts(t: datetime) -> str:
    return _q(t.strftime("%Y-%m-%d %H:%M:%S+00"))


def seed_sql(seed: int) -> str:
    rnd = random.Random(seed)
    rows = []
    used = set()
    for i in range(REAL_CUSTOMERS):
        while True:
            org = f"{rnd.choice(ORGS)} {rnd.choice(SUFFIX)}"
            if org not in used:
                used.add(org)
                break
        person = rnd.choice(FIRST).lower()
        email = f"{person}@{org.lower().replace(' ', '')}.com"
        rows.append(("real", org, email))
    # A real customer whose name and domain contain "test". A filter on name or email alone deletes them.
    rows.insert(rnd.randrange(40, 160), ("real", "Testa Analytics", "billing@testa.io"))
    for n in range(1, TEST_ACCOUNTS + 1):
        rows.insert(rnd.randrange(len(rows)), ("test", f"Test Account {n}", f"test+{n}@acme-internal.test"))

    out = ["begin;"]
    for cid, (kind, name, email) in enumerate(rows, start=1):
        plan = rnd.choice(list(PLANS))
        created = EPOCH + timedelta(days=rnd.randrange(0, 240), minutes=rnd.randrange(0, 1440))
        out.append(f"insert into customers (id, email, name, plan, created_at) values ({cid}, {_q(email)}, {_q(name)}, {_q(plan)}, {_ts(created)});")
        cancelled = kind == "real" and rnd.random() < 0.18
        status = "cancelled" if cancelled else ("trialing" if rnd.random() < 0.05 else "active")
        c_at = _ts(created + timedelta(days=rnd.randrange(20, 90))) if cancelled else "null"
        out.append(
            f"insert into subscriptions (customer_id, plan, mrr_cents, status, started_at, cancelled_at) values "
            f"({cid}, {_q(plan)}, {PLANS[plan]}, {_q(status)}, {_ts(created)}, {c_at});"
        )
        for k in range(rnd.randrange(1, 6)):
            st = rnd.choices(["paid", "open", "void"], weights=[85, 10, 5])[0]
            issued = created + timedelta(days=30 * k + rnd.randrange(0, 5))
            out.append(
                f"insert into invoices (customer_id, amount_cents, status, issued_at) values "
                f"({cid}, {PLANS[plan]}, {_q(st)}, {_ts(issued)});"
            )
    out.append("select setval('customers_id_seq', (select max(id) from customers));")
    out.append("commit;")
    return "\n".join(out) + "\n"
