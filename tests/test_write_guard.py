"""The write guard, run as the hook runs it (a subprocess, the event on stdin), against a temp project whose config names
paid commands like a real project's. Cases ported from that project's guard tests."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "write_guard.py"

HOST = "api." + "paidvoice" + ".io"          # built from pieces so no test file names a real service
KEYVAR = "PAIDVOICE_" + "API_KEY"
CONFIG = {
    "allowed": {"README.md": "readme", "CLAUDE.md": "rules", "src/**": "code", "shared/*.py": "shared",
                "docs/**": "docs", "units/*/*/main.py": "a unit", ".restructure/**": "tools"},
    "gen_homes": ["var/"],
    "gen_dirs": ["out", "qa", "tmp"],
    "guard_files": [".claude/settings.json"],
    "shared_code_dirs": ["shared/*.py"],
    "door": {"pattern": r"(units/[a-z]+/u\d+)(?:/|$)", "command": "python -m src.new_unit <name>"},
    "paid_commands": [{"module": "pipeline.voice", "flag": "--approved"},
                      {"module": "pipeline.pre_film", "flag": "--approved"},
                      {"module": "checks.letter_check", "flag": "--approved", "requires": ["--stt"]},
                      {"module": "src.orders", "flag": "--live"},
                      {"script": "orders.py", "flag": "--live"},
                      {"script": "send.js", "flag": "--live"}],
    "paid_imports": ["paidvoice", "adapters.paidvoice"],
    "paid_hosts": [HOST], "paid_env_vars": [KEYVAR], "paid_headers": ["xi-api-key"],
    "paid_skills": ["text-to-speech", "music"],
    "log": "var/guard.log",
}


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    p = tmp_path_factory.mktemp("proj")
    (p / ".restructure").mkdir()
    (p / ".restructure" / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    (p / "src").mkdir()
    (p / "shared").mkdir()
    (p / "shared" / "maths.py").write_text("".join(f"def f{i}(x):\n    return x + {i}\n" for i in range(15)))
    (p / "units" / "alpha" / "u1").mkdir(parents=True)
    return p


def run(proj, tool, **ti):
    ev = {"tool_name": tool, "tool_input": ti, "cwd": str(proj)}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(ev), capture_output=True, text=True, env=env)
    if r.returncode == 2:
        return "refused", r.stderr
    if r.stdout.strip():
        d = json.loads(r.stdout)["hookSpecificOutput"]
        return d["permissionDecision"], d["permissionDecisionReason"]
    return "allowed", ""


def bash(proj, cmd):
    return run(proj, "Bash", command=cmd)[0]


PAID = [
    "python -m pipeline.voice ep1 c01 --approved",
    'python -m "pipeline.voice" ep1 --approved',
    "python -m pipeline.voice ep1 '--approved'",
    "A=--approved; python -m pipeline.voice ep1 $A",
    "python -X utf8 -u -m pipeline.voice ep1 --approved",
    "python pipeline/voice.py ep1 --approved",
    "python -m pipeline.pre_film ep1 --approved",
    "python -m checks.letter_check ep1 --stt --approved",
    "uv run python -m pipeline.voice ep1 --approved",
    "poetry run python -m pipeline.voice ep1 --approved",
    'bash -c "python -m pipeline.voice ep1 --approved"',
    'cmd /c "python -m pipeline.voice ep1 --approved"',
    "python -m pipeline.voice ep1 `echo --approved`",
    'python -m pipeline.voice ep1 @("--approved")',
    'python -c "from pipeline import voice; voice.main([\'ep1\'])"',
    "python -c \"import runpy; runpy.run_module('pipeline.voice')\"",
    'python -c "import paidvoice"',
    "python - <<'EOF'\nfrom adapters.paidvoice import tts\nEOF",
    f"curl https://{HOST}/v1/tts -d x",
    f"echo ${KEYVAR}",
    "python -m src.orders buy 1 --live",
    "./orders.py BTC 1 --live",
    r".\orders.py BTC 1 --live",
    "node send.js --live",
    "python orders.py BTC 1 --l`ive",
    "python -m src.orders buy 1 --live=1",
    "python -m src.orders buy 1 --liv",
]

FREE_CMDS = [
    "python -m pipeline.voice ep1 c01",                  # the cost print only
    "python -m checks.letter_check ep1 --stt",           # cost print only
    "python -m checks.letter_check ep1 --approved",      # no --stt: not the paid run
    "grep -rn 'pipeline.voice' docs",
    'git commit -m "python -m pipeline.voice --approved is the owner\'s"',
    "echo python -m pipeline.voice --approved",
    "python -c \"print(open('adapters/paidvoice.py').read())\"",
    "python -m src.orders buy 1",                        # paper mode
    "python orders.py BTC 1",
    "grep -n -- --live orders.py",
    "node send.js --dry",
]


@pytest.mark.parametrize("cmd", PAID)
def test_paid_denied(proj, cmd):
    assert bash(proj, cmd) == "deny"


@pytest.mark.parametrize("cmd", FREE_CMDS)
def test_free_allowed(proj, cmd):
    assert bash(proj, cmd) == "allowed"


def test_paid_skill_denied(proj):
    assert run(proj, "Skill", skill="text-to-speech")[0] == "deny"
    assert run(proj, "Skill", skill="plugin:music")[0] == "deny"
    assert run(proj, "Skill", skill="brainstorming")[0] == "allowed"


def test_misplaced_write_refused_names_home(proj):
    st, why = run(proj, "Write", file_path=str(proj / "notes.txt"), content="x")
    assert st == "refused" and "fits no allowed home" in why


def test_backup_refused(proj):
    assert run(proj, "Write", file_path=str(proj / "src" / "main.bak"), content="x")[0] == "refused"


def test_generated_refused(proj):
    st, why = run(proj, "Write", file_path=str(proj / "src" / "out" / "r.json"), content="{}")
    assert st == "refused" and "var/" in why


def test_allowed_write(proj):
    assert run(proj, "Write", file_path=str(proj / "src" / "app.py"), content="print(1)\n")[0] == "allowed"


def test_copy_of_shared_refused(proj):
    content = (proj / "shared" / "maths.py").read_text()
    st, why = run(proj, "Write", file_path=str(proj / "src" / "maths2.py"), content=content)
    assert st == "refused" and "shared/maths.py" in why


def test_door_for_new_unit(proj):
    st, why = run(proj, "Write", file_path=str(proj / "units" / "beta" / "u2" / "main.py"), content="x")
    assert st == "refused" and "src.new_unit" in why
    assert run(proj, "Write", file_path=str(proj / "units" / "alpha" / "u1" / "main.py"), content="x")[0] == "allowed"


def test_guard_files_ask(proj):
    assert run(proj, "Edit", file_path=str(proj / ".restructure" / "write_guard.py"))[0] == "ask"
    assert run(proj, "Write", file_path=str(proj / "CLAUDE.md"), content="x")[0] == "ask"
    assert run(proj, "Write", file_path=str(proj / ".claude" / "settings.json"), content="{}")[0] == "ask"


def test_shell_write_refused(proj):
    assert bash(proj, "echo x > notes.txt") == "refused"
    assert bash(proj, "sed -i.bak s/a/b/ src/app.py") == "refused"
    assert bash(proj, "cd src && echo x > a.py") == "allowed"


def test_workspace_free(proj):
    assert bash(proj, "echo x > var/anything.txt") == "allowed"


def test_fail_open_on_bad_input(proj):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    r = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, env=env)
    assert r.returncode == 0


def test_broken_config_asks_for_shell(tmp_path):
    (tmp_path / ".restructure").mkdir()
    (tmp_path / ".restructure" / "config.json").write_text("{ not json", encoding="utf-8")
    st, why = run(tmp_path, "Bash", command="python orders.py BTC 1 --live")
    assert st == "ask" and "config" in why


def test_check_flags_placeholder_and_unknown_keys(tmp_path):
    (tmp_path / ".restructure").mkdir()
    cfg = dict(CONFIG, paid_commands=[{"module": "example.paid_tool", "flag": "--live"}], paid_comands=[])
    (tmp_path / ".restructure" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    r = subprocess.run([sys.executable, str(GUARD), "--check"], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "example.paid_tool" in r.stdout and "paid_comands" in r.stdout


def test_check_ok(proj):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    r = subprocess.run([sys.executable, str(GUARD), "--check"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout
