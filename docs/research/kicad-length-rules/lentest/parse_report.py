"""Parse a kicad-cli DRC text report into one record per violation block.

The report is localised (the detail text is Chinese on this machine), so we key on the
error code in [brackets], the `Rule:` line and the numbers, not on the wording.

    from parse_report import blocks
    for b in blocks(text): b.code, b.rule, b.numbers, b.nets, b.items
"""
import re
from collections import namedtuple

Block = namedtuple("Block", "code detail rule severity items nets numbers")


def blocks(text):
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^\[(\w+)\]: (.*)$", line)
        if m:
            if cur:
                out.append(cur)
            detail = m.group(2)
            nums = re.findall(r"(-?\d+(?:\.\d+)?) mm", detail)
            cur = {"code": m.group(1), "detail": detail, "rule": "", "severity": "", "items": [],
                   "nets": [], "numbers": [float(x) for x in nums]}
            continue
        if cur is None:
            continue
        m = re.match(r"^\s+Rule: (.*?); (\w+)\s*$", line)
        if m:
            cur["rule"], cur["severity"] = m.group(1), m.group(2)
            continue
        if line.startswith("    @"):
            cur["items"].append(line.strip())
            m = re.search(r"\[(/[^\]]*|[^\]]*)\]", line)
            if m:
                cur["nets"].append(m.group(1))
    if cur:
        out.append(cur)
    return [Block(**b) for b in out]


def net_of(b):
    """the single net a length block refers to (items come from one net)"""
    s = sorted(set(b.nets))
    return s[0] if len(s) == 1 else ",".join(s)
