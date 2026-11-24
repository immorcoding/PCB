"""A board's SPEC.md table "本板取值" against its rule profile and its data files (PROC-8).

    python -m Tools.KiCadDesignTools.project.spec_check <board dir> [--profile <profile .md>]

Runs with any Python >= 3.11 (no pcbnew). The driver's layout step runs it first and stops on exit 1.

1. Every item of the profile's table "布局和走线的取值" (docs/rule-profiles/<[board] profile>-*.md, or --profile) has a
   row in SPEC.md's table "本板取值" (columns 项目, 本板取值, 数据源; first table after the heading that names it) whose
   value is filled: a value, or 不适用. An item may be split into rows "<item>：<part>" (one per class, per length
   group); each of them must be filled. Items in PARTS must have exactly those parts. Empty means: nothing, "-", "—",
   "待定", "?", "TBD".
2. One source: where a value also lives in a data file the tools read, the row's 数据源 cell names it (several are
   separated by "；"), and the SPEC value must agree with each of them. Which side is the source of an item is written
   in templates/C-bga-065/README.md; spec_check only reports that the two disagree. References:
     board.toml:<key.key>             any board TOML / JSON file of the board folder (place.toml, length_groups.json ...);
     length_groups.json:groups[rule=sdram_addr_window].hi     a list element by a key's value, or [n]
     routes_sdram.py:TUNING.pitch.default                      a module of the board folder: attribute, then keys
     kicad_dru:sdram_lane0.skew.max                            the board's rule file: rule, constraint, min/max/opt (mm)
     copper.sketch:gap,  copper.sketch:L1_GND.minwidth         the copper sketch: a parameter, a region's setting (mm)
   Agreement: a number must appear among the numbers of the value cell (sign ignored: lo -20 / hi 20 against "±20");
   a list of layer roles must equal the cell's slash list (信号 / 地 / 电源 / 混合) and its signal-layer count appear in
   the cell; a text must be part of the cell. A data file that does not exist yet is noted, not a failure (a board's
   SPEC is written before its routes); a missing key in an existing file is a failure.

Exit 1 when an item is missing or empty, a reference cannot be read or a value disagrees; 0 otherwise; 2 on a usage
or board.toml error. [board] spec_table = false (a SPEC written before the table existed): the failures are printed
as warnings and the exit is 0. A folder without board.toml (the SPEC template) needs --profile; only step 1 runs.
"""
import glob, importlib, importlib.util, json, os, re, sys, tomllib

from Tools.KiCadDesignTools.core import config, paths

PROFILES = os.path.join(paths.REPO, "docs", "rule-profiles")
PROFILE_HEADING = "布局和走线的取值"
SPEC_HEADING = "本板取值"
NA = "不适用"
EMPTY = {"", "-", "—", "–", "待定", "?", "？", "TBD", "tbd"}
SEP = re.compile(r"[：:]")
# items whose rows must be exactly these parts (the coordinator's list of 2026-11-24: which nets get a via-count cap,
# and the cap)
PARTS = {"过孔数上限": ("哪些线", "个数")}
ROLE_ZH = {"signal": "信号", "ground": "地", "power": "电源", "mixed": "混合"}
ZH_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


class RefError(Exception):
    pass


class NotYet(Exception):
    pass


# ---------------------------------------------------------------------------------------------------- markdown tables
def table_after(text, heading):
    """Rows (lists of cells) of the first Markdown table after the first heading line that contains `heading`;
    None when there is no such heading or table."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.lstrip().startswith("#") and heading in l), None)
    if start is None:
        return None
    rows, seen = [], False
    for l in lines[start + 1:]:
        s = l.strip()
        if s.startswith("|"):
            seen = True
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", s.strip("|"))]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            rows.append(cells)
        elif seen:
            break
        elif s.startswith("#"):
            return None
    return rows or None


def plain(cell):
    return re.sub(r"[`*]", "", cell).strip()


def profile_items(path):
    rows = table_after(open(path, encoding="utf-8").read(), PROFILE_HEADING)
    if not rows:
        raise RefError("%s: no table under a heading %s" % (path, PROFILE_HEADING))
    return [plain(r[0]) for r in rows[1:] if r and plain(r[0])]


def profile_file(cfg):
    p = cfg.get("board.profile")
    if not p:
        raise config.ConfigError("%s: [board] profile is missing" % cfg.toml)
    hits = sorted(glob.glob(os.path.join(PROFILES, "%s-*.md" % p)))
    if len(hits) != 1:
        raise config.ConfigError("profile %s: %d files %s-*.md in docs/rule-profiles" % (p, len(hits), p))
    return hits[0]


def spec_rows(path):
    """{row name: (value, [references])} of SPEC.md's table, in order; None when the table is missing."""
    rows = table_after(open(path, encoding="utf-8").read(), SPEC_HEADING)
    if not rows:
        return None
    head = [plain(c) for c in rows[0]]
    try:
        ci = next(i for i, h in enumerate(head) if h == "项目")
        cv = next(i for i, h in enumerate(head) if "取值" in h)
    except StopIteration:
        raise RefError("%s: the table %s needs the columns 项目 and 本板取值 (has %s)" % (path, SPEC_HEADING, " | ".join(head)))
    cs = next((i for i, h in enumerate(head) if h == "数据源"), None)
    out = {}
    for r in rows[1:]:
        get = lambda i: r[i] if i is not None and i < len(r) else ""
        name = plain(get(ci))
        if not name:
            continue
        refs = [plain(x) for x in re.split(r"；|;|<br\s*/?>", get(cs))]
        out[name] = (get(cv).strip(), [x for x in refs if x and x not in EMPTY and x != "无"])
    return out


# ---------------------------------------------------------------------------------------------------- data references
def walk(value, path, ref):
    for tok in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path):
        if tok.startswith("["):
            sel = tok[1:-1]
            if not isinstance(value, list):
                raise RefError("%s: %s is not a list" % (ref, tok))
            if "=" in sel:
                k, v = sel.split("=", 1)
                hit = [e for e in value if isinstance(e, dict) and str(e.get(k)) == v]
                if not hit:
                    raise RefError("%s: no element with %s" % (ref, sel))
                value = hit[0]
            else:
                try:
                    value = value[int(sel)]
                except (ValueError, IndexError):
                    raise RefError("%s: no element %s" % (ref, tok))
        else:
            if isinstance(value, dict) and tok in value:
                value = value[tok]
            elif not isinstance(value, dict) and hasattr(value, tok):
                value = getattr(value, tok)
            else:
                raise RefError("%s: no key %s" % (ref, tok))
    return value


def board_module(cfg, file):
    stem = os.path.splitext(file)[0]
    try:
        cfg.package
    except (config.ConfigError, ValueError):       # a board outside the repository (the benchmark's copies)
        spec = importlib.util.spec_from_file_location("spec_check_board_%s" % stem, cfg.path(file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return cfg.module(stem)


def dru_value(text, ref, path):
    m = re.fullmatch(r"([^.]+)\.(\w+)\.(min|max|opt)", path)
    if not m:
        raise RefError("%s: expected kicad_dru:<rule>.<constraint>.<min|max|opt>" % ref)
    rule, cons, bound = m.groups()
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    bodies = [b.group(1) for b in re.finditer(r'\(rule\s+"%s"(.*?)(?=\n\(rule\s|\Z)' % re.escape(rule), text, re.S)]
    if not bodies:
        raise RefError("%s: no rule %s" % (ref, rule))
    c = re.search(r"\(constraint\s+%s\b([^\n]*)" % re.escape(cons), bodies[-1])          # the last one wins in KiCad
    if not c:
        raise RefError("%s: rule %s has no constraint %s" % (ref, rule, cons))
    v = re.search(r"\(%s\s+(-?[\d.]+)\s*(mm|mil)?\)" % bound, c.group(1))
    if not v:
        raise RefError("%s: constraint %s of rule %s has no %s" % (ref, cons, rule, bound))
    x = float(v.group(1))
    return round(x * 0.0254, 6) if v.group(2) == "mil" else x


def sketch_value(cfg, file, ref, path):
    from Tools.KiCadDesignTools.copper import cu_sketch
    sk = cu_sketch.parse(open(cfg.path(file), encoding="utf-8").read(), layers=len(cfg.layers))
    name, _, key = path.partition(".")
    if not key:
        if name not in sk.p:
            raise RefError("%s: no sketch parameter %s (%s)" % (ref, name, ", ".join(sk.p)))
        return sk.p[name] / 1e6
    r = next((r for r in sk.regions if r.name == name), None)
    if r is None:
        raise RefError("%s: no region %s" % (ref, name))
    if key not in ("clearance", "minwidth"):
        raise RefError("%s: a region's clearance or minwidth" % ref)
    return r.get(sk, key) / 1e6


def resolve(cfg, ref):
    """The value a reference points at. NotYet when its file does not exist."""
    file, sep, path = ref.partition(":")
    if not sep or not path:
        raise RefError("%s: expected <file>:<path>" % ref)
    if file == "kicad_dru":
        if not os.path.isfile(cfg.dru):
            raise NotYet(os.path.basename(cfg.dru))
        return dru_value(open(cfg.dru, encoding="utf-8").read(), ref, path)
    full = cfg.path(file)
    if not os.path.isfile(full):
        raise NotYet(file)
    if file.endswith(".kicad_dru"):
        return dru_value(open(full, encoding="utf-8").read(), ref, path)
    if file.endswith(".toml"):
        with open(full, "rb") as f:
            return walk(tomllib.load(f), path, ref)
    if file.endswith(".json"):
        return walk(json.load(open(full, encoding="utf-8")), path, ref)
    if file.endswith(".py"):
        return walk(board_module(cfg, file), path, ref)
    if file.endswith(".sketch"):
        return sketch_value(cfg, file, ref, path)
    raise RefError("%s: no reader for %s" % (ref, file))


# ---------------------------------------------------------------------------------------------------- agreement
def numbers(cell):
    nums = [abs(float(x)) for x in re.findall(r"\d+(?:\.\d+)?", cell)]
    nums += [float(ZH_NUM[c]) for c in re.findall(r"([一二两三四五六七八九十])\s*个", cell)]
    return nums


def agrees(value, cell):
    """-> (True/False, what the data says)"""
    if isinstance(value, bool) or value is None:
        raise RefError("a %s cannot be compared" % type(value).__name__)
    if isinstance(value, (int, float)):
        return any(abs(abs(value) - n) < 1e-6 for n in numbers(cell)), "%g" % value
    if isinstance(value, str):
        return value in cell, value
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, str) and v in ROLE_ZH for v in value):
        want = [ROLE_ZH[v] for v in value]
        seq = re.search(r"(信号|地|电源|混合)(?:\s*/\s*(?:信号|地|电源|混合))+", cell)
        got = re.findall(r"信号|地|电源|混合", seq.group(0)) if seq else []
        n = sum(1 for v in value if v in ("signal", "mixed"))
        return got == want and float(n) in numbers(cell), "%d 个信号层：%s" % (n, " / ".join(want))
    if isinstance(value, (list, tuple)):
        res = [agrees(v, cell) for v in value]
        return all(r[0] for r in res), ", ".join(r[1] for r in res)
    raise RefError("a %s cannot be compared" % type(value).__name__)


# ---------------------------------------------------------------------------------------------------- the check
def check(spec_path, items, cfg=None):
    """-> (lines, failures) for a SPEC.md against the profile's items; cfg None: completeness only."""
    lines, fails = [], []
    rows = spec_rows(spec_path)
    if rows is None:
        fails.append("SPEC.md 没有“%s”表" % SPEC_HEADING)
        for it in items:
            fails.append("缺：%s" % it)
        return lines, fails
    used = set()
    for it in items:
        mine = [(n, v) for n, v in rows.items() if n == it or (n.startswith(it) and SEP.match(n[len(it):len(it) + 1] or "x"))]
        used.update(n for n, _ in mine)
        if not mine:
            fails.append("缺：%s（表里没有这一行）" % it)
            continue
        if it in PARTS:
            parts = [SEP.split(n, 1)[1].strip() if n != it else "" for n, _ in mine]
            if sorted(parts) != sorted(PARTS[it]):
                fails.append("缺：%s 要分成 %s 几行（现在是 %s）" % (it, "、".join("%s：%s" % (it, p) for p in PARTS[it]),
                                                                   "、".join(n for n, _ in mine)))
        for n, (val, refs) in mine:
            if plain(val) in EMPTY:
                fails.append("空：%s（既没有值也没写“%s”）" % (n, NA))
                continue
            lines.append("      %s：%s" % (n, plain(val)))
            if cfg is None:
                continue
            if refs and plain(val).startswith(NA):
                fails.append("矛盾：%s 写的是“%s”，却有数据源 %s" % (n, NA, "；".join(refs)))
                continue
            for ref in refs:
                try:
                    v = resolve(cfg, ref)
                    ok, said = agrees(v, plain(val))
                except NotYet as e:
                    lines.append("        数据源 %s：%s 还没有，没比" % (ref, e))
                    continue
                except RefError as e:
                    fails.append("读不了：%s 的数据源 %s" % (n, e))
                    continue
                if ok:
                    lines.append("        数据源 %s = %s，一致" % (ref, said))
                else:
                    fails.append("不一致：%s 写“%s”，数据源 %s 是 %s" % (n, plain(val), ref, said))
    extra = [n for n in rows if n not in used]
    if extra:
        lines.append("（表里另有 %d 行，规格档没有这几项，不查：%s）" % (len(extra), "、".join(extra)))
    return lines, fails


def shown(path):
    """A path relative to the repository when it is inside it."""
    try:
        rel = os.path.relpath(path, paths.REPO)
    except ValueError:                             # another drive
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


def main(argv):
    args =[a for a in argv if not a.startswith("--")]
    prof = None
    if "--profile" in argv:
        i = argv.index("--profile")
        if i + 1 >= len(argv):
            print(__doc__)
            return 2
        prof = argv[i + 1]
        args = [a for a in args if a != prof]
    if len(args) != 1:
        print(__doc__)
        return 2
    d = args[0] if os.path.isabs(args[0]) or os.path.exists(args[0]) else os.path.join(paths.REPO, args[0])
    d = os.path.dirname(d) if os.path.isfile(d) else d
    cfg = None
    if os.path.isfile(os.path.join(d, "board.toml")):
        try:
            cfg = config.load(d)
            prof = prof or profile_file(cfg)
        except config.ConfigError as e:
            print("board.toml: %s" % e)
            return 2
    elif not prof:
        print("%s has no board.toml: give the profile with --profile <docs/rule-profiles/X-....md>" % d)
        return 2
    spec = os.path.join(d, "SPEC.md")
    if not os.path.isfile(spec):
        print("no SPEC.md in %s" % d)
        return 2
    try:
        items = profile_items(prof)
        lines, fails = check(spec, items, cfg)
    except RefError as e:
        print(e)
        return 2
    strict = cfg is None or cfg.get("board.spec_table", True)
    name = cfg.name if cfg else os.path.basename(os.path.normpath(d))
    print("spec_check %s：规格档 %s 的“%s”%d 项，对 SPEC.md 的“%s”表%s" % (
        name, shown(prof), PROFILE_HEADING, len(items), SPEC_HEADING,
        "和数据文件" if cfg else "（没有 board.toml：只查齐不齐）"))
    for l in lines:
        print(l)
    tag = "FAIL  " if strict else "warn  "
    for f in fails:
        print(tag + f)
    if not fails:
        print("结论：齐全%s" % ("，和数据文件一致" if cfg else ""))
        return 0
    if strict:
        print("结论：%d 处不合格（exit 1）" % len(fails))
        return 1
    print("结论：%d 处不合格，只警告（board.toml [board] spec_table = false：这块板的 SPEC 早于这张表）" % len(fails))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
