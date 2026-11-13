# New project: built by the principles from the first commit

Use this mode when the owner starts a project from nothing, or one with only a few files, and
wants the agent to build it the right way instead of cleaning it up later.

Nothing exists yet, so nothing can change. There is no baseline, no safety tag and no
old-to-new map. The work is deciding the layout once, writing it down, and switching the checks
on before the first feature.

## 1. Ask, one question at a time

Ask only what changes the layout:

- what the project does, and who or what runs it: a person, cron, a server or a bot;
- the language and stack, if the owner has a preference. Otherwise propose one and say why;
- every outside tool or service it will call: APIs, brokers, browsers, cloud, other CLIs;
- which actions cost money or cannot be undone: live orders, paid API calls, sending messages,
  deploys. These go into the guard before any code runs;
- whether it will make many units of one kind, such as strategies, courses, pages or patterns. If
  so, it gets a door (step 4).

## 2. Choose the folders

Use the stack's own conventions for the names. The roles are fixed, one folder each:

| Role | Principle | Example (Python) |
|---|---|---|
| shared code other parts call | 1 | `src/<pkg>/core/` |
| the layers, one dependency direction | 2 | `app/` → `core/` → `adapters/` |
| one adapter per outside service | 3 | `src/<pkg>/adapters/<service>/` |
| the paths module | 4 | `src/<pkg>/core/paths.py` |
| working files, logs, results (ignored) | 5 | `var/` |
| docs and rule files | 6 | `docs/`, `CLAUDE.md` |
| settings that differ per machine | 9 | `.env` (ignored), `.env.example` (names only) |

Tell the owner the layout in a few lines, in his language, and build on his OK. This is the
only approval gate in this mode.

## 3. Write the rules down before the code

- **`CLAUDE.md`:**
  - the ten principles, linked to [principles.md](principles.md) rather than copied;
  - the folder names chosen above;
  - the paid actions;
  - the door, if any.
  This is what every later agent reads, so it is the main deliverable of this mode.
- **`.gitignore`:** the working folder and `.env`.
- **`.env.example`:** each key's name, no values.
- **The paths module:** the folders above as named constants, nothing built from `__file__`
  anywhere else.

## 4. Switch the checks on

1. `git init`, then commit the files above, because the installer refuses a folder with
   uncommitted work.
2. `python ~/.claude/skills/codebase-steward/tools/install.py <project>`.
3. Fill `.restructure/config.json`:
   - `allowed`: the chosen folders;
   - `paid_commands`, `paid_hosts`, `paid_env_vars`: from step 1;
   - `shared_code_dirs`;
   - `door`: if units are made.
   Leave `baseline.commands` empty until the project produces a result worth comparing.
4. If units are made: write the generator, one command that makes a unit's folder, its
   registration and its test stub. Make the first unit through it, never by copying.
5. Commit through the hooks. The guard, the layout lint and the pre-commit hook are live from
   here on.

## 5. Then build

Every feature from now on goes through the feature check ([feature.md](feature.md)): decide
where it belongs, write it, and check what changed.

Once the project has outputs, add them to `baseline.commands`, so a later full process or
re-run can prove that nothing changed.

## Report

In the owner's language:
- the layout;
- where the rules live;
- the locked paid actions;
- the door, if any;
- the first commit.
