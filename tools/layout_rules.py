"""The project's layout rules, read from .restructure/config.json (restructure-project skill).

Nothing here names a project: every folder name comes from the config the agent writes for the project.
"""
import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = ".restructure/config.json"

CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php",
            ".sh", ".ps1", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".lua", ".dart"}
GEN_EXT = {".json", ".txt", ".svg", ".png", ".jpg", ".csv", ".log", ".html"}

# A real project's CLAUDE.md rule, generalised: backup copies are never committed.
BACKUP_RE = re.compile(
    r"(?i)(?:[-_.]before(?:[-_.]|$)|\.removed-|[-_]old(?:[-_./]|$)|\.old\.|\.orig$|\.bak$|~$"
    r"|[-._]v\d+\.(?:js|py|json|html|ts)$|[-_. ]copy(?:[-_. ]|$)|(?:^|/)copy[-_ ]of[-_ ])")
ABS_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:(?:\\\\|\\|/)[A-Za-z0-9_.$ -]+|(?<![\w.])/(?:Users|home)/[A-Za-z0-9_.-]+/")
KEY_RE = re.compile(
    r"(?:sk_live_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[bap]-[A-Za-z0-9-]{20,}"
    r"|(?i:(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']))")


@dataclass
class Config:
    allowed: dict = field(default_factory=dict)
    gen_homes: list = field(default_factory=lambda: ["var/"])
    gen_dirs: list = field(default_factory=lambda: ["out", "qa", "tmp", "cache", "frames", "work"])
    rule_globs: list = field(default_factory=lambda: ["CLAUDE.md"])
    guard_files: list = field(default_factory=list)
    never_edit: list = field(default_factory=list)
    legacy: list = field(default_factory=list)
    dup_lines: int = 12
    size_cap: int = 32000
    dup_skip: list = field(default_factory=lambda: ["templates/", "reference/"])
    history_excludes: list = field(default_factory=lambda: ["docs/history/"])
    exceptions_note: str = "CLAUDE.md"
    raw: dict = field(default_factory=dict)


def load_config(root: Path, text: str = None) -> Config:
    """the config from the working copy, or from `text` (the lint's --staged passes the index's copy)"""
    p = Path(root) / CONFIG_PATH
    if text is None:
        text = p.read_text(encoding="utf-8") if p.exists() else ""
    data = json.loads(text) if text.strip() else {}
    known = {k: data[k] for k in Config.__dataclass_fields__ if k in data and k != "raw"}
    return Config(**known, raw=data)


def match(path: str, pattern: str) -> bool:
    """fnmatch with '**' meaning any depth (and '*' staying inside one folder)."""
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3] + "/") or path == pattern[:-3]
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.fullmatch(rx, path) is not None


def any_match(path: str, patterns) -> bool:
    return any(match(path, p) for p in patterns)


def role_of(cfg: Config, path: str):
    for pat, role in cfg.allowed.items():
        if match(path, pat):
            return role
    return None


def is_code(path: str) -> bool:
    return Path(path).suffix.lower() in CODE_EXT


def is_rule_file(cfg: Config, path: str) -> bool:
    return any_match(path, cfg.rule_globs)


def under(path: str, prefixes) -> bool:
    return any(path.startswith(p) for p in prefixes)


def fnmatch_any(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)
