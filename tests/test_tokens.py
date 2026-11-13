import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tokens  # noqa: E402

LOGS = ROOT / "tests" / "fixtures" / "logs"


def test_counts_fixture():
    t = tokens.tally_dir(LOGS)
    # main: a (once) + b ; agents: c
    assert t["main"]["calls"] == 2 and t["agents"]["calls"] == 1
    assert t["main"]["cache read"] == 3000 and t["agents"]["cache read"] == 2000
    # weighted a = 1000*.1 + 100*1.25 + 10 + 20*5 = 335 ; b = 200 + 5 + 50 = 255 ; c = 255
    assert round(t["main"]["weighted"]) == 590 and round(t["agents"]["weighted"]) == 255


def test_from_filters():
    t = tokens.tally_dir(LOGS, start="2026-11-11")
    assert t["main"]["calls"] == 1 and round(t["main"]["weighted"] + t["agents"]["weighted"]) == 510
    assert round(tokens.weighted_since("2026-11-11", logs_dir=LOGS)) == 510


def test_cli():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "tokens.py"), "--logs-dir", str(LOGS)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "weighted" in r.stdout and "845" in r.stdout
