"""Layout lint (codebase-steward skill): refuses a commit that breaks the project's layout rules.

  python .restructure/layout_lint.py --staged   (the pre-commit hook)
  python .restructure/layout_lint.py --all      (every tracked file)
  python .restructure/layout_lint.py --sizes    (each rule file's size and margin)

Exit 0 clean, 1 findings. It never writes a file.
"""
import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout_rules as R  # noqa: E402

TOOL_DIR = ".restructure/"


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    msg: str

    def __str__(self):
        return f"{self.rule} {self.path}:{self.line} {self.msg}"


def _git(root, *args, binary=False):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def _tracked(root, staged):
    return [p for p in _git(root, "ls-files", "-z", "--cached").split("\0") if p]


def _changed(root):
    """Staged changes: list of (status, path, old_path)."""
    out = []
    for line in _git(root, "diff", "--cached", "--name-status", "-M").splitlines():
        parts = line.split("\t")
        st = parts[0][:1]
        if st == "R":
            out.append(("D", parts[1], None))
            out.append(("A", parts[2], parts[1]))
        else:
            out.append((st, parts[1], None))
    return out


def _read(root, path, staged):
    if staged:
        return _git(root, "show", f":{path}", binary=True)
    p = Path(root) / path
    return p.read_bytes() if p.is_file() else b""


def _text(data: bytes) -> str:
    return data.decode("utf-8", "replace")


def _per_file(cfg, path, text):
    if path.startswith(TOOL_DIR):
        return []
    f = []
    if R.BACKUP_RE.search(path) and not R.under(path, cfg.history_excludes):
        return [Finding("backup-name", path, 1, "a backup copy; git keeps old versions: delete it")]
    parts = path.split("/")
    if (Path(path).suffix.lower() in R.GEN_EXT and any(d in cfg.gen_dirs for d in parts[:-1])
            and not R.under(path, cfg.gen_homes)):
        return [Finding("generated-output", path, 1, f"generated output belongs in {cfg.gen_homes[0]}")]
    if R.role_of(cfg, path) is None:
        f.append(Finding("misplaced", path, 1, "fits no allowed home in .restructure/config.json"))
    legacy = path in cfg.legacy
    if not R.under(path, cfg.history_excludes):
        for i, line in enumerate(text.splitlines(), 1):
            if not legacy and R.ABS_RE.search(line):
                f.append(Finding("absolute-path", path, i, "an absolute path; use the paths module or config"))
                break
        for i, line in enumerate(text.splitlines(), 1):
            if R.KEY_RE.search(line):
                f.append(Finding("key", path, i, "a key in a tracked file; keys live in .env"))
                break
    if R.is_rule_file(cfg, path) and len(text.encode("utf-8")) > cfg.size_cap:
        f.append(Finding("size-cap", path, 1, f"rule file over {cfg.size_cap} bytes: split it by topic"))
    return f


def _windows(text, n):
    lines = [(i, ln.strip()) for i, ln in enumerate(text.splitlines(), 1)]
    lines = [(i, s) for i, s in lines if s and s not in ("}", "{", ")", "]", "});", "end")]
    for k in range(len(lines) - n + 1):
        chunk = "\n".join(s for _, s in lines[k:k + n])
        yield lines[k][0], hashlib.sha1(chunk.encode()).hexdigest()


def _dups(cfg, files, texts, judge):
    seen = {}
    found = set()
    out = []
    for path in sorted(files):
        if not R.is_code(path) or path.startswith(TOOL_DIR) or path in cfg.legacy:
            continue
        is_src_only = R.under(path, cfg.dup_skip)
        for line, h in _windows(texts[path], cfg.dup_lines):
            first = seen.get(h)
            if first is None:
                if not is_src_only:
                    seen[h] = (path, line)
            elif first[0] != path and path in judge and path not in found and not is_src_only:
                found.add(path)
                out.append(Finding("duplicate-code", path, line,
                                   f"{cfg.dup_lines}+ lines also in {first[0]}:{first[1]}: make one shared helper"))
    return out


def _sentences(text):
    for s in re.split(r"(?<=[.!?؟])\s+", re.sub(r"\s+", " ", text)):
        s = s.strip()
        if len(s) >= 80 and not s.startswith(("|", "-", "#", "```")):
            yield s


def _rule_dups(cfg, files, texts, judge):
    seen, out = {}, []
    for path in sorted(p for p in files if R.is_rule_file(cfg, p)):
        for s in _sentences(texts[path]):
            if s in seen and seen[s] != path and path in judge:
                out.append(Finding("rule-duplicate", path, 1, f"a rule sentence also in {seen[s]}: link to it"))
                break
            seen.setdefault(s, path)
    return out


def _widened(cfg, root):
    out = []
    changes = _changed(root)
    note_changed = any(p == cfg.exceptions_note for _, p, _ in changes)
    if note_changed:
        return out
    watched = list(cfg.guard_files) + [R.CONFIG_PATH]
    for st, path, _ in changes:
        if R.any_match(path, watched) or path in cfg.guard_files:
            what = {"D": "deletes", "A": "adds"}.get(st, "changes")
            out.append(Finding("rules-widened", path, 1,
                               f"{what} a guard or rules file: change the exceptions note in {cfg.exceptions_note} "
                               "in the same commit to say what and why (owner sign-off)"))
    return out


def _line_endings(root, changes):
    out = []
    for st, path, _ in changes:
        if st != "M":
            continue
        old, new = _git(root, "show", f"HEAD:{path}", binary=True), _git(root, "show", f":{path}", binary=True)
        if b"\0" in old[:8000]:
            continue
        o, n = b"\r\n" in old, b"\r\n" in new
        if old.count(b"\n") > 1 and o != n:
            out.append(Finding("line-endings", path, 1, "the file's line endings changed (%s → %s): keep its own"
                               % ("CRLF" if o else "LF", "CRLF" if n else "LF")))
    return out


def lint(root, staged: bool):
    root = Path(root)
    cfg = R.load_config(root, _text(_read(root, R.CONFIG_PATH, True)) if staged else None)
    files = _tracked(root, staged)
    if staged:
        changes = _changed(root)
        judge = {p for st, p, _ in changes if st != "D"}
    else:
        judge = set(files)
    texts = {p: _text(_read(root, p, staged)) for p in files}
    out = []
    for p in sorted(judge):
        out += _per_file(cfg, p, texts.get(p, ""))
    out += _dups(cfg, files, texts, judge)
    out += _rule_dups(cfg, files, texts, judge)
    if staged:
        out += _widened(cfg, root)
        out += _line_endings(root, changes)
    return out


def sizes(root):
    root = Path(root)
    cfg = R.load_config(root)
    for p in _tracked(root, False):
        if R.is_rule_file(cfg, p):
            n = len(_read(root, p, False))
            print(f"{n:7d}  margin {cfg.size_cap - n:7d}  {p}")


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--sizes", action="store_true")
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    if a.sizes:
        sizes(a.root)
        return 0
    found = lint(a.root, staged=a.staged)
    for f in found:
        print(f)
    print(f"{len(found)} finding(s)" if found else "layout lint: clean")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
