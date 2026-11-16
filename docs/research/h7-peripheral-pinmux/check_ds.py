"""Cross-check the pin DB (and the chosen assignments) against DS12110 Table 9 text.

Input: pdftotext -raw text of DS12110 pages 64-88 (Table 9, pin/ball definition).
  1. every GPIO pin: UFBGA176+25 ball in Table 9 == ball in the DB
  2. every (pin, signal) pair of the chosen combinations: signal name appears in that pin's
     "alternate functions" text in Table 9 (membership only; AF numbers are not in Table 9)
Usage: python -I check_ds.py <t9raw.txt> <balls.json> <solutions.json>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403

t9, balls_p, sol_p = sys.argv[1:4]
balls = load(balls_p)
p2b = pin_of(balls)

# --- parse Table 9 into rows: pin -> (ball176, text) ---
lines = open(t9, encoding='utf-8').read().split('\n')
start = re.compile(r'^(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (P[A-K]\d+(?:_C)?)\b')
start2 = re.compile(r'^(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)$')   # name on the next line (PH0-, PH1-)
rows, cur = {}, None
for i, ln in enumerate(lines):
    m = start.match(ln)
    if m:
        cur = m.group(9)
        rows[cur] = {'ball': m.group(5), 'text': ln}
        continue
    m2 = start2.match(ln)                 # pin name on the next line, e.g. "PA13(JTM / S/SWDIO)"
    if m2 and i + 1 < len(lines) and re.match(r'^P[A-K]\d+', lines[i + 1]):
        cur = re.match(r'^(P[A-K]\d+)', lines[i + 1]).group(1)
        rows[cur] = {'ball': m2.group(5), 'text': ln}
        continue
    if re.match(r'^(Table 9|Pin/ball name|DS12110|STM32H742)', ln):
        cur = None
        continue
    if re.match(r'^(\S+ ){7}\S+$', ln) and not re.match(r'^[A-Z]{2,}', ln.split()[0]):
        cur = None            # a row without a plain port name (power pins, PH0/PH1, NRST ...)
        continue
    if cur:
        rows[cur]['text'] += ' ' + ln

gpio = [p for p in p2b if re.match(r'P[A-I]\d+$', p)]
bad = [(p, rows.get(p, {}).get('ball'), p2b[p]) for p in gpio
       if p not in rows or rows[p]['ball'] != p2b[p]]
print(f'Table 9 rows parsed: {len(rows)}; DB GPIO pins: {len(gpio)}')
print('ball mismatches DB vs DS Table 9 (excluding PC14/15, PH0/1 which have split rows):',
      [b for b in bad if b[0] not in ('PC14', 'PC15', 'PH0', 'PH1')])


def alias(sig):
    s = sig
    out = {s}
    if s.startswith('LTDC_'):
        out.add('LCD_' + s[5:])
    if s.startswith('ETH_'):
        out |= {'ETH_RMII_' + s[4:], 'ETH_MII_' + s[4:]}
        if s == 'ETH_REF_CLK':
            out.add('ETH_RMII_REF_CLK')
    if s.startswith('USB_OTG_HS_'):
        out.add(s[4:])                    # the datasheet writes OTG_HS_ULPI_CK
    if s == 'RCC_MCO_1':
        out.add('MCO1')
    if s.startswith('DEBUG_'):
        out.add(s[6:])
    return out


def has(text, sig):
    t = re.sub(r'\s+', '', text)
    for a in alias(sig):
        if re.search(r'(^|[-,/(])' + re.escape(a) + r'(?![A-Za-z0-9_])', t):
            return True
    return False


sol = json.load(open(sol_p))
tot = miss = 0
for name, d in sol.items():
    items = [(r['pin'], r['signal']) for r in d['rows']]
    items += [(v['pin'], k) for k, v in d['sdram'].items()]
    for pin, sg in items:
        tot += 1
        if pin not in rows or not has(rows[pin]['text'], sg):
            miss += 1
            print('  NOT FOUND in Table 9 text:', name, pin, sg)
print(f'(pin, signal) pairs checked: {tot}, not found: {miss}')
