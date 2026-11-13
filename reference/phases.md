# The phases

Every phase ends with a cost line to the owner (`python .restructure/tokens.py --from <start> --project-dir <the folder
the Claude Code session was opened in>`: the logs belong to the session's folder, not the target project; `--from` is
UTC, as in the logs, e.g. `date -u +%Y-%m-%dT%H:%M:%S` at the start). Past 1.5× the announced
estimate: stop and ask.

## Phase 0: Measure (read-only)

Run **nothing** from the project (no tests, no scripts, no installs): the guard is not in place yet. Read and count:

- files by type; duplicated blocks (12+ identical lines); existing tests and how they run;
- rule/agent docs (`CLAUDE.md`, `AGENTS.md`, `docs/`, `.claude/agents/`) and repeated or conflicting rule sentences;
- external services and where they are called; **paid or irreversible actions** (paid APIs, live orders, sends, deletes);
- generated files, backups, absolute paths and key-looking strings tracked in git.

Awkward starts: not a git repo → ask, then `git init`; uncommitted work → **stop and ask** (never fold it into the safety
commit); existing hook managers (husky, pre-commit framework, `.claude/settings.json` hooks) → keep them, add beside.

Report a short table and a size ([sizes-and-cost.md](sizes-and-cost.md)) with the cost range. The owner may override.

## Phase 1: Safety net

1. A branch for the work (e.g. `restructure`), then a safety commit if anything is uncommitted by the owner's OK, and the
   tag `structure-start` on the starting commit.
2. Ask the owner which actions cost money or cannot be undone. Install the tools
   (`python ~/.claude/skills/codebase-steward/tools/install.py <project>`), fill `.restructure/config.json`
   (`paid_commands`, `paid_hosts`, `paid_env_vars`, `paid_skills`, `guard_files`, `never_edit`) and check the guard denies
   each one by feeding it events (`echo '<event json>' | python .restructure/write_guard.py`, with **absolute** paths, as
   Claude Code sends them). Run `python .restructure/write_guard.py --check`: it must say `guard config: OK` (it flags
   template placeholders, typos and an empty paid list). The owner runs paid actions himself as `! <command>`. Write
   the known limits into the project `CLAUDE.md`.
   Paid entries: `{"module": "pkg.mod", "flag": "--live"}` for `python -m pkg.mod`; `{"script": "orders.py", "flag":
   "--live"}` for a file run directly or after any interpreter (python, node, bash…); `"flags": [...]` for several;
   `"requires": ["--stt"]` when the flag only costs together with another; `paid_imports` for python code that imports
   a paid library; `paid_hosts` / `paid_env_vars` / `paid_headers` deny any command naming them; `paid_skills` the
   Claude Code skills that spend. `door: {"pattern": "(<unit folder regex>)", "command": "<generator>"}` (group 1 = the
   unit folder); `free`: extra folders the guard never judges.
   **Stop here until the guard is live.** The hook runs only in a Claude Code session opened **in that project**, after
   `/hooks` once. If this session was opened elsewhere, stop: ask the owner to open Claude Code in the project and
   continue there. Prove it live with one paid test command that must come back denied. Only then run project code.
3. Baseline: describe "same result" in `config.json` `baseline` (test command + output commands, fixed inputs, normalisers
   for timestamps/seeds), then `python .restructure/baseline.py record`. Compare checks output **contents**, so a step
   that moves where an output is written only updates `outputs` in the same commit; the results must still match. `NOT DETERMINISTIC` (exit 2) → stop and ask the
   owner before moving anything.

## Phase 2: Spec and plan

A spec: the target layout **with names chosen for this project** (its stack and conventions), the old → new map, what is
out of scope, the rule docs to consolidate. The owner approves it. Then a plan (superpowers:writing-plans), tasks sized by
Phase 0; at light size the plan may be a section of the spec.

## Phase 3: Execute

Small committed steps; `python .restructure/baseline.py compare` after each; no result may change (a bug found is listed,
not fixed, unless the fix keeps results identical). Strictly one task after another unless the owner allows overlap.
Token savers: a fresh context per task, a short ledger, reviewers read the diff only, short agent reports.

Full size: superpowers:subagent-driven-development (implementer + reviewer per task). Standard: one review per phase.
Light: one implementer, one final review.

## Phase 4: Protect

- Project `CLAUDE.md`: the layout (its names), the ten principles as rules, the checks, the known limits.
- `.restructure/config.json` `allowed` globs describe every file's home; `python .restructure/layout_lint.py --all` clean.
- Pre-commit hook on (`git config core.hooksPath` or the project's hook manager).
- **All rule and agent docs consolidated:** every rule sentence one home, others link; no contradictions; stale paths fixed.

## Phase 5: Prove

- **End-to-end:** a fresh agent with only the project's rules makes a new unit through the one door and runs the checks;
  the guard log shows no refusals; only the expected folders changed; then delete the unit.
- **Rule sweep:** a fresh agent answers 15–20 realistic situations from the rule files with file:line and lists
  contradictions/stale references; fix; one confirming pass (target: 2 passes).
- Light size: these two are one fresh-agent pass.
- Full `baseline.py compare`; one final whole-branch review on the most capable model; one fix pass; scoped re-review.

## Phase 6: Finish

Report with [owner-report.md](owner-report.md); write his open decisions into the project's status file (make
`docs/status.md` if there is none). Write `.restructure/last-run.json` (`date`, `commit`, `size`,
`tokens_weighted`) and commit it. Push or merge **only** on the owner's explicit OK, only the branch he names.
