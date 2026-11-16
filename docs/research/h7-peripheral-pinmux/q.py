"""Query balls.json: python -I q.py <balls.json> <regex over signal names>
Prints, for each matching signal, the pins/balls/AF that can carry it."""
import json
import re
import sys

balls = json.load(open(sys.argv[1]))
pat = re.compile(sys.argv[2])
res = {}
for b, d in balls.items():
    for s, a in d['sig'].items():
        if pat.search(s):
            res.setdefault(s, []).append((d['pin'].split(' ')[0], b, a))
for s in sorted(res):
    print(s.ljust(22), '  '.join(f'{p}:{b}:AF{a}' for p, b, a in sorted(res[s])))
