# Sizes and cost

Choose after Phase 0 and say it in plain words with the cost range; the owner may override.

| Size | Signals | Shape |
|---|---|---|
| light | under ~100 code files, few duplicates, few or no rule docs, one or no paid action | one implementer, one fresh-agent proof pass, one final review |
| standard | ~100–400 files, or real duplication, or a handful of rule docs | tasks grouped by phase, one review per phase |
| full | large, many rule/agent docs, several paid/irreversible actions, or a past of agents breaking rules | implementer + reviewer per task |

Every size keeps: baseline compare, lint + pre-commit, guard (also guarding itself), project `CLAUDE.md`.

## Reference numbers (estimates, weighted tokens)

| Case | Cost |
|---|---|
| a real project, full, with heavy Arabic rule docs (2026-11-10/11) | ~97 M |
| a code-only project of that size | ~30–50 M (estimate) |
| a small code project | ~1.5–15 M (trader test, light: 1.32 M) |
| a re-run (check-and-repair) | about half of the last run's `tokens_weighted` (trader test: 0.58 M vs 1.32 M) |

What drives cost (measured on that project): 97 % of tokens are context re-reads (long sessions, many agents re-reading plan,
ledger, diffs); the largest single topic was the rule docs; late-locked paid actions cost extra guard rounds. So: short
sessions, short ledgers, diff-only reviews, rule sweep in two passes, lock paid actions in Phase 1.
