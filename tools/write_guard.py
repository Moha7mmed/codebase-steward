"""Write guard (codebase-steward skill), a Claude Code PreToolUse hook for
Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell|Skill. Every name comes from .restructure/config.json.

A new file (or folder) inside the project is REFUSED (exit 2, reason on stderr) when it is outside the layout (`allowed`),
a backup name, generated output outside the working folders (`gen_homes`), a copy (>= 20 lines, 80 % the same) of a file
in `shared_code_dirs`, or a new unit folder that `door.pattern` says only `door.command` may make.
A paid or irreversible call is DENIED in every permission mode (`paid_commands` with their flag, python code that imports or
runs them or `paid_imports`, any command naming `paid_hosts` / `paid_env_vars` / `paid_headers`, the `paid_skills`): the
owner runs it himself as `! <command>`. A write to the guard files (`guard_files`, `.restructure/`, CLAUDE.md) is ASKED.
The guard fails OPEN: an error of its own allows the call and is logged. Calls with a target are lines of `log`.
Known limits: writes from inside a program, a paid call hidden in a script file, Start-Process, xargs.
"""
import difflib, json, os, posixpath, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
HOME = Path(os.environ.get('CLAUDE_PROJECT_DIR') or HERE.parent)
try:
    import layout_rules as R
    CFG = R.load_config(HOME)
    ROOT, BROKEN = HOME, None
except Exception as e:                       # fail open even when the rules cannot be read
    R = CFG = None; ROOT, BROKEN = HOME, e
_c = (CFG.raw if CFG else {})
LOG = ROOT / _c.get('log', 'var/guard.log')
FREE = tuple(['.git/', '.superpowers/'] + list(_c.get('gen_homes', ['var/'])) + list(_c.get('free', [])))
FREE_FILES = ('.env',)
_guard_globs = list(_c.get('guard_files', [])) + ['.restructure/**', 'CLAUDE.md']
PAID = [d for d in _c.get('paid_commands', []) if isinstance(d, dict)]
PAID_MODULES = tuple(d.get('module') or re.sub(r'\.py$', '', d.get('script', '')).replace('/', '.') for d in PAID)
_mods = [m for m in PAID_MODULES if m] + list(_c.get('paid_imports', []))


def _mod_rx(m):
    parent, _, leaf = m.rpartition('.')
    alts = [r'\bimport\s+' + re.escape(m) + r'\b', r'\bfrom\s+' + re.escape(m) + r'(?:\.\w+)*\s+import\b',
            r'(?:import_module|__import__|run_module)\(\s*[\'"]' + re.escape(m)]
    if parent:
        alts.append(r'\bfrom\s+' + re.escape(parent) + r'\s+import\s+[^\n;]*\b' + re.escape(leaf) + r'\b')
    alts.append(r'\brun_path\(\s*[\'"][^\'"]*' + re.escape(leaf or m) + r'(?:\.py)?[\'"]')
    return '|'.join(alts)


PAID_CODE = re.compile('|'.join(_mod_rx(m) for m in _mods)) if _mods else re.compile(r'(?!x)x')
PAID_REASON = ('Paid or irreversible call: an agent never runs it, in any permission mode. STOP and give the owner what it '
               'will cost or do, and this exact command, which he runs himself at his prompt: ')
_svc = [re.escape(x) for x in list(_c.get('paid_hosts', [])) + list(_c.get('paid_env_vars', [])) + list(_c.get('paid_headers', []))]
SERVICE = re.compile('|'.join(_svc), re.I) if _svc else re.compile(r'(?!x)x')
SERVICE_OWNER = "! <the project's own command for it> (the service is never called by hand: see the project CLAUDE.md)"
PAID_SKILLS = {s.lower() for s in _c.get('paid_skills', [])}
LAUNCHERS = {'uv', 'poetry', 'pipx', 'conda'}
PY = re.compile(r'python[\d.]*|py')
SHARED_TOPS = tuple(_c.get('shared_code_dirs', []))
_door = _c.get('door') or {}
PART = re.compile(_door['pattern']) if _door.get('pattern') else None
DOOR = _door.get('command', '')
COPY_LINES, COPY_RATIO = 20, 0.8
HARMLESS = {'/dev/null', '/dev/stdout', '/dev/stderr', 'nul', 'con', '$null'}
SWITCHES = {'force', 'recurse', 'append', 'nonewline', 'noclobber', 'passthru', 'whatif', 'confirm', 'container', 'verbose'}
CD = {'cd', 'chdir', 'pushd', 'set-location', 'sl', 'push-location'}
POPD = {'popd', 'pop-location'}
SHELLS = {'bash': ('-c',), 'sh': ('-c',), 'zsh': ('-c',), 'powershell': ('-command', '-c'), 'pwsh': ('-command', '-c'),
          'cmd': ('/c', '/k')}
JOINED = {'powershell', 'pwsh', 'cmd'}
IO_FILE = re.compile(r'\[(?:System\.)?IO\.File\]::(?:Write|Append)\w*\(\s*([\'"])(.*?)\1', re.I)


def _is_guard(rel):
    return R is not None and R.any_match(rel, _guard_globs)


def _home(rel):
    return (CFG.gen_homes[0] if CFG and CFG.gen_homes else 'var/') + posixpath.basename(rel)


# --- the paths a call writes -----------------------------------------------------------------------------------------------
def _where(tok, cwd):
    """('in', rel) | ('out', abs) | ('unknown', tok) | ('skip', None) for a path token, seen from the folder cwd (None: unknown)"""
    t = (tok or '').strip()
    for v in ('${CLAUDE_PROJECT_DIR}', '$CLAUDE_PROJECT_DIR', '$env:CLAUDE_PROJECT_DIR'): t = t.replace(v, str(ROOT))
    if not t or t.lower() in HARMLESS: return 'skip', None
    if '$' in t or '*' in t or '?' in t or t.startswith('~') or t == '-': return 'unknown', tok
    t = t.replace('\\', '/')
    m = re.match(r'/([A-Za-z])/', t)
    if m: t = m.group(1) + ':/' + t[3:]                                    # Git Bash /c/<folder>/… → c:/<folder>/…
    if not (re.match(r'[A-Za-z]:/', t) or t.startswith('/')):
        if cwd is None: return 'unknown', tok                             # relative to a folder the guard could not follow
        t = str(cwd).replace('\\', '/').rstrip('/') + '/' + t
    t = posixpath.normpath(t)
    root = str(ROOT).replace('\\', '/').rstrip('/')
    if t.lower() == root.lower(): return 'in', ''
    return ('in', t[len(root) + 1:]) if t.lower().startswith(root.lower() + '/') else ('out', t)


def _rel(tok, cwd):
    """the project-relative form of a path token; None when it is outside the root or cannot be known"""
    state, v = _where(tok, cwd)
    return v if state == 'in' else None


def _strip(cmd):
    """the command without heredoc bodies, PowerShell here-strings and $(( arithmetic )), where a > is not a redirect"""
    cmd = re.sub(r'@([\'"])\r?\n.*?\r?\n\1@', "''", cmd, flags=re.S)
    cmd = re.sub(r'\$\(\(.*?\)\)', '', cmd, flags=re.S)
    out, lines, i = [], cmd.split('\n'), 0
    while i < len(lines):
        out.append(lines[i]); m = re.search(r'<<-?\s*([\'"]?)([\w.-]+)\1', lines[i]); i += 1
        if m:
            while i < len(lines) and lines[i].strip() != m.group(2): i += 1
            i += 1
    return '\n'.join(out)


def _segments(cmd):
    """the simple commands of a shell line: [[(kind, word)]], kind 'w' (a word, quotes removed) or '>' (a redirect target)"""
    segs, seg, word, quoted, q, nxt = [], [], '', False, None, 'w'
    i, s = 0, _strip(cmd)
    def end():
        nonlocal word, quoted, nxt
        if word or quoted:
            if nxt != 'skip': seg.append((nxt, word))
            nxt = 'w'
        word, quoted = '', False
    while i < len(s):
        ch = s[i]
        if q:
            if ch == q: q = None
            else: word += ch
        elif ch in '\'"': q = ch; quoted = True
        elif ch in ' \t\r': end()
        elif ch in ';|&()\n':
            end(); nxt = 'w'
            if seg: segs.append(seg); seg = []
        elif ch in '<>':
            if word.isdigit() and not quoted: word = ''                  # 2> : the descriptor, not a word
            end()
            j = i + 1
            while j < len(s) and s[j] in '<>|': j += 1
            if ch == '>' and j < len(s) and s[j] == '&': j += 1; nxt = 'skip'          # >&1 2>&1 : another descriptor
            else: nxt = '>' if ch == '>' else 'skip'                                    # < and << name an input
            i = j; continue
        else: word += ch
        i += 1
    end()
    if seg: segs.append(seg)
    return segs


def _named(args, values=()):
    """(positionals, {param: value}) of a command's words: -Name value (PowerShell), -x flags (bash); values: short flags that
    take a value (install -m 644)"""
    pos, named, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith('-') and len(a) > 1:
            k = a.lstrip('-').split(':')[0].lower()
            if a in values and i + 1 < len(args): named[a] = args[i + 1]; i += 2; continue
            if len(k) >= 3 and ':' not in a and k not in SWITCHES and not a.startswith('--') and i + 1 < len(args):
                named[k] = args[i + 1]; i += 2; continue
            i += 1; continue
        pos.append(a); i += 1
    return pos, named


def _inplace(cmd, args):
    """[(path token, kind, None)] of an in-place edit: sed -i / --in-place, perl -i (with a suffix, the backup copy it leaves
    is a new file too: sed -i.bak f → f and f.bak)"""
    files, script, inplace, suffix, i = [], False, False, '', 0
    while i < len(args):
        a = args[i]
        takes = ('-e', '-E') if cmd == 'perl' else ('-e', '-f', '--expression', '--file')        # a flag followed by the script
        if a in takes: script = True; i += 2; continue
        if a.startswith(('--expression=', '--file=')): script = True; i += 1; continue
        if a.startswith('--in-place'): inplace = True; suffix = a.partition('=')[2]; i += 1; continue
        m = re.fullmatch(r'-([A-Za-z]*)i(\S*)', a)
        if m and not a.startswith('--'):
            inplace = True
            rest = m.group(2)
            if cmd == 'perl' and rest.endswith('e'): rest = rest[:-1]; script = True; i += 1   # -pie: -p -i -e <code>
            if rest and not rest.startswith('-'): suffix = rest
            i += 1; continue
        if cmd == 'perl' and re.fullmatch(r'-[A-Za-z]*e', a): script = True; i += 2; continue      # -pe <code>
        if a.startswith('-') and len(a) > 1: i += 1; continue
        files.append(a); i += 1
    if not inplace: return []
    if not script and files: files = files[1:]                      # the first word is the script itself
    return [(f, 'file', None) for f in files] + [(f + suffix, 'file', None) for f in files if suffix]


def _writes(words):
    """[(path token, kind, source token)] of one simple command"""
    cmd, args = words[0].lower().rsplit('/', 1)[-1], words[1:]
    if cmd in ('sed', 'perl'): return _inplace(cmd, args)
    if cmd == 'git' and args[:1] == ['mv']: cmd, args = 'mv', args[1:]
    if cmd == 'dd': return [(a[3:], 'file', None) for a in args if a.startswith('of=')]
    if cmd in ('rename-item', 'rni', 'ren', 'rename'):                    # the new name sits next to the old file
        pos, named = _named(args)
        src = named.get('path') or named.get('literalpath') or (pos.pop(0) if pos else None)
        new = named.get('newname') or (pos[0] if pos else None)
        if not (src and new): return []
        if not re.search(r'[/\\]', new): new = posixpath.join(posixpath.dirname(src.replace('\\', '/')), new)
        return [(new, 'file', src)]
    if cmd in ('curl', 'wget'):
        flags = ('-o', '--output') if cmd == 'curl' else ('-O', '--output-document')
        out = [args[i + 1] for i, a in enumerate(args[:-1]) if a in flags]
        out += [a.split('=', 1)[1] for a in args if a.startswith(flags[1] + '=')]
        return [(t, 'file', None) for t in out]
    if cmd in ('invoke-webrequest', 'iwr', 'invoke-restmethod', 'irm'):
        t = _named(args)[1].get('outfile'); return [(t, 'file', None)] if t else []
    if cmd == 'tar':
        opts = args[:1] + [a for a in args if a.startswith('-') and not a.startswith('--')]
        x = any(a in ('--extract', '--get') for a in args) or any(re.fullmatch(r'-?[A-Za-z]*x[A-Za-z]*', a) for a in opts)
        d = [args[i + 1] for i, a in enumerate(args[:-1]) if a in ('-C', '--directory')]
        d += [a.split('=', 1)[1] for a in args if a.startswith('--directory=')]
        return [(t, 'dir', None) for t in d] if x else []
    if cmd == 'unzip': return [(args[i + 1], 'dir', None) for i, a in enumerate(args[:-1]) if a == '-d']
    if cmd == 'expand-archive':
        t = _named(args)[1].get('destinationpath'); return [(t, 'dir', None)] if t else []
    pos, named = _named(args, ('-t', '-m', '-o', '-g', '-e'))
    pick = lambda *keys: next((named[k] for k in keys if k in named), pos[0] if pos else None)
    if cmd in ('tee', 'touch'): return [(p, 'file', None) for p in pos]
    if cmd in ('mkdir', 'md'): return [(p, 'dir', None) for p in ([named['path']] if 'path' in named else pos)]
    if cmd in ('out-file', 'tee-object'): t = pick('filepath', 'path', 'literalpath'); return [(t, 'file', None)] if t else []
    if cmd in ('set-content', 'add-content', 'sc', 'ac'): t = pick('path', 'literalpath'); return [(t, 'file', None)] if t else []
    if cmd in ('new-item', 'ni'):
        t = pick('path', 'literalpath')
        if t and 'name' in named: t = t.rstrip('/\\') + '/' + named['name']
        kind = 'dir' if named.get('itemtype', '').lower() == 'directory' else 'file'
        return [(t, kind, None)] if t else []
    if cmd == 'install' and any(a == '-d' for a in args): return [(p, 'dir', None) for p in pos]
    if cmd in ('cp', 'mv', 'copy', 'move', 'copy-item', 'move-item', 'cpi', 'mi', 'install', 'rsync', 'ln'):
        tdir = named.get('-t') or next((a.split('=', 1)[1] for a in args if a.startswith('--target-directory=')), None)
        if tdir:                                                           # cp -t <dir> <src>…
            return [(tdir.rstrip('/\\') + '/' + posixpath.basename(p.replace('\\', '/').rstrip('/')), 'file', p) for p in pos]
        if cmd == 'rsync': pos = [p for p in pos if not re.match(r'[^/\\]{2,}:', p)]       # host:path is remote
        src = named.get('path') or named.get('literalpath') or (pos[0] if pos else None)
        dst = named.get('destination') or (pos[-1] if len(pos) >= 2 else None)
        return [(dst, 'file', src)] if dst else []
    return []


def _inner(name, words):
    """the inner command of bash/sh/zsh -c '…', powershell/pwsh -Command …, cmd /c … (/k), or None"""
    low = [w.lower() for w in words]
    k = next((i for i, w in enumerate(low) if w in SHELLS[name]), None)
    if k is None or k + 1 >= len(words): return None
    return ' '.join(words[k + 1:]) if name in JOINED else words[k + 1]


def _shell(cmd, cwd, depth=0):
    """[(state, path, kind, source path or None)] of a shell command; cd / pushd / popd / Set-Location move cwd"""
    out, stack = [], []
    for seg in _segments(cmd):
        words = [w for k, w in seg if k == 'w']
        while words and re.fullmatch(r'\w+=\S*', words[0]): words = words[1:]
        name = words[0].lower().rsplit('/', 1)[-1] if words else ''
        name = name[:-4] if name.endswith('.exe') else name
        if name in CD:
            if name in ('pushd', 'push-location'): stack.append(cwd)
            pos, named = _named(words[1:])
            arg = named.get('path') or named.get('literalpath') or (pos[0] if pos else None)
            state, v = _where(arg, cwd) if arg else ('unknown', None)
            cwd = {'in': lambda: str(ROOT) + ('/' + v if v else ''), 'out': lambda: v}.get(state, lambda: None)()
            continue
        if name in POPD: cwd = stack.pop() if stack else None; continue
        if name in SHELLS and depth < 3:
            inner = _inner(name, words)
            if inner: out += _shell(inner, cwd, depth + 1)
            continue
        for kind, w in seg:
            if kind == '>': out.append(_where(w, cwd) + ('file', None))
        if words:
            for tok, kind, src in _writes(words):
                out.append(_where(tok, cwd) + (kind, _where(src, cwd) if src else None))
    return out


def _calls(event):
    """[(rel or None, kind, content or None, shown)]: every in-project path the call writes, and every target it cannot know
    (rel None, shown '?<token>')"""
    ti, tool = event.get('tool_input') or {}, event.get('tool_name', '')
    cwd = event.get('cwd') or str(ROOT); found = []
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        found.append(_where(ti.get('file_path') or ti.get('notebook_path') or '', cwd) + ('file', ti.get('content') if tool == 'Write' else None))
        found = [(st, v, k, ('text', c)) for st, v, k, c in found]
    elif tool in ('Bash', 'PowerShell'):
        cmd = ti.get('command') or ''
        found = _shell(cmd, cwd) + [_where(m.group(2), cwd) + ('file', None) for m in IO_FILE.finditer(_strip(cmd))]
    out = []
    for state, v, kind, src in found:
        if state == 'unknown': out.append((None, kind, None, '?' + str(v))); continue
        if state != 'in' or not v: continue
        content = None
        if src and src[0] == 'text': content = src[1]
        elif src and src[0] in ('in', 'out') and src[1] is not None:
            f = ROOT / src[1] if src[0] == 'in' else Path(src[1])
            try: content = f.read_text(encoding='utf-8') if f.is_file() else None
            except (OSError, UnicodeDecodeError): content = None
            if (ROOT / v).is_dir(): v = v + '/' + posixpath.basename(src[1].rstrip('/'))
            if f.is_dir(): kind = 'dir'                                # a folder copied or moved (cp -r styles/a styles/b)
        out.append((v, kind, content, v))
    seen = set()
    return [c for c in out if not (c[3] in seen or seen.add(c[3]))]


def targets(event: dict) -> list:
    return [r for r, _, _, _ in _calls(event) if r is not None]


# --- the rules ------------------------------------------------------------------------------------------------------------
def _shared_files():
    for p in [q for top in SHARED_TOPS for q in ROOT.glob(top)]:
        r = p.relative_to(ROOT).as_posix()
        if p.is_file() and '__pycache__' not in r: yield r, p


def copy_of(rel, content):
    """the shared file a new text is a copy of (>= COPY_LINES lines, ratio >= COPY_RATIO), or None"""
    new = [l.rstrip() for l in content.splitlines()]
    if len(new) < COPY_LINES: return None
    for r, p in _shared_files():
        if r == rel: continue
        try: old = [l.rstrip() for l in p.read_text(encoding='utf-8').splitlines()]
        except (OSError, UnicodeDecodeError): continue
        sm = difflib.SequenceMatcher(None, new, old, autojunk=False)
        if sm.real_quick_ratio() >= COPY_RATIO and sm.quick_ratio() >= COPY_RATIO and sm.ratio() >= COPY_RATIO: return r, sm.ratio()
    return None


def _dir_allowed(rel):
    probes = ('README.md', 'x.md', 'x.py', 'x.js', 'x.ts', 'x.json', 'x.go', 'x/y.py', 'x/y.md')
    return any(R.role_of(CFG, rel + '/' + n) for n in probes)


def judge(rel, kind='file', content=None):
    """(status, reason) for one path the call writes: allowed | refused | ask"""
    if _is_guard(rel): return 'ask', 'a write to the guards themselves (%s): the owner confirms it' % rel
    if rel == '' or rel.startswith(FREE) or rel in FREE_FILES: return 'allowed', 'workspace'
    if (ROOT / rel).exists(): return 'allowed', 'existing'
    if R.BACKUP_RE.search(rel): return 'refused', 'a backup name: git keeps every old version (CLAUDE.md, no backup copies)'
    parts = rel.split('/')
    if kind == 'file' and Path(rel).suffix.lower() in R.GEN_EXT and any(d in CFG.gen_dirs for d in parts[:-1]):
        return 'refused', 'generated output outside the working folder → %s (CLAUDE.md)' % _home(rel)
    m = PART.match(rel) if PART else None
    if m and not (ROOT / m.group(1)).is_dir():
        return 'refused', 'a new unit folder: make it with the one door (%s), never by hand' % DOOR
    if kind == 'dir':
        return ('allowed', 'in place') if _dir_allowed(rel) else (
            'refused', 'outside the layout: no allowed file can live in %s/ (allowed in .restructure/config.json)' % rel)
    if R.role_of(CFG, rel) is None:
        return 'refused', 'outside the layout: %s fits no allowed home (.restructure/config.json; CLAUDE.md)' % rel
    if content:
        c = copy_of(rel, content)
        if c: return 'refused', ('a copy of %s (%.0f%% the same): call the shared code instead of copying it'
                                 % (c[0], c[1] * 100))
    return 'allowed', 'in place'


def _heredocs(cmd):
    """the bodies of the heredocs in a shell command (what a 'python -' reads from stdin)"""
    out, lines, i = [], cmd.split('\n'), 0
    while i < len(lines):
        m = re.search(r'<<-?\s*([\'"]?)([\w.-]+)\1', lines[i]); i += 1
        if m:
            body = []
            while i < len(lines) and lines[i].strip() != m.group(2): body.append(lines[i]); i += 1
            out.append('\n'.join(body)); i += 1
    return out


def _expand(word, env):
    """a word with the $NAME / ${NAME} / $env:NAME set earlier in the same command filled in"""
    return re.sub(r'\$\{?(?:env:)?(\w+)\}?', lambda m: env.get(m.group(1), m.group(0)), word)


def _assign(words, env):
    """record NAME=value (bash, also after export/set) and $NAME = value / $env:NAME = value (PowerShell); True when the
    segment was only an assignment"""
    w = words[1:] if words and words[0].lower() in ('export', 'set', 'local', 'declare') else words
    if len(w) >= 3 and re.fullmatch(r'\$(?:env:)?\w+', w[0], re.I) and w[1] == '=':
        env[re.sub(r'^\$(?:env:)?', '', w[0], flags=re.I)] = _expand(' '.join(w[2:]), env); return True
    m = re.fullmatch(r'\$?(?:env:)?(\w+)=(.*)', w[0], re.S | re.I) if w else None
    if m and (len(w) == 1 or w[0].startswith('$')): env[m.group(1)] = _expand(m.group(2), env); return True
    return False


def _owner_line(words):
    return '! ' + ' '.join("'%s'" % w if re.search(r'\s', w) else w for w in words)


INTERPRETERS = re.compile(r'python[\d.]*|py|node|deno|bun|ruby|perl|php|bash|sh|zsh|pwsh|powershell|java|dotnet|go')


def _flag_hit(args, flags):
    """a paid flag among args: exact, --flag=value, an abbreviation argparse accepts (--liv for --live), or an unknown
    $word / `word` that may be it"""
    for w in args:
        if '$' in w or '`' in w: return True
        for f in flags:
            if w == f or w.startswith(f + '=') or (w.startswith('--') and len(w) >= 4 and f.startswith(w)): return True
    return False


def _base(word):
    return word.replace('\\', '/').rsplit('/', 1)[-1].lower()


def _paid_script(words):
    """the owner's line when a paid `script` entry runs: as the command itself (./orders.py, .\\orders.py) or after an
    interpreter (python orders.py, node send.js)"""
    prog = re.sub(r'\.exe$', '', _base(words[0]))
    for i, w in enumerate(words):
        if i > 0 and not INTERPRETERS.fullmatch(prog): break
        for d in PAID:
            s = d.get('script')
            if not s or _base(w) != _base(s): continue
            rest = words[i + 1:]
            if any(r not in rest for r in d.get('requires', [])): return None
            flags = d.get('flags') or ([d['flag']] if d.get('flag') else [])
            if not flags or _flag_hit(rest, flags): return _owner_line(words)
            return None
    return None


def _paid_words(words, heredocs):
    """the owner's command line when this simple command (words: the command word first) is a paid call, else None"""
    hit = _paid_script(words)
    if hit: return hit
    prog = re.sub(r'\.exe$', '', words[0].replace('\\', '/').rsplit('/', 1)[-1].lower())
    if not PY.fullmatch(prog): return None
    rest = words[1:]
    for i, x in enumerate(rest):          # the paid module or script ANYWHERE in the args (python -X utf8 -u -m …, a full path)
        dotted = re.sub(r'\.py$', '', x.replace('\\', '/')).replace('/', '.')
        k = next((j for j, m in enumerate(PAID_MODULES) if m and re.fullmatch(r'(?:.*[./])?' + re.escape(m), dotted)), None)
        if k is None: continue
        d = PAID[k]
        if any(r not in rest for r in d.get('requires', [])): return None
        flags = d.get('flags') or ([d['flag']] if d.get('flag') else [])
        hit = (not flags) or _flag_hit(rest, flags)
        return _owner_line(['python', '-m', PAID_MODULES[k]] + rest[i + 1:]) if hit else None
    code = rest[rest.index('-c') + 1] if '-c' in rest and rest.index('-c') + 1 < len(rest) else None
    if code is None and ('-' in rest or not [x for x in rest if not x.startswith('-')]): code = '\n'.join(heredocs)   # stdin
    if code and PAID_CODE.search(code):
        return '! <the paid command this code runs> (see the project CLAUDE.md)'
    return None


def _paid_shell(cmd, env, depth=0):
    docs = _heredocs(cmd)
    for seg in _segments(cmd):
        words = [_expand(w, env) for k, w in seg if k == 'w']
        if not words or _assign(words, env): continue
        while words and (re.fullmatch(r'\w+=\S*', words[0]) or words[0].lower() in ('env', 'command', 'nohup', 'time', 'exec', 'call', 'sudo')):
            words = words[1:]
        if not words: continue
        if any(SERVICE.search(w) for w in words): return SERVICE_OWNER
        name = re.sub(r'\.exe$', '', words[0].lower().rsplit('/', 1)[-1])
        if name in LAUNCHERS and words[1:2] == ['run']:            # uv run [--with x] python -m …, uv run -m …, conda run -n e python …
            rest = words[2:]
            k = next((i for i, w in enumerate(rest) if PY.fullmatch(re.sub(r'\.exe$', '', w.replace('\\', '/').rsplit('/', 1)[-1].lower()))), None)
            words, name = ['python'] + (rest[k + 1:] if k is not None else rest), 'python'
        if name in SHELLS and depth < 3:
            inner = _inner(name, words)
            hit = _paid_shell(inner, dict(env), depth + 1) if inner else None
            if hit: return hit
            continue
        if name in ('eval', 'invoke-expression', 'iex') and depth < 3:
            hit = _paid_shell(' '.join(words[1:]), dict(env), depth + 1)
            if hit: return hit
            continue
        hit = _paid_words(words, docs)
        if hit: return hit
    return None


def paid(event: dict):
    """the command line the owner runs himself for the paid call a shell command makes, or None. Read from the command WORDS (quotes removed, $VAR set earlier filled in): only the command
    word counts, so grep / git commit -m / echo that merely name a paid command are not paid calls. The one exception, on
    purpose (fail safe, but noisy): a command that names the service itself (its API host or /v1 URL, the key variable, the
    xi-api-key header) is denied wherever the name sits, a grep or a commit message included"""
    ti = event.get('tool_input') or {}
    if event.get('tool_name') == 'Skill':          # {"skill": "text-to-speech", "args": …}; a plugin prefix (x:text-to-speech) too
        name = str(ti.get('skill') or '').strip().lower().rsplit(':', 1)[-1].rsplit('/', 1)[-1]
        return SERVICE_OWNER if name in PAID_SKILLS else None
    if event.get('tool_name') not in ('Bash', 'PowerShell'): return None
    cmd = str(ti.get('command') or '')
    if SERVICE.search(cmd): return SERVICE_OWNER
    cmd = re.sub(r'@\(([^()]*)\)', lambda m: m.group(1).replace(',', ' '), cmd)     # PowerShell @("--approved") → its items
    # `echo --approved` (bash) → its words; --l`ive (PowerShell drops the backtick) → --live: check both readings
    return _paid_shell(cmd.replace('`', ' '), {}) or _paid_shell(cmd.replace('`', ''), {})


def verdict(event: dict):
    """(status, reason, [shown paths]): a paid call is denied (the owner runs it himself), then a refusal wins,
    then an ask (a write to the guard files), else allowed"""
    calls = _calls(event); shown = [c[3] for c in calls]; asks = []
    owner = paid(event)
    if owner: return 'deny', PAID_REASON + owner, shown
    for rel, kind, content, _ in calls:
        if rel is None: continue
        status, why = judge(rel, kind, content)
        if status == 'refused': return 'refused', '%s: %s' % (rel, why), shown
        if status == 'ask': asks.append(why)
    if asks: return 'ask', '; '.join(asks), shown
    unknown = [s for s in shown if s.startswith('?')]
    return 'allowed', ('in place' if not unknown else 'in place; not judged (unknown path): ' + ' '.join(unknown)), shown


def decide(event: dict):
    status, reason, _ = verdict(event)
    return status not in ('refused', 'deny'), reason


def log(status, tool, path, reason):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8', newline='\n') as f:
            f.write('%s %s %s %s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), status, tool or '-', path or '-', ' '.join(str(reason).split())))
    except OSError:
        pass


def _out(stream, text):
    try: stream.buffer.write(text.encode('utf-8')); stream.flush()      # utf-8 whatever the console's code page
    except AttributeError: stream.write(text)


KNOWN_KEYS = {'_doc', 'allowed', 'gen_homes', 'gen_dirs', 'rule_globs', 'guard_files', 'never_edit', 'legacy', 'dup_lines',
              'size_cap', 'dup_skip', 'history_excludes', 'exceptions_note', 'log', 'free', 'paid_commands', 'paid_imports',
              'paid_hosts', 'paid_env_vars', 'paid_headers', 'paid_skills', 'shared_code_dirs', 'door', 'baseline'}


def check() -> int:
    """validate .restructure/config.json for the guard: exit 0 OK, 1 problems (printed)"""
    p = HOME / '.restructure' / 'config.json'
    try:
        raw = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print('config.json cannot be read: %s: %s' % (type(e).__name__, e)); return 1
    bad = ['unknown key %r (a typo? the guard ignores it)' % k for k in raw if k not in KNOWN_KEYS]
    for d in raw.get('paid_commands', []):
        name = (d.get('module') or d.get('script') or '') if isinstance(d, dict) else ''
        if not name: bad.append('paid_commands entry %r has no module or script' % (d,))
        if 'example' in name or 'example' in str(d.get('flag', '')): bad.append('placeholder %r: replace it with the real command' % name)
    for h in raw.get('paid_hosts', []):
        if 'example' in h: bad.append('placeholder host %r' % h)
    door = raw.get('door') or {}
    if door.get('pattern') and re.compile(door['pattern']).groups < 1: bad.append('door.pattern needs a group: the unit folder')
    if not raw.get('paid_commands') and not raw.get('paid_hosts'): bad.append('no paid_commands or paid_hosts: confirm with the owner that nothing costs money or is irreversible')
    for b in bad: print(b)
    print('guard config: OK' if not bad else '%d problem(s)' % len(bad))
    return 1 if bad else 0


def main() -> int:
    if sys.argv[1:] == ['--check']: return check()
    tool, path = '-', '-'
    if BROKEN:
        log('error', tool, path, 'the guard cannot load its rules: %s: %s' % (type(BROKEN).__name__, BROKEN))
        try: tool = json.loads(sys.stdin.read() or '{}').get('tool_name', '-')
        except Exception: tool = '-'
        if tool in ('Bash', 'PowerShell', 'Skill'):        # unguarded paid calls must not pass silently: the owner confirms
            _out(sys.stdout, json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask',
                 'permissionDecisionReason': 'the guard config is broken (.restructure/config.json: %s): paid calls are '
                 'not checked; fix it (python .restructure/write_guard.py --check)' % BROKEN}}) + '\n')
        return 0
    try:
        event = json.loads(sys.stdin.read() or '{}')
        tool = event.get('tool_name', '-')
        status, reason, shown = verdict(event)
        path = ','.join(shown) or '-'
    except Exception as e:                                       # fail open: a broken guard never blocks every write
        log('error', tool, path, '%s: %s' % (type(e).__name__, e)); return 0
    if shown or status != 'allowed': log(status, tool, path, reason)        # a call with no target is not logged
    if status == 'refused':
        _out(sys.stderr, 'REFUSED by .restructure/write_guard.py: %s\n' % reason); return 2
    if status in ('ask', 'deny'):         # a deny holds in every permission mode; bypass mode skips an ask
        _out(sys.stdout, json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': status,
                                                            'permissionDecisionReason': reason}}) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
