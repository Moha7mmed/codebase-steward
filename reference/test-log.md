# Test log (fresh-agent proofs, 2026-11-11)

Fixture: `tests/fixtures/trading-like/` (3 strategies with copied helpers, a broker key and an absolute path in code,
`results_old.csv`, generated `out/results.json`, `orders.py --live` = a real order).

| Run | Path | Result | Weighted tokens |
|---|---|---|---|
| 1 | full process, light | shared code in `core/`, broker behind `adapters/`, key to `.env`, one door for strategies, `var/` results; BASELINE MATCH after every step; lint clean; no `--live` run; report in Arabic | ~1.32 M |
| 2 | re-run after a teammate's hook-less commit | check-and-repair: found the copied helper + absolute path, removed the stray file, BASELINE MATCH, lint clean | ~0.58 M |

Gaps the runs found and how they were fixed: line endings not checked → `line-endings` lint rule; two pre-commit copies →
one; moved outputs broke the baseline → compare by content; unclear guard test, branch, light plan, status file, token
folder/UTC, re-run estimate, tool update needing the exceptions note, hand-made units → phases.md / rerun.md text.

Not tested by a live session: the guard as a real hook (subagents run in another project's session); it was tested by
feeding events, as in `tests/test_write_guard.py`.
Skipped: a "without the skill" control run (the first real project's history before 2026-11-10 is that control).
