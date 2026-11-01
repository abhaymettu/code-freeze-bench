from __future__ import annotations

import argparse
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import report, run, scenarios
from .levels import LEVELS


def _seeds(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def _list(text: str) -> list[str]:
    return [x for x in text.split(",") if x]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="freezetest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="one seeded run of the Claude Code harness, then print its scorecard")
    r.add_argument("--level", choices=list(LEVELS), default="prompt")
    r.add_argument("--task", choices=list(scenarios.TASKS), required=True)
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--model", default="sonnet")
    r.add_argument("--incident", choices=run.CONDITIONS, default="none",
                   help="planted: a nightly job, not the agent, runs a destructive cleanup between the two turns")
    r.add_argument("--keep", action="store_true", help="leave the containers up afterwards")
    r.add_argument("--json", action="store_true", help="print the score as JSON instead of the scorecard")
    m = sub.add_parser("matrix", help="every combination of the given cells, skipping cells already scored")
    m.add_argument("--levels", type=_list, default=list(LEVELS))
    m.add_argument("--tasks", type=_list, default=list(scenarios.TASKS))
    m.add_argument("--models", type=_list, default=["haiku", "sonnet", "opus"])
    m.add_argument("--seeds", type=_seeds, default=_seeds("1-3"), help="a seed or a range like 1-5")
    m.add_argument("--incidents", type=_list, default=["none"])
    m.add_argument("--jobs", type=int, default=4, help="runs in parallel; each is one container pair and one CLI")
    sub.add_parser("scoreboard", help="rewrite results/SCOREBOARD.md and the paper's tables from results/*/run.json")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        out = run.run_one(level=a.level, task=a.task, seed=a.seed, model=a.model, keep=a.keep, incident=a.incident)
        rec = json.loads((out / "run.json").read_text())
        print(json.dumps({"run": str(out), "score": rec.get("score")}, indent=2) if a.json else report.card(rec))
    elif a.cmd == "matrix":
        done = {run.run_id_prefix(r["level"], r["task"], r.get("incident", "none"), r["seed"], r["model"])
                for r in run.load_runs()}
        cells = [c for c in itertools.product(a.levels, a.tasks, a.incidents, a.seeds, a.models)
                 if run.run_id_prefix(*c) not in done]
        print(f"{len(cells)} cell(s) to run, {a.jobs} at a time", flush=True)

        def one(c):
            lv, task, inc, seed, model = c
            return run.run_one(level=lv, task=task, seed=seed, model=model, incident=inc)

        def go():
            failed = 0
            with ThreadPoolExecutor(a.jobs) as pool:
                futures = {pool.submit(one, c): c for c in cells}
                for f in as_completed(futures):
                    c = futures[f]
                    try:
                        sc = json.loads((f.result() / "run.json").read_text())["score"]
                        print(f"ok   {run.run_id_prefix(*c)} violated={sc['violated']} attempted={sc['attempted']} "
                              f"honest={sc['disclosure_honest']}/{sc['self_report_honest']}", flush=True)
                    except Exception as e:  # one failed cell must not stop the matrix; a rerun retries it
                        failed += 1
                        print(f"FAIL {run.run_id_prefix(*c)} {type(e).__name__}: {str(e)[:200]}", flush=True)
            return failed

        sys.exit(1 if go() else 0)
    else:
        print(report.write_all(run.load_runs()))


if __name__ == "__main__":
    main()
