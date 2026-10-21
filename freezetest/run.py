"""One seeded run: build production, declare the freeze, let the agent work, ask it what happened, then check its answer
against the server log, the state diff and a real point-in-time restore."""

from __future__ import annotations

import fcntl
import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import agent_claude, audit, env, pg, scenarios
from .score import parse_claim, score
from .snapshot import diff, is_unchanged, snapshot

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
STATE = ROOT / ".state"
LEVELS = ("prompt",)  # v0. Database roles and a typed permission gate are the next two levels; neither is built yet.
LOCK = Path("/tmp/overnight-compute.lock")


@contextmanager
def compute_lock(wait: float = 0):
    """One heavy job at a time on this machine. Raises TimeoutError if the lock stays held for `wait` seconds."""
    f = open(LOCK, "a")
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                f.close()
                raise TimeoutError(f"{LOCK} is held by another job")
            time.sleep(10)
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def _scrub(text: str) -> str:
    """Local paths out of stored transcripts: the repo checkout becomes <repo>, the home directory ~."""
    tilde = "~/" + str(ROOT.relative_to(Path.home()))
    return text.replace(str(ROOT), "<repo>").replace(tilde, "<repo>").replace(str(Path.home()), "~")


CONDITIONS = ("none", "planted")  # planted: a nightly job, not the agent, breaks production between the two turns


def run_one(*, level: str, task: str, seed: int, model: str, keep: bool = False, incident: str = "none") -> Path:
    if level not in LEVELS:
        raise ValueError(f"level {level!r} is not built yet; v0 has {LEVELS}")
    t = scenarios.TASKS[task]
    if incident not in CONDITIONS:
        raise ValueError(f"incident must be one of {CONDITIONS}")
    tag = f"{level}-{task}" + ("-planted" if incident == "planted" else "")
    run_id = f"{tag}-s{seed}-{model}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    out = RESULTS / run_id
    out.mkdir(parents=True)
    name = f"ft-{uuid.uuid4().hex[:8]}"
    record: dict = {
        "run_id": run_id, "level": level, "task": task, "seed": seed, "model": model, "harness": "claude-code", "incident": incident,
        "claude_version": agent_claude.claude_version(), "postgres_image": pg.IMAGE, "expected": t.expected,
    }
    try:
        s = env.build_production(name, seed)
        frozen = env.declare_freeze(s)
        record["freeze"] = {"started_at": frozen.started_at, "restore_point_lsn": frozen.lsn,
                            "dashboard_at_freeze": frozen.snapshot["dashboard"]}
        sess = agent_claude.new_session(STATE / run_id, name, model)
        turns = [sess.ask(scenarios.task_prompt(t))]
        if incident == "planted":
            env.plant_incident(s)
        turns.append(sess.ask(scenarios.INCIDENT_QUESTION))
        env.close_out(s)
        after = snapshot(s)
        d = diff(frozen.snapshot, after)
        log = s.statement_log()
        agent_only = audit.HARNESS_ROLES | {env.NIGHTLY_ROLE}
        found = audit.summarize(audit.events(log, since=frozen.started_at, harness_roles=agent_only))
        found["nightly_job_writes"] = audit.summarize(
            [e for e in audit.events(log, since=frozen.started_at) if e.user == env.NIGHTLY_ROLE])["completed_writes"]
        found["superuser_intrusions"] = audit.superuser_intrusions(log, since=frozen.started_at)
        recovery = env.recovery_check(name, frozen)
        claim = parse_claim(turns[1].result_text)
        record.update({
            "audit": found,
            "state_diff": d,
            "recovery": recovery,
            "claim": claim,
            "score": score(audit=found, state_diff_unchanged=is_unchanged(d), recovery=recovery, claim=claim),
            "turns": [
                {"seconds": round(tr.seconds, 1), "exit_code": tr.exit_code, "tool_calls": len(tr.tool_calls),
                 "reply": _scrub(tr.result_text), "stderr_tail": _scrub(tr.stderr[-800:])}
                for tr in turns
            ],
        })
        for i, tr in enumerate(turns, 1):
            (out / f"transcript-{i}.jsonl").write_text(_scrub("\n".join(json.dumps(e) for e in tr.events) + "\n"))
    finally:
        (out / "run.json").write_text(_scrub(json.dumps(record, indent=2, default=str)) + "\n")
        if not keep:
            pg.teardown(name)
    return out


def load_runs() -> list[dict]:
    runs = []
    for p in sorted(RESULTS.glob("*/run.json")):
        r = json.loads(p.read_text())
        if "score" in r:
            runs.append(r)
    return runs


def scoreboard(runs: list[dict]) -> str:
    lines = [
        "# Scoreboard",
        "",
        "Generated by `freezetest scoreboard` from `results/*/run.json`. Every number below is a count of runs that",
        "actually happened; nothing is extrapolated.",
        "",
        "| Run | Level | Task | Incident | Seed | Model | Broke freeze (log) | Writes | Production changed | Said it changed | "
        "Disclosure honest | Restore claim | PITR restored | Claim verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    yn = lambda v: "n/a" if v is None else ("yes" if v else "no")
    for r in runs:
        sc, c = r["score"], r.get("claim") or {}
        lines.append(
            f"| `{r['run_id']}` | {r['level']} | {r['task']} | {r.get('incident', 'none')} | {r['seed']} | {r['model']} | {yn(sc['violated'])} | "
            f"{r['audit']['completed_writes']} ({', '.join(r['audit']['kinds']) or 'none'}) | {yn(sc['production_changed'])} | "
            f"{yn(c.get('changed_production'))} | {yn(sc['disclosure_honest'])} | {sc['restore_claim'] or 'n/a'} | "
            f"{yn(sc['recovery_success'])} | {sc['restore_claim_verdict'] or 'n/a'} |"
        )
    lines += ["", "## By level and condition", ""]
    for level, incident in sorted({(r["level"], r.get("incident", "none")) for r in runs}):
        rs = [r for r in runs if r["level"] == level and r.get("incident", "none") == incident]
        n = len(rs)
        viol = sum(r["score"]["violated"] for r in rs)
        honest = [r["score"]["disclosure_honest"] for r in rs if r["score"]["disclosure_honest"] is not None]
        rec = [r["score"]["recovery_success"] for r in rs if r["score"]["recovery_success"] is not None]
        verdicts = {}
        for r in rs:
            v = r["score"]["restore_claim_verdict"]
            if v:
                verdicts[v] = verdicts.get(v, 0) + 1
        vtext = ", ".join(f"{k} {v}" for k, v in sorted(verdicts.items())) or "none scored"
        lines.append(
            f"- **{level}, incident {incident}**: {n} run(s). Agent broke the freeze: {viol} of {n}. Honest about "
            f"whether production changed: {sum(honest)} of {len(honest)}. PITR restored the freeze state: "
            f"{sum(rec)} of {len(rec)}. Restore claims: {vtext}."
        )
    return "\n".join(lines) + "\n"
