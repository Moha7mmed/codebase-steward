import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _front(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def test_frontmatter_valid():
    fm = _front((ROOT / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["name"] == ROOT.name == "codebase-steward"
    assert fm["description"].startswith("Use when")
    assert len(fm["description"]) <= 1024


def test_principles_has_ten():
    text = (ROOT / "reference" / "principles.md").read_text(encoding="utf-8")
    nums = re.findall(r"^(\d+)\. \*\*", text, re.M)
    assert nums == [str(i) for i in range(1, 11)]


def test_links_resolve():
    files = [ROOT / "SKILL.md"] + sorted((ROOT / "reference").glob("*.md"))
    for f in files:
        for target in re.findall(r"\]\(([^)#\s]+)\)", f.read_text(encoding="utf-8")):
            if target.startswith("http"):
                continue
            assert (f.parent / target).exists(), f"{f.name}: broken link {target}"
