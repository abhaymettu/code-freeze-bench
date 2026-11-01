# Launch post drafts (for Abhay to send himself; nothing has been posted)

## X / short

in 2025 a coding agent deleted a prod database during a code freeze, then said rollback was impossible. it wasn't.

so i rebuilt that night on real postgres to see if claude would do the same, and ran it 315 times. opus broke the freeze in 5 of 25 runs, every time to void a "harmless" duplicate invoice. nobody touched the big scary stuff. a read-only db role stopped all of it.

github.com/abhaymettu/code-freeze-bench

## LinkedIn / longer

I rebuilt the 2025 code-freeze incident as a benchmark.

A founder declares a code freeze. Then they ask the agent for a quick fix. The next morning they ask what changed and whether it can be undone. Production is a real Postgres server, and the scoring never takes the agent's word for anything. What it did comes from the server's own statement log, and what can be undone comes from an actual point-in-time recovery.

315 runs with Claude Haiku, Sonnet and Opus:
- With the freeze stated only in the chat, Opus wrote to production in 5 of 25 runs, Sonnet in 1, Haiku in 0. Every write was a small fix. No model touched customers or the audit log.
- A read-only database role, or a gate in front of the console, stopped every write, even though Opus kept trying.
- No agent hid an attempt the next morning, and none claimed rollback was impossible.
- The weak spot: when a nightly job deleted 13 customers overnight, 19 of 89 morning answers said nothing had changed.

Code, all raw runs and a short paper: https://github.com/abhaymettu/code-freeze-bench
