---
name: restructure-project
description: Use when a project's files and code are not laid out by the owner's principles (duplicated code, no shared modules, tools called from everywhere, keys or absolute paths in code, generated files in git, backup copies, rules repeated or contradicting) and it should be restructured once without changing any result, or when an already-restructured project needs a cheap check-and-repair, or when a new project should be built by those principles from the start, or when one new feature should be placed by them.
---

# Restructure a project

Restructure a project to fixed principles **without changing any result**, and leave behind the rules, the commit lint
and the guard that keep it that way. Proven on a real production project (2026-11-10/11). Talk to the owner in **his language**; this file
is English because agents read it.

## Step 0: which mode?

- **Starting a new project** (nothing, or a few files, yet): the **new project** mode,
  [reference/new-project.md](reference/new-project.md). Layout and checks before the first feature.
- **Adding one feature** (a module, tool, job or pattern) and not reorganising: the light **feature check**,
  [reference/feature.md](reference/feature.md). Restructured or not, no install, no baseline.
- **Reorganising:** run `python ~/.claude/skills/restructure-project/tools/install.py status <project>`.

  - `NEW` → the full process below.
  - `RESTRUCTURED since <date> at <commit>` → **check-and-repair** only: [reference/rerun.md](reference/rerun.md).

## The fixed principles

The same ten for every project: [reference/principles.md](reference/principles.md). Folder **names** are chosen per
project (its stack, its existing conventions) and written into its `CLAUDE.md` and `.restructure/config.json`; the
principles never change.

## The process

Full text, with what each phase must produce: [reference/phases.md](reference/phases.md).

| Phase | What | Always? |
|---|---|---|
| 0 Measure | read-only recon, choose size, announce cost range | yes |
| 1 Safety net | safety commit + tag, baseline record/compare, **lock paid/irreversible actions** (install guard) | yes |
| 2 Spec + plan | target layout, old → new map; owner approves the spec | yes |
| 3 Execute | small committed steps, `compare` after each, no result changes | yes |
| 4 Protect | project `CLAUDE.md`, lint + pre-commit, guard, every rule sentence in one home | yes |
| 5 Prove | fresh-agent end-to-end run + rule sweep, full compare, final review | yes (merged at light size) |
| 6 Finish | owner report, last-run record; push/merge only on his OK | yes |

Sizes and the cost estimate to announce: [reference/sizes-and-cost.md](reference/sizes-and-cost.md).

## The tools

`python ~/.claude/skills/restructure-project/tools/install.py <project>` installs into `<project>/.restructure/`:
`layout_lint.py` (+ `layout_rules.py`), `write_guard.py`, `baseline.py`, `tokens.py`, a `config.json` you then fill for
the project, the PreToolUse hook (added beside existing hooks) and the pre-commit hook (chained, never replacing).

## Owner rules (never broken)

- Phase 0 runs **nothing** from the project until the guard is installed.
- Ask the owner which actions cost money or cannot be undone; lock them in the guard before any run.
- No merge, push or PR without his explicit OK; when given, push only the branch he names. Never `--no-verify`.
- Report cost at every phase end (`python .restructure/tokens.py --from <start> --project-dir <session folder>`); **stop and ask** past 1.5× the estimate.
- A project rule or memory of the owner overrides this skill.
- Report with [reference/owner-report.md](reference/owner-report.md).
