import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import layout_lint  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "messy"

CONFIG = {
    "allowed": {"README.md": "readme", "CLAUDE.md": "rules", "app/*.py": "app code", "core/*.py": "core code",
                "shared/*.py": "shared code", ".restructure/**": "restructure tools", ".gitignore": "git"},
    "gen_homes": ["var/"],
    "gen_dirs": ["out", "qa", "tmp", "cache"],
    "rule_globs": ["CLAUDE.md", "docs/rules/*.md"],
    "guard_files": [".restructure/write_guard.py", ".claude/settings.json"],
    "dup_lines": 12,
    "size_cap": 32000,
    "dup_skip": ["templates/", "reference/"],
}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(FIX, dst)
    (dst / ".restructure").mkdir()
    (dst / ".restructure" / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    git(dst, "init", "-q")
    git(dst, "config", "core.autocrlf", "false")
    git(dst, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(dst, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return dst


def rules(findings):
    return {(f.rule, f.path) for f in findings}


def test_messy_fixture_findings(repo):
    got = rules(layout_lint.lint(repo, staged=False))
    assert got == {
        ("backup-name", "app/x.bak"),
        ("backup-name", "app/film-old.js"),
        ("generated-output", "out/result.json"),
        ("duplicate-code", "app/b.py"),
        ("absolute-path", "core/paths.py"),
        ("key", "core/keys.py"),
    }


def test_clean_after_fix(repo):
    for p in ["app/x.bak", "app/film-old.js", "out/result.json", "core/keys.py"]:
        git(repo, "rm", "-q", p)
    (repo / "core" / "paths.py").write_text('import os\nDATA = os.environ.get("DATA_DIR", "data")\n')
    (repo / "app" / "b.py").write_text("from app.a import a as b\n")
    git(repo, "add", "-A")
    assert layout_lint.lint(repo, staged=False) == []


def test_misplaced_names_home(repo):
    (repo / "notes.txt").write_text("x\n")
    git(repo, "add", "notes.txt")
    f = [x for x in layout_lint.lint(repo, staged=True) if x.path == "notes.txt"]
    assert f and f[0].rule == "misplaced"


def test_staged_reads_index(repo):
    # an unstaged new file is not judged by --staged
    (repo / "stray.txt").write_text("x\n")
    assert all(x.path != "stray.txt" for x in layout_lint.lint(repo, staged=True))


def _commit_env(repo):
    return ["-c", "user.email=t@t", "-c", "user.name=t"]


def test_rules_widened_add_delete_rename(repo):
    (repo / ".restructure" / "write_guard.py").write_text("# guard\n")
    (repo / "CLAUDE.md").write_text("# rules\n\n## Exceptions note\nnone\n")
    git(repo, "add", "-A")
    git(repo, *_commit_env(repo), "commit", "-qm", "guard")
    # delete
    git(repo, "rm", "-q", "--cached", ".restructure/write_guard.py")
    assert ("rules-widened", ".restructure/write_guard.py") in rules(layout_lint.lint(repo, staged=True))
    git(repo, "reset", "-q")
    # add a new guard-listed file
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text("{}\n")
    git(repo, "add", ".claude/settings.json")
    assert ("rules-widened", ".claude/settings.json") in rules(layout_lint.lint(repo, staged=True))
    # with the CLAUDE.md note changed in the same commit, it passes
    (repo / "CLAUDE.md").write_text("# rules\n\n## Exceptions note\nsettings added by owner\n")
    git(repo, "add", "CLAUDE.md")
    assert all(f.rule != "rules-widened" for f in layout_lint.lint(repo, staged=True))


def test_lint_keeps_crlf_untouched(repo):
    p = repo / "app" / "a.py"
    before = p.read_bytes().replace(b"\n", b"\r\n")
    p.write_bytes(before)
    layout_lint.lint(repo, staged=False)
    assert p.read_bytes() == before


def test_cli_exit_codes(repo):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "layout_lint.py"), "--all", "--root", str(repo)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "key" in r.stdout


def test_line_endings_change_refused(repo):
    p = repo / "app" / "a.py"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    git(repo, "add", "app/a.py")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "crlf")
    p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n") + b"# more\n")
    git(repo, "add", "app/a.py")
    assert ("line-endings", "app/a.py") in rules(layout_lint.lint(repo, staged=True))


def test_same_line_endings_pass(repo):
    p = repo / "app" / "a.py"
    p.write_bytes(p.read_bytes() + b"# more\n")
    git(repo, "add", "app/a.py")
    assert all(f.rule != "line-endings" for f in layout_lint.lint(repo, staged=True))


def test_staged_reads_config_from_index(repo):
    cfg = json.loads((repo / ".restructure" / "config.json").read_text())
    cfg["allowed"]["*.txt"] = "widened but not staged"
    (repo / ".restructure" / "config.json").write_text(json.dumps(cfg))
    (repo / "notes.txt").write_text("x\n")
    git(repo, "add", "notes.txt")
    assert ("misplaced", "notes.txt") in rules(layout_lint.lint(repo, staged=True))
