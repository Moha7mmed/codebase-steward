"""Token use of this project's Claude Code sessions (codebase-steward skill): main conversations + their subagents.

  python .restructure/tokens.py                       every session of this project
  python .restructure/tokens.py --from 2026-11-10     only calls at or after that time (UTC, as in the log)

Each API call counts once (by message id). "weighted" prices every kind of token as plain input (cache read x0.1,
cache write x1.25 for 5 min or x2 for 1 h, input x1, output x5): the number to compare runs and to check the 1.5x stop.
"""
import argparse
import json
import re
import sys
from pathlib import Path

KEYS = [("cache read", "cache_read_input_tokens"), ("cache write", "cache_creation_input_tokens"),
        ("new input", "input_tokens"), ("output", "output_tokens")]


def logs_dir_for(project: Path) -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path(project).resolve()))


def weighted(u):
    h1 = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)
    m5 = u.get("cache_creation_input_tokens", 0) - h1
    return (u.get("cache_read_input_tokens", 0) * 0.1 + m5 * 1.25 + h1 * 2 + u.get("input_tokens", 0)
            + u.get("output_tokens", 0) * 5)


def _calls(files, start, end):
    calls = {}
    for f in files:
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") != "assistant" or not (start <= r.get("timestamp", "") <= end):
                continue
            m = r.get("message", {})
            if m.get("usage"):
                calls[m.get("id")] = m["usage"]
    return calls


def _sum(calls):
    out = {name: sum(u.get(k, 0) for u in calls.values()) for name, k in KEYS}
    out["calls"] = len(calls)
    out["weighted"] = sum(weighted(u) for u in calls.values())
    return out


def tally_dir(logs_dir: Path, start: str = "", end: str = "9"):
    logs_dir = Path(logs_dir)
    mains = sorted(logs_dir.glob("*.jsonl"))
    subs = sorted(logs_dir.glob("*/subagents/**/*.jsonl"))
    return {"main": _sum(_calls(mains, start, end)), "agents": _sum(_calls(subs, start, end))}


def weighted_since(start: str, project_dir: Path = Path("."), logs_dir: Path = None) -> float:
    t = tally_dir(logs_dir or logs_dir_for(project_dir), start)
    return t["main"]["weighted"] + t["agents"]["weighted"]


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--from", dest="start", default="")
    ap.add_argument("--to", dest="end", default="9")
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--logs-dir", default=None)
    a = ap.parse_args(argv)
    d = Path(a.logs_dir) if a.logs_dir else logs_dir_for(Path(a.project_dir))
    if not d.is_dir():
        print(f"no session logs in {d}: pass --project-dir <the folder the Claude Code session was opened in>")
        return 1
    t = tally_dir(d, a.start, a.end)
    m, s = t["main"], t["agents"]
    print("%-12s %16s %16s %16s" % ("", f"main ({m['calls']} calls)", f"agents ({s['calls']} calls)", "total"))
    for name in [k for k, _ in KEYS] + ["weighted"]:
        print("%-12s %16s %16s %16s" % (name, f"{round(m[name]):,}", f"{round(s[name]):,}", f"{round(m[name] + s[name]):,}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
