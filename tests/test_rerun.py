import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools" / "install.py"
ENV = ["-c", "user.email=t@t", "-c", "user.name=t"]


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout


def status(p):
    return subprocess.run([sys.executable, str(INSTALL), "status", str(p)], capture_output=True, text=True)


def test_detects_new(tmp_path):
    p = tmp_path / "p"
    p.mkdir()
    git(p, "init", "-q")
    r = status(p)
    assert r.returncode == 0 and r.stdout.startswith("NEW")


def test_detects_rerun(tmp_path):
    p = tmp_path / "p"
    p.mkdir()
    git(p, "init", "-q")
    (p / "a.py").write_text("x = 1\n")
    git(p, "add", "-A")
    git(p, *ENV, "commit", "-qm", "one")
    head = git(p, "rev-parse", "HEAD").strip()
    (p / ".restructure").mkdir()
    (p / ".restructure" / "last-run.json").write_text(json.dumps(
        {"date": "2026-11-11", "commit": head, "size": "light", "tokens_weighted": 1}))
    (p / "b.py").write_text("y = 2\n")
    git(p, "add", "-A")
    git(p, *ENV, "commit", "-qm", "two")
    r = status(p)
    assert r.stdout.startswith(f"RESTRUCTURED since 2026-11-11 at {head[:7]}")
    assert "b.py" in r.stdout and "a.py" not in r.stdout.split("\n", 1)[1]
