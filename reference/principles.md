# The fixed principles

The same for every project. The names of folders are the project's own; these rules are not.

1. **One copy of shared code.** Code that repeats (12 identical lines or more) lives once, in a shared module or folder,
   and every part calls it. A data file (script text, fixtures) may repeat; code may not.
2. **Separation of concerns, one direction.** Layers depend one way only (for example app/domain → core → adapters).
   Shared code never names one specific feature, course, strategy or style; it reads them from config.
3. **Ports and adapters.** Every external tool or service (APIs, brokers, ffmpeg, browsers, cloud) sits behind one adapter
   folder. Keys come from `.env` only, never committed; `.env.example` lists the names only.
4. **Paths from one module.** No hard-coded top-folder paths, no `__file__`-style path building scattered in code; a missing
   path is a new function in the paths module.
5. **Generated output outside git.** Working files, logs and caches go to one ignored working folder; exports to their own
   ignored folder.
6. **Docs in `docs/`, rules in rule files.** A rule sentence lives in one file; the others link to it. No two docs disagree.
7. **No backup copies.** No `-old`, `.bak`, `_v2`, `copy`, `-before` files or folders: git keeps every old version.
8. **One door for a new unit.** When the project makes units (parts, modules, strategies), one generator makes them; never
   "copy a sibling folder".
9. **Config in the environment** (Twelve-Factor): settings that change between machines are env or config, not code.
10. **Line endings and encodings are kept.** Each file keeps its own; tools read and write bytes.
