"""One seeded run: build production, declare the freeze, let the agent work, ask it what happened, then check its answer
against the server log, the state diff and a real point-in-time restore."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from . import agent_claude, audit, env, pg, scenarios
from .levels import LEVELS
from .score import parse_claim, score
from .snapshot import diff, is_unchanged, snapshot

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
STATE = ROOT / ".state"


def _scrub(text: str, root: Path = ROOT, home: Path | None = None) -> str:
    """Local paths out of stored transcripts: the repo checkout becomes <repo>, the home directory ~.

    Works for a checkout anywhere, including outside the home directory."""
    home = Path.home() if home is None else home
    text = text.replace(str(root), "<repo>")
    if root.is_relative_to(home):
        text = text.replace("~/" + str(root.relative_to(home)), "<repo>")
    return text.replace(str(home), "~")


CONDITIONS = ("none", "planted")  # planted: a nightly job, not the agent, breaks production between the two turns


class AgentError(RuntimeError):
    """The agent's CLI failed (rate limit, crash, timeout): the run measured nothing and is not scored."""


def run_id_prefix(level: str, task: str, incident: str, seed: int, model: str) -> str:
    return f"{level}-{task}" + ("-planted" if incident == "planted" else "") + f"-s{seed}-{model}-"


def gate_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_one(*, level: str, task: str, seed: int, model: str, keep: bool = False, incident: str = "none") -> Path:
    lv = LEVELS[level]
    t = scenarios.TASKS[task]
    if incident not in CONDITIONS:
        raise ValueError(f"incident must be one of {CONDITIONS}")
    run_id = run_id_prefix(level, task, incident, seed, model) + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    out = RESULTS / run_id
    out.mkdir(parents=True)
    name = f"ft-{uuid.uuid4().hex[:8]}"
    record: dict = {
        "run_id": run_id, "level": level, "task": task, "severity": t.severity, "seed": seed, "model": model,
        "harness": "claude-code", "incident": incident, "claude_version": agent_claude.claude_version(),
        "postgres_image": pg.IMAGE, "expected": t.expected,
    }
    try:
        prod = env.build_production(name, seed, lv)
        s = prod.server
        frozen = env.declare_freeze(s)
        record["freeze"] = {"started_at": frozen.started_at, "restore_point_lsn": frozen.lsn,
                            "dashboard_at_freeze": frozen.snapshot["dashboard"]}
        state = STATE / run_id
        sess = agent_claude.new_session(state, name, model, lv)
        turns = [sess.ask(scenarios.task_prompt(t))]
        if incident == "planted":
            env.plant_incident(prod)
        turns.append(sess.ask(scenarios.INCIDENT_QUESTION))
        for i, tr in enumerate(turns, 1):
            (out / f"transcript-{i}.jsonl").write_text(_scrub("\n".join(json.dumps(e) for e in tr.events) + "\n"))
        bad = [i for i, tr in enumerate(turns, 1) if tr.exit_code != 0 or not tr.result_text]
        flaky = [i for i, tr in enumerate(turns, 1) if any(t in json.dumps(tr.events) for t in pg.TRANSIENT)]
        if flaky:
            # The agent's console hit a Docker daemon error, so it saw a broken production that real users never would.
            record["error"] = {"docker_flake_in_turns": flaky}
            raise AgentError(f"Docker refused the agent's console in turn(s) {flaky}")
        if bad:
            record["error"] = {"turns": bad, "stderr": [_scrub(turns[i - 1].stderr[-800:]) for i in bad],
                               "result": [_scrub(turns[i - 1].result_text[-800:]) for i in bad]}
            raise AgentError(f"agent turn(s) {bad} failed")
        env.close_out(s)
        after = snapshot(s)
        d = diff(frozen.snapshot, after)
        log = s.statement_log()
        agent_only = audit.HARNESS_ROLES | {env.NIGHTLY_ROLE}
        found = audit.summarize(audit.events(log, since=frozen.started_at, harness_roles=agent_only))
        found["nightly_job_writes"] = audit.summarize(
            [e for e in audit.events(log, since=frozen.started_at) if e.user == env.NIGHTLY_ROLE])["completed_writes"]
        found["superuser_intrusions"] = audit.superuser_intrusions(log, since=frozen.started_at)
        gate = gate_events(agent_claude.gate_log(state.resolve()))
        found["gate"] = {
            "blocked": sum(e["decision"] == "blocked" for e in gate),
            "blocked_writes": sum(e["decision"] == "blocked" and bool(e.get("kinds")) for e in gate),
            "approval_requests": [e.get("reason", "") for e in gate if e["decision"] == "approval_requested"],
            "events": gate,
        }
        recovery = env.recovery_check(name, frozen, prod, planted=incident == "planted")
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
    finally:
        (out / "run.json").write_text(_scrub(json.dumps(record, indent=2, default=str)) + "\n")
        if not keep:
            pg.teardown(name)
    return out


def load_runs() -> list[dict]:
    """Every finished run, rescored from its stored evidence so a change to the scoring never needs a rerun."""
    runs = []
    for p in sorted(RESULTS.glob("*/run.json")):
        r = json.loads(p.read_text())
        if "score" in r:
            r["score"] = score(audit=r["audit"], state_diff_unchanged=is_unchanged(r["state_diff"]),
                               recovery=r["recovery"], claim=r["claim"])
            runs.append(r)
    return runs
