"""Install the restructure tools into a project, or report where it stands (restructure-project skill).

  python ~/.claude/skills/restructure-project/tools/install.py <project> [--dry-run]
  python ~/.claude/skills/restructure-project/tools/install.py status <project>

install: copies the tools into <project>/.restructure/ (an update overwrites the tools, never config.json), writes
config.json from the template only when absent, adds the guard hook to .claude/settings.json beside any hooks already
there, chains the layout lint into the existing pre-commit hook (husky, core.hooksPath, .git/hooks) or makes one, and
adds the working folder to .gitignore. Each file keeps its line endings. It refuses (exit 3) a folder that is not a git
repository or has uncommitted work: the skill then asks the owner.
status: NEW, or "RESTRUCTURED since <date> at <commit>" and the files changed since that commit.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TOOLS = ["layout_lint.py", "layout_rules.py", "write_guard.py", "baseline.py", "tokens.py"]
PY = Path(sys.executable).stem            # the interpreter name this machine answers to (python / python3)
LINT_LINE = PY + " .restructure/layout_lint.py --staged || exit 1"


def _git(p, *a):
    return subprocess.run(["git", *a], cwd=p, capture_output=True, text=True)


def _nl(data: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in data else b"\n"


def _append_line(path: Path, line: str, dry, report, before_exec=False):
    """add a line once; before_exec: put it before the hook's first exec/exit line (pre-commit framework, husky)"""
    data = path.read_bytes() if path.exists() else b""
    if line.encode() in data:
        return
    nl = _nl(data) if data else b"\n"
    if data and not data.endswith(nl):
        data += nl
    report.append(f"add '{line}' to {path.as_posix()}")
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not before_exec:
        path.write_bytes(data + line.encode() + nl)
        return
    lines = data.split(nl)
    at = next((i for i, ln in enumerate(lines) if re.match(rb"\s*(exec|exit)\b", ln)), None)
    if at is None:
        at = len(lines) - 1 if lines and lines[-1] == b"" else len(lines)
    lines.insert(at, line.encode())
    path.write_bytes(nl.join(lines))


def _merge_settings(p: Path, dry, report):
    f = p / ".claude" / "settings.json"
    raw = f.read_bytes() if f.exists() else b""
    s = json.loads(raw.decode("utf-8")) if raw.strip() else {}
    pre = s.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if any(".restructure/write_guard.py" in h.get("command", "") for e in pre for h in e.get("hooks", [])):
        return
    tpl = json.loads((SKILL / "templates" / "settings.hooks.json").read_text(encoding="utf-8"))
    for e in tpl["hooks"]["PreToolUse"]:
        for h in e["hooks"]:
            h["command"] = re.sub(r"^python\b", PY, h["command"])
    pre.extend(tpl["hooks"]["PreToolUse"])
    report.append("add the guard hook to .claude/settings.json (existing hooks kept)")
    if not dry:
        f.parent.mkdir(parents=True, exist_ok=True)
        nl = _nl(raw) if raw else b"\n"
        f.write_bytes(json.dumps(s, indent=2, ensure_ascii=False).replace("\n", nl.decode()).encode("utf-8") + nl)


def _hook_file(p: Path):
    """the pre-commit file git really runs, and whether it is ours to create"""
    hp = _git(p, "config", "core.hooksPath").stdout.strip()
    if hp.rstrip("/").endswith(".husky/_"):                 # husky v9: the user hooks are .husky/<name>
        return p / hp.rstrip("/")[:-2] / "pre-commit"
    if hp:
        return p / hp / "pre-commit"
    return p / ".git" / "hooks" / "pre-commit"


def _pre_commit(p: Path, dry, report):
    f = _hook_file(p)
    if f.exists():
        _append_line(f, LINT_LINE, dry, report, before_exec=True)
    else:
        report.append(f"make {f.relative_to(p).as_posix()}")
        if not dry:
            f.parent.mkdir(parents=True, exist_ok=True)
            tpl = (SKILL / "templates" / "pre-commit").read_text(encoding="utf-8")
            f.write_bytes(re.sub(r"^python\b", PY, tpl, flags=re.M).encode())
    if not dry and f.exists():
        f.chmod(f.stat().st_mode | 0o111)


def install(p: Path, dry=False):
    if _git(p, "rev-parse", "--git-dir").returncode != 0:
        print("REFUSED: not a git repository: ask the owner, then git init and a first commit")
        return 3
    if _git(p, "status", "--porcelain").stdout.strip():
        print("REFUSED: uncommitted work in the project: ask the owner (never fold it into the safety commit)")
        return 3
    report = []
    d = p / ".restructure"
    for t in TOOLS:
        report.append(f"copy {t} to .restructure/")
        if not dry:
            d.mkdir(exist_ok=True)
            shutil.copyfile(SKILL / "tools" / t, d / t)
    if not (d / "config.json").exists():
        report.append("write .restructure/config.json from the template (fill it for this project)")
        if not dry:
            shutil.copyfile(SKILL / "templates" / "config.example.json", d / "config.json")
    _merge_settings(p, dry, report)
    _pre_commit(p, dry, report)
    cfg = d / "config.json"
    homes = json.loads(cfg.read_text(encoding="utf-8")).get("gen_homes", ["var/"]) if cfg.exists() else ["var/"]
    for h in list(homes) + [".restructure/__pycache__/"]:
        _append_line(p / ".gitignore", h, dry, report)
    print(("DRY RUN, would:\n" if dry else "") + "\n".join("  " + r for r in report))
    return 0


def status(p: Path):
    f = p / ".restructure" / "last-run.json"
    if not f.exists():
        print("NEW (no restructure recorded): run the full process")
        return 0
    last = json.loads(f.read_text(encoding="utf-8"))
    commit = last.get("commit", "")
    print(f"RESTRUCTURED since {last.get('date')} at {commit[:7]} (size {last.get('size')}): check-and-repair")
    changed = _git(p, "diff", "--name-only", f"{commit}..HEAD").stdout.split()
    for c in changed:
        if c != ".restructure/last-run.json":
            print(f"  changed: {c}")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["status"]:
        return status(Path(argv[1]).resolve())
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("project")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    return install(Path(a.project).resolve(), a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
