"""Edits of a .kicad_pcb file as TEXT (no pcbnew): only the lines named change, every other byte stays.

    layer_rows(rows)          the copper rows of a board's layer table, rows = [(id, name, type, user name or None)]
    sync_layers(path, rows)   bring the copper rows of an existing board's layer table to rows

The board-file text helpers of copper_report.py (unfill, strip, orphans) join this module in a later batch of the
Tools/ consolidation.
"""
import re


def layer_rows(rows):
    return "".join('\t\t(%d "%s" %s%s)\n' % (i, n, t, ' "%s"' % u if u else "") for i, n, t, u in rows)


def sync_layers(path, rows):
    """Bring the copper rows of an existing board's layer table to rows (type and user name); the stackup and
    every object stay. Text edit, nothing else in the file changes. True when it wrote."""
    s = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in s[:2000] else "\n"
    pat = "".join(r'\t\t\(%d "%s" (?:signal|power|mixed|jumper)(?: "[^"]*")?\)\r?\n' % (i, re.escape(n)) for i, n, _, _ in rows)
    m = re.search(pat, s)
    assert m, "copper rows of the layer table not found in %s" % path
    new = layer_rows(rows).replace("\n", eol)
    if m.group(0) == new:
        return False
    open(path, "w", encoding="utf-8", newline="").write(s[:m.start()] + new + s[m.end():])
    return True
