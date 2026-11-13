# Re-run: check and repair

`install.py status <project>` said `RESTRUCTURED since <date> at <commit>` and listed the files changed since.

0. Estimate: half of `tokens_weighted` in `.restructure/last-run.json`; announce it; the 1.5× stop applies to it.
1. Update the installed tools if the skill's are newer: `python ~/.claude/skills/restructure-project/tools/install.py <project>`
   (keeps `config.json`, keeps every hook). The tools are guard files: change the `CLAUDE.md` exceptions note in the same
   commit (what was updated and why), or the commit lint refuses it (`rules-widened`).
2. `python .restructure/layout_lint.py --all`; `python .restructure/baseline.py compare`.
3. Rule sweep **only over the rule/agent files changed since `<commit>`**: one fresh agent, contradictions and stale
   references with file:line.
4. Fix the drift in small committed steps, `compare` after each (same rules as Phase 3). Read every changed file, not only
   the lint's findings (the lint misses copies under 12 lines and units not made by the door). A unit made by hand:
   if it holds real work, remake it through the door and move the work in; if it holds nothing of its own, delete it
   (git keeps it). Either way, list it as an owner decision.
5. If the drift is large (many new modules, a new paid action, the layout no longer fits), say so and offer the full
   process instead.
6. Update `.restructure/last-run.json` (`date`, `commit`, `size: "rerun"`, `tokens_weighted`) and report with
   [owner-report.md](owner-report.md). Push only on the owner's OK.
