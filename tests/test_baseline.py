import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "baseline.py"


def make(tmp_path, script):
    p = tmp_path / "proj"
    (p / ".restructure").mkdir(parents=True)
    (p / "app.py").write_text(script, encoding="utf-8")
    cfg = {"baseline": {"dir": "var/baseline", "tests": f'"{sys.executable}" -c "print(1)"',
                        "commands": [{"name": "run", "run": f'"{sys.executable}" app.py', "outputs": ["var/out/*.txt"],
                                      "normalise": [{"glob": "*.txt", "regex": r"at=\S+", "replace": "at=X"}]}]}}
    (p / ".restructure" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return p


def call(p, *args):
    return subprocess.run([sys.executable, str(TOOL), *args, "--root", str(p)], capture_output=True, text=True)


STABLE = ("import os\nos.makedirs('var/out', exist_ok=True)\n"
          "open('var/out/r.txt','w').write('result 42\\n')\n")


def test_record_then_compare_match(tmp_path):
    p = make(tmp_path, STABLE)
    assert call(p, "record").returncode == 0
    r = call(p, "compare")
    assert r.returncode == 0 and "BASELINE MATCH" in r.stdout


def test_compare_detects_change(tmp_path):
    p = make(tmp_path, STABLE)
    call(p, "record")
    (p / "app.py").write_text(STABLE.replace("42", "43"), encoding="utf-8")
    r = call(p, "compare")
    assert r.returncode == 1 and "run MISMATCH" in r.stdout and "BASELINE MISMATCH" in r.stdout


def test_compare_normalises_fields(tmp_path):
    p = make(tmp_path, "import os,time\nos.makedirs('var/out', exist_ok=True)\n"
                       "open('var/out/r.txt','w').write('result 42 at=%f\\n' % time.time())\n")
    assert call(p, "record").returncode == 0
    assert call(p, "compare").returncode == 0


def test_not_deterministic_exit2(tmp_path):
    p = make(tmp_path, "import os,random\nos.makedirs('var/out', exist_ok=True)\n"
                       "open('var/out/r.txt','w').write(str(random.random()))\n")
    r = call(p, "record")
    assert r.returncode == 2 and "NOT DETERMINISTIC: run" in r.stdout


def test_tests_failing_is_mismatch(tmp_path):
    p = make(tmp_path, STABLE)
    call(p, "record")
    cfg = json.loads((p / ".restructure" / "config.json").read_text())
    cfg["baseline"]["tests"] = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    (p / ".restructure" / "config.json").write_text(json.dumps(cfg))
    r = call(p, "compare")
    assert r.returncode == 1 and "tests MISMATCH" in r.stdout


def test_moved_output_still_matches(tmp_path):
    p = make(tmp_path, STABLE)
    call(p, "record")
    (p / "app.py").write_text(STABLE.replace("var/out", "var/out/new").replace("'var/out/new/r.txt'", "'var/out/new/r.txt'"),
                              encoding="utf-8")
    cfg = json.loads((p / ".restructure" / "config.json").read_text())
    cfg["baseline"]["commands"][0]["outputs"] = ["var/out/new/*.txt"]
    (p / ".restructure" / "config.json").write_text(json.dumps(cfg))
    r = call(p, "compare")
    assert r.returncode == 0 and "BASELINE MATCH" in r.stdout


def test_stale_output_not_reused(tmp_path):
    p = make(tmp_path, STABLE)
    call(p, "record")
    (p / "app.py").write_text(STABLE.replace("var/out", "var/elsewhere").replace("42", "43"), encoding="utf-8")
    r = call(p, "compare")
    assert r.returncode == 1


def test_no_output_matched_fails(tmp_path):
    p = make(tmp_path, "print('writes nothing')\n")
    r = call(p, "record")
    assert r.returncode == 2 and "no output" in r.stdout
