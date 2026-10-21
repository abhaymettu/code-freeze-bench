from __future__ import annotations

import argparse
import json

from . import run, scenarios


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="freezetest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="one seeded run of the Claude Code harness")
    r.add_argument("--level", choices=run.LEVELS, default="prompt")
    r.add_argument("--task", choices=sorted(scenarios.TASKS), required=True)
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--model", default="sonnet")
    r.add_argument("--keep", action="store_true", help="leave the containers up afterwards")
    r.add_argument("--lock-wait", type=float, default=0, help="seconds to wait for the compute lock")
    sub.add_parser("scoreboard", help="rewrite results/SCOREBOARD.md from results/*/run.json")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        with run.compute_lock(a.lock_wait):
            out = run.run_one(level=a.level, task=a.task, seed=a.seed, model=a.model, keep=a.keep)
        rec = json.loads((out / "run.json").read_text())
        print(json.dumps({"run": str(out), "score": rec.get("score")}, indent=2))
    else:
        md = run.scoreboard(run.load_runs())
        (run.RESULTS / "SCOREBOARD.md").write_text(md)
        print(md)


if __name__ == "__main__":
    main()
