# AGENTS.md

Notes for coding agents working on this repository.

## What this is

A benchmark. Each run builds a real Postgres 17 server in Docker, declares a code freeze, runs Claude Code headless
against it with one tempting request, asks it the next morning what changed, and scores the answers against the
server's statement log, state fingerprints and a real point-in-time recovery.

## Layout

- `freezetest/scenarios.py` holds the freeze text, the five tasks and the morning question. Changing any of them changes
  what the benchmark measures, so old runs stop being comparable.
- `freezetest/levels.py` holds the enforcement levels. `freezetest/gate.py` is the typed permission gate.
- `freezetest/env.py` builds production, declares the freeze, plants the incident and measures damage.
- `freezetest/pg.py` drives Postgres through `docker exec`. `freezetest/audit.py` reads the statement log.
- `freezetest/score.py` scores one run. `freezetest/report.py` builds the scoreboard, the figure and the paper tables.
- `freezetest/agent_claude.py` is the Claude Code harness and its isolation settings.
- `results/<run_id>/` holds one run each: `run.json` and two transcripts. `results/archive/` holds older runs that the
  scoreboard ignores.

## Commands

```bash
uv run pytest -q tests/test_units.py      # fast, no Docker
uv run pytest -q                          # adds real Postgres and PITR tests (needs Docker)
make bench                                # one agent run and its scorecard
uv run freezetest matrix --levels gate --models haiku --seeds 1-2   # a slice of the grid
uv run freezetest scoreboard              # regenerate results/SCOREBOARD.md, docs/hero.svg, paper/results.tex
make paper                                # build paper/main.pdf with tectonic
```

## Rules

- Never hand-edit `results/*/run.json`, `results/SCOREBOARD.md`, `results/summary.json`, `docs/hero.svg` or
  `paper/results.tex`. They are generated.
- Nothing under `freezetest/` may name the real 2025 incident: the agent can read parts of it, and the name would cue
  the model. A test enforces this.
- No em or en dashes in our own prose. A test enforces this too; agent transcripts are exempt.
- The detector must stay independent of the agent: never score from what the agent says it did.
