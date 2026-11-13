"""Baseline (codebase-steward skill): "the same result" before and after every step.

  python .restructure/baseline.py record [--only=a,b]    run everything twice, keep the hashes (exit 2 if two runs differ)
  python .restructure/baseline.py compare [--only=a,b]   run again and compare: BASELINE MATCH (0) or BASELINE MISMATCH (1)

Config (.restructure/config.json "baseline"): {"dir": "var/baseline", "tests": "<command>",
  "commands": [{"name", "run", "outputs": [globs], "normalise": [{"glob", "regex", "replace"}]}]}
Outputs are hashed after the normalisers (timestamps, seeds…), so only real changes count.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path


def _cfg(root):
    return json.loads((root / ".restructure" / "config.json").read_text(encoding="utf-8")).get("baseline", {})


def _run(cmd, root):
    return subprocess.run(cmd, shell=True, cwd=root, capture_output=True)


def _hash_outputs(root, c):
    out = {}
    for pattern in c.get("outputs", []):
        for f in sorted(root.glob(pattern)):
            if not f.is_file():
                continue
            data = f.read_bytes()
            for n in c.get("normalise", []):
                if fnmatch(f.name, n.get("glob", "*")):
                    data = re.sub(n["regex"].encode(), n["replace"].encode(), data)
            out[f.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return out


def _snapshot(root, cfg, only):
    snap = {}
    if cfg.get("tests") and (not only or "tests" in only):
        snap["tests"] = {"exit": _run(cfg["tests"], root).returncode}
    for c in cfg.get("commands", []):
        if only and c["name"] not in only:
            continue
        for pattern in c.get("outputs", []):          # a stale output from an earlier run must not pass for a new one
            for f in root.glob(pattern):
                if f.is_file():
                    f.unlink()
        r = _run(c["run"], root)
        snap[c["name"]] = {"exit": r.returncode, "outputs": _hash_outputs(root, c)}
        if c.get("outputs") and not snap[c["name"]]["outputs"]:
            snap[c["name"]]["no_output"] = True
    return snap


def record(root, only=None):
    cfg = _cfg(root)
    first = _snapshot(root, cfg, only)
    empty = [k for k, v in first.items() if v.get("no_output")]
    for k in empty:
        print(f"no output matched for {k}: fix its outputs globs (a baseline that hashes nothing proves nothing)")
    if empty:
        return 2
    second = _snapshot(root, cfg, only)
    bad = [k for k in first if first[k] != second.get(k)]
    for k in bad:
        print(f"NOT DETERMINISTIC: {k} (two runs differ: fix the inputs or add a normaliser, then ask the owner)")
    if bad:
        return 2
    d = root / cfg.get("dir", "var/baseline")
    d.mkdir(parents=True, exist_ok=True)
    old = json.loads((d / "snapshot.json").read_text()) if (d / "snapshot.json").exists() else {}
    old.update(first)
    (d / "snapshot.json").write_text(json.dumps(old, indent=1, sort_keys=True), encoding="utf-8")
    print(f"recorded {len(first)} item(s) in {d.relative_to(root).as_posix()}/snapshot.json")
    return 0


def _same(a, b):
    """same exit code and the same output contents (paths may move: a restructure moves files, not results)"""
    return a.get("exit") == b.get("exit") and sorted(a.get("outputs", {}).values()) == sorted(b.get("outputs", {}).values())


def compare(root, only=None):
    cfg = _cfg(root)
    base = json.loads((root / cfg.get("dir", "var/baseline") / "snapshot.json").read_text(encoding="utf-8"))
    now = _snapshot(root, cfg, only)
    bad = 0
    for k in sorted(now):
        if k not in base:
            print(f"{k} NEW (not in the baseline: record it)")
            bad += 1
        elif _same(base[k], now[k]):
            print(f"{k} OK")
        else:
            print(f"{k} MISMATCH")
            for f in sorted(set(base[k].get("outputs", {})) | set(now[k].get("outputs", {}))):
                if base[k].get("outputs", {}).get(f) != now[k].get("outputs", {}).get(f):
                    print(f"  {f}")
            if base[k].get("exit") != now[k].get("exit"):
                print(f"  exit {base[k].get('exit')} -> {now[k].get('exit')}")
            bad += 1
    print("BASELINE MATCH" if not bad else "BASELINE MISMATCH")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("action", choices=["record", "compare"])
    ap.add_argument("--only", default="")
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    only = {x for x in a.only.split(",") if x}
    root = Path(a.root).resolve()
    return record(root, only) if a.action == "record" else compare(root, only)


if __name__ == "__main__":
    sys.exit(main())
