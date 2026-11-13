import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools" / "install.py"
ENV = ["-c", "user.email=t@t", "-c", "user.name=t"]


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout


def repo(tmp_path, files=None):
    p = tmp_path / "p"
    p.mkdir()
    git(p, "init", "-q")
    git(p, "config", "core.autocrlf", "false")
    for name, data in (files or {"README.md": b"# p\n"}).items():
        f = p / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    git(p, "add", "-A")
    git(p, *ENV, "commit", "-qm", "init")
    return p


def install(p, *a):
    return subprocess.run([sys.executable, str(INSTALL), *a, str(p)], capture_output=True, text=True)


def test_install_fresh_repo(tmp_path):
    p = repo(tmp_path)
    r = install(p)
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ["layout_lint.py", "layout_rules.py", "write_guard.py", "baseline.py", "tokens.py", "config.json"]:
        assert (p / ".restructure" / f).exists(), f
    s = json.loads((p / ".claude" / "settings.json").read_text())
    cmds = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert any("write_guard.py" in c for c in cmds)
    assert "var/" in (p / ".gitignore").read_text()
    assert (p / ".git" / "hooks" / "pre-commit").exists()


def test_install_keeps_existing_hooks(tmp_path):
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}],
                          "Stop": [{"hooks": [{"type": "command", "command": "stop.sh"}]}]}}
    p = repo(tmp_path, {"README.md": b"x\n", ".claude/settings.json": json.dumps(settings).encode(),
                        ".husky/pre-commit": b"#!/bin/sh\nnpm test\n"})
    git(p, "config", "core.hooksPath", ".husky")
    assert install(p).returncode == 0
    s = json.loads((p / ".claude" / "settings.json").read_text())
    cmds = [h["command"] for ev in s["hooks"].values() for e in ev for h in e["hooks"]]
    assert "mine.sh" in cmds and "stop.sh" in cmds and any("write_guard.py" in c for c in cmds)
    hook = (p / ".husky" / "pre-commit").read_text()
    assert "npm test" in hook and "layout_lint.py --staged" in hook
    assert git(p, "config", "core.hooksPath").strip() == ".husky"


def test_install_refuses_dirty_tree(tmp_path):
    p = repo(tmp_path)
    (p / "README.md").write_text("changed\n")
    r = install(p)
    assert r.returncode == 3 and "ask the owner" in r.stdout


def test_install_refuses_non_git(tmp_path):
    p = tmp_path / "plain"
    p.mkdir()
    r = install(p)
    assert r.returncode == 3 and "not a git repository" in r.stdout


def test_install_idempotent(tmp_path):
    p = repo(tmp_path)
    install(p)
    (p / ".restructure" / "config.json").write_text('{"allowed": {"**": "mine"}}')
    (p / "CLAUDE.md").write_text("# rules\nExceptions note: tools installed by the owner.\n")
    git(p, "add", "-A")
    git(p, *ENV, "commit", "-qm", "installed")
    assert install(p).returncode == 0
    assert json.loads((p / ".restructure" / "config.json").read_text()) == {"allowed": {"**": "mine"}}
    s = json.loads((p / ".claude" / "settings.json").read_text())
    cmds = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert sum("write_guard.py" in c for c in cmds) == 1
    hook = (p / ".git" / "hooks" / "pre-commit").read_text()
    assert hook.count("layout_lint.py --staged") == 1


def test_install_keeps_crlf(tmp_path):
    p = repo(tmp_path, {"README.md": b"x\r\n", ".gitignore": b"node_modules/\r\n"})
    install(p)
    assert (p / "README.md").read_bytes() == b"x\r\n"
    data = (p / ".gitignore").read_bytes()
    assert data.startswith(b"node_modules/\r\n") and b"var/\r\n" in data


def test_dry_run_changes_nothing(tmp_path):
    p = repo(tmp_path)
    r = install(p, "--dry-run")
    assert r.returncode == 0 and not (p / ".restructure").exists()


def test_one_pre_commit_copy(tmp_path):
    p = repo(tmp_path)
    install(p)
    copies = [f for f in p.rglob("pre-commit")]
    assert copies == [p / ".git" / "hooks" / "pre-commit"]


def test_lint_runs_before_exec_line(tmp_path):
    p = repo(tmp_path)
    hook = p / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/usr/bin/env bash\n# pre-commit framework\nexec pre-commit hook-impl --hook-type=pre-commit\n")
    assert install(p).returncode == 0
    lines = hook.read_text().splitlines()
    lint = next(i for i, l in enumerate(lines) if "layout_lint.py --staged" in l)
    assert lint < next(i for i, l in enumerate(lines) if l.startswith("exec "))


def test_husky_v9_user_hook(tmp_path):
    p = repo(tmp_path, {"README.md": b"x\n", ".husky/pre-commit": b"npm test\n", ".husky/_/pre-commit": b"#!/bin/sh\n. h\n"})
    git(p, "config", "core.hooksPath", ".husky/_")
    assert install(p).returncode == 0
    assert "layout_lint.py --staged" in (p / ".husky" / "pre-commit").read_text()
    assert "layout_lint" not in (p / ".husky" / "_" / "pre-commit").read_text()


def test_other_git_hooks_kept(tmp_path):
    p = repo(tmp_path)
    (p / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\ngit lfs pre-push \"$@\"\n")
    assert install(p).returncode == 0
    assert subprocess.run(["git", "config", "core.hooksPath"], cwd=p, capture_output=True, text=True).stdout.strip() == ""
    assert "layout_lint" in (p / ".git" / "hooks" / "pre-commit").read_text()


def test_foreign_guard_does_not_block_ours(tmp_path):
    s = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python hooks/write_guard.py"}]}]}}
    p = repo(tmp_path, {"README.md": b"x\n", ".claude/settings.json": json.dumps(s).encode()})
    assert install(p).returncode == 0
    cmds = [h["command"] for e in json.loads((p / ".claude" / "settings.json").read_text())["hooks"]["PreToolUse"]
            for h in e["hooks"]]
    assert "python hooks/write_guard.py" in cmds and any(".restructure/write_guard.py" in c for c in cmds)


def test_settings_keep_non_ascii(tmp_path):
    s = {"note": "ملاحظة", "hooks": {}}
    p = repo(tmp_path, {"README.md": b"x\n", ".claude/settings.json": json.dumps(s, ensure_ascii=False).encode("utf-8")})
    install(p)
    assert "ملاحظة" in (p / ".claude" / "settings.json").read_text(encoding="utf-8")


def test_hook_uses_this_python(tmp_path):
    p = repo(tmp_path)
    install(p)
    exe = Path(sys.executable).stem
    cmds = [h["command"] for e in json.loads((p / ".claude" / "settings.json").read_text())["hooks"]["PreToolUse"]
            for h in e["hooks"]]
    assert any(c.startswith(exe + " ") for c in cmds)
