# Feature check: place one new feature by the principles

Use this mode when the owner asks to **add** something to a project, such as a new module, tool, job
or pattern, rather than to reorganise it. It works whether or not the project went through the full
process.

It is light: no safety tag, no baseline and no fresh-agent proof. It exists so a new feature lands in
the right place the first time, instead of drifting until the next re-run.

Proven on a real trading project, 2026-11-13. One-off scan scripts became one detector per
pattern in a shared package, with a single scan command and tests on the owner's real examples.

## 1. Before writing: decide where it goes

1. Read the layout the project already has: its `CLAUDE.md`, and `.restructure/config.json` if
   present. Use the project's folder names, never this skill's.
2. Answer each question in one line. Each answer is a placement decision.

   | Question | If yes |
   |---|---|
   | Will other parts call it, now or later? | the shared module or folder (principle 1) |
   | Does it talk to an outside tool or service? | that service's adapter folder; keys from `.env` (3) |
   | Does it need a path? | ask the paths module; add a function there if it is missing (4) |
   | Does it write working files, logs or results? | the ignored working folder (5) |
   | Does it carry a rule (thresholds, a definition)? | one rule file; the code links to it and does not restate it (6) |
   | Is it one of a kind the project makes many of? | the project's door for that kind; if there is none and a third copy is coming, make one (8) |
   | Does a setting change between machines or users? | env or a command-line option, not code (9) |

3. Look for existing code that already does part of it, such as a script, a helper or an old
   one-off. Reuse it or move it; never paste a second copy.
4. Tell the owner the placement in two or three lines, in his language: what goes where, and why.
   Then build. This is not an approval gate unless the placement changes the project's layout.

## 2. While writing

- Give units of the same kind one shape, for example the same function signature for every
  detector, so a single caller runs them all.
- Test on the owner's own real cases (his approved examples), saved as small fixtures, not on
  invented data.
- A rule sentence the feature adds goes into its one home. The project's `CLAUDE.md` gets a
  pointer of a few lines, not the rule again.

## 3. After writing: check only what changed

1. `python .restructure/layout_lint.py --staged` after `git add` (the same check the pre-commit hook
   runs), or the project's own guard if it was never restructured.
2. Run the project's tests for the touched area.
3. Read the diff for:
   - copies of existing code, including short ones the lint misses;
   - hard-coded paths or keys;
   - output written inside git;
   - a rule now written in two places.
4. Commit through the project's hooks, never with `--no-verify`.

## 4. When the feature does not fit

The layout may have no right place for the feature: a new layer, a new paid action, or a shape
that breaks a dependency direction. Stop and tell the owner it needs a re-run, or the full process.
Do not bend the layout silently.

## Report

Five lines, in the owner's language:
- where it went;
- what was reused;
- what was tested, on which of his examples;
- what was left out, and why;
- the commit.
