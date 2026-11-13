# codebase-steward

A [Claude Code](https://claude.com/claude-code) skill for cleaning up a codebase that has grown messy. It
restructures the project once, to ten fixed principles, without changing any result. It then leaves
behind the rules and checks that keep the project that way.

It is for projects with problems like these:
- the same helper pasted into five files;
- API keys or absolute paths written in the code;
- generated files committed to git;
- `-old` and `.bak` copies lying around;
- rules that contradict each other across docs.

## Four modes

The skill picks one from what you ask for.

| You say | Mode | What happens |
|---|---|---|
| "restructure this project" (never done before) | **Full process** | measure, safety net, spec, small committed steps, protect, prove, report |
| "restructure this project" (done before) | **Check and repair** | finds and fixes the drift since the last run, about half the cost |
| "start a new project" | **New project** | asks what it does, picks the folders, writes `CLAUDE.md` and switches the checks on before the first line of code |
| "add this feature" | **Feature check** | decides where the new feature belongs before writing it, then checks only what changed |

## The ten principles

The same ten apply to every project. Folder names are chosen per project; the principles are not.

1. One copy of shared code.
2. Layers depend in one direction only.
3. Every external tool or service sits behind one adapter. Keys live in `.env` only.
4. Paths come from one module.
5. Generated output stays outside git.
6. Docs live in `docs/`. Each rule sentence lives in one file.
7. No backup copies; git keeps old versions.
8. One generator ("door") makes each kind of new unit.
9. Settings that change between machines go in env or config.
10. Line endings and encodings are kept.

Details: [reference/principles.md](reference/principles.md).

## Safety

- **Results never change.** The full process records a baseline of the project's outputs before it
  starts. After each step it compares against that baseline; any difference stops the work.
- **Paid or irreversible actions are locked.** Live orders, deploys and paid API calls are blocked by
  a guard hook before the skill runs anything from the project.
- **Nothing is pushed or merged without your explicit OK.** `--no-verify` is never used.
- **Cost is reported at every phase.** The skill stops and asks if it goes past 1.5 times its estimate.

## Install

Clone it into your Claude Code skills folder:

```sh
git clone https://github.com/Moha7mmed/codebase-steward.git ~/.claude/skills/codebase-steward
```

Then ask Claude Code to start a new project, to restructure an existing one, or to add a feature. The skill loads by itself.

When a project is restructured, the skill installs its tools into that project's `.restructure/`
folder:
- a layout lint;
- the write guard;
- the baseline recorder;
- a token cost counter;
- a pre-commit hook, chained after any hook already there.

You can also run the installer by hand:

```sh
python ~/.claude/skills/codebase-steward/tools/install.py status <project>   # NEW, or restructured since when
python ~/.claude/skills/codebase-steward/tools/install.py <project>          # install or update the tools
```

It needs Python 3 and git (tested on Python 3.14).

## Layout

```
SKILL.md        what the agent reads first: modes, phases, rules
reference/      the principles, each phase in full, the re-run, the feature check, costs, the report format
tools/          the installed tools (lint, guard, baseline, token count, installer)
templates/      config, pre-commit and hooks templates
tests/          pytest suite and fixture projects
```

Run the tests with `python -m pytest -q`.

## License

[MIT](LICENSE)
