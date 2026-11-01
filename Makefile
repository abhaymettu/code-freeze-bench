# One command: `make bench` brings up Postgres in Docker, runs one scenario and prints its scorecard.
TASK ?= cleanup
LEVEL ?= prompt
MODEL ?= haiku
SEED ?= 1

.PHONY: bench test matrix scoreboard paper

bench:
	@docker image inspect postgres:17-alpine >/dev/null 2>&1 || docker pull postgres:17-alpine
	@uv sync -q
	uv run freezetest run --task $(TASK) --level $(LEVEL) --model $(MODEL) --seed $(SEED)

test:
	uv run pytest -q

matrix:
	uv run freezetest matrix --seeds 1-5 --jobs 5
	uv run freezetest matrix --incidents planted --seeds 1-3 --jobs 5
	uv run freezetest scoreboard > /dev/null

scoreboard:
	uv run freezetest scoreboard

paper:
	cd paper && tectonic -X compile main.tex
