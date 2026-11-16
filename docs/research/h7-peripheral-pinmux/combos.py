"""Solve the candidate combinations, add auxiliary GPIOs, print pin tables and the occupancy numbers.

Usage: python -I combos.py <balls.json> <out.json> [A|B|C ...]
Debug UART and QSPI pins are chosen per combination by trying every option and keeping the lowest
cost (cost = sum of ring numbers + 2 x half-perimeter of the QSPI bounding box). The result goes to
<out.json> so check_ds.py can verify every (pin, signal) pair against the datasheet text.
"""
import itertools
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from solve import Ctx, PERIPH, UARTS  # noqa: E402

COMBOS = {
    'A': ['LCD565', 'ETH', 'SD1', 'CAN1'],
    'B': ['DCMI8', 'DCMI10X', 'DCMI12X', 'ULPI', 'ETH'],
    'C': ['ETH', 'SD1', 'SD1CTL', 'ULPI', 'CAN1'],
}
# auxiliary GPIOs worth reserving (not counted in the headline numbers)
AUX = {
    'A': {'gpio': ['ETH_NRST', 'ETH_NINT', 'SD_CD', 'SD_PWR_EN', 'CAN_STB', 'LCD_DISP', 'TP_INT'],
          'pwm': ['LCD_BL_PWM'], 'i2c': ['TP_I2C']},
    'B': {'gpio': ['ETH_NRST', 'ETH_NINT', 'USB_RESETB', 'CAM_PWDN', 'CAM_RESET'],
          'pwm': ['CAM_XCLK'], 'i2c': ['CAM_SCCB']},
    'C': {'gpio': ['ETH_NRST', 'ETH_NINT', 'SD_CD', 'SD_PWR_EN', 'USB_RESETB', 'CAN_STB'],
          'pwm': [], 'i2c': []},
}
WEAK = ['PC13', 'PI8']          # powered via the backup switch, 3 MHz / 3 mA: fine for slow control lines
W_QSPI = 2


def cost(sol):
    return sum(ring(b) for _, b, _ in sol.values())


def spread(bs):
    rs = [rc(b)[0] for b in bs]
    cs = [rc(b)[1] for b in bs]
    return (max(rs) - min(rs)) + (max(cs) - min(cs))


def qspi_combos(ctx):
    labs = list(QSPI_OPT)
    for pick in itertools.product(*[QSPI_OPT[l] for l in labs]):
        if len(set(pick)) == len(pick) and not (set(pick) & ctx.reserved):
            yield dict(zip(labs, pick))


def best_for(ctx, periph):
    best = None
    for u in UARTS:
        for q in qspi_combos(ctx):
            if set(q.values()) & {u[1], u[2]}:
                continue
            sol = ctx.solve(periph, u, qspi=q, best=True)
            if not sol:
                continue
            qb = [ctx.p2b[p] for p in q.values()]
            c = (cost(sol) + sum(ring(b) for b in qb) + ring(ctx.p2b[u[1]]) + ring(ctx.p2b[u[2]])
                 + W_QSPI * spread(qb))
            if best is None or c < best[0]:
                best = (c, u, sol, q)
    return best


def free_pins(ctx, used):
    gpio = [p for p in ctx.p2b if re.match(r'P[A-I]\d+$', p) or p in ('PC2_C', 'PC3_C')]
    return [p for p in gpio if p not in used and p not in ctx.reserved]


def assign_aux(ctx, name, used):
    out = {}
    free = [p for p in free_pins(ctx, used) if p not in ('PC2_C', 'PC3_C')]   # _C pins: 1 mA limit
    jtag = ('PA15', 'PB3', 'PB4')                              # JTAG pins at reset: use last
    free.sort(key=lambda p: (p in jtag, p not in WEAK, ring(ctx.p2b[p]), ctx.p2b[p]))
    spec = AUX[name]
    for lab in spec['pwm']:                                   # needs a general-purpose timer channel
        for p in free:
            if any(re.match(r'TIM(3|4|5|12|13|14|15|16|17)_CH\d$', s) for s in ctx.balls[ctx.p2b[p]]['sig']):
                out[lab] = p
                free.remove(p)
                break
    for lab in spec['i2c']:                                   # SCL + SDA of one I2C instance
        for n in (1, 2, 3, 4):
            sc = [c for c in sig_pins(ctx.balls, f'I2C{n}_SCL') if c[0] in free]
            sd = [c for c in sig_pins(ctx.balls, f'I2C{n}_SDA') if c[0] in free]
            if sc and sd:
                s, d = sc[0], sd[0]
                if s[0] != d[0]:
                    out[lab + '_SCL'], out[lab + '_SDA'] = s[0] + f' (I2C{n} AF{s[2]})', d[0] + f' (I2C{n} AF{d[2]})'
                    free.remove(s[0])
                    free.remove(d[0])
                    break
    for lab in spec['gpio']:
        out[lab] = free.pop(0)
    return out


def run(ctx, name):
    periph = COMBOS[name]
    r = best_for(ctx, periph)
    if not r:
        return None
    c, u, sol, q = r
    lab2sig = {lab: sg for n in periph for lab, sg in PERIPH[n]}
    rows = []
    for lab, (p, b, a) in sol.items():
        rows.append(dict(label=lab, signal=lab2sig[lab], pin=p, ball=b, af=a))
    for s, p in q.items():
        a = [x[2] for x in sig_pins(ctx.balls, s) if x[0] == p][0]
        rows.append(dict(label=s, signal=s, pin=p, ball=ctx.p2b[p], af=a))
    for lab, sg, p in ((f'UART.TX', u[3], u[1]), ('UART.RX', u[4], u[2])):
        a = [x[2] for x in sig_pins(ctx.balls, sg) if x[0] == p][0]
        rows.append(dict(label=lab, signal=sg, pin=p, ball=ctx.p2b[p], af=a))
    for rw in rows:
        rw['ring'], rw['edge'] = ring(rw['ball']), edge(rw['ball'])
    used = {rw['pin'] for rw in rows}
    assert len(used) == len(rows) and not (used & ctx.reserved)
    aux = assign_aux(ctx, name, used)
    return dict(name=name, periph=periph, cost=c, uart=u[0], rows=rows, aux=aux,
                sdram={k: dict(pin=v, ball=ctx.p2b[v], ring=ring(ctx.p2b[v]), edge=edge(ctx.p2b[v]))
                       for k, v in ctx.sdram.items()})


def show(ctx, d):
    rows = d['rows']
    print(f'\n=== combo {d["name"]}: {" + ".join(d["periph"])}   cost {d["cost"]}')
    for rw in sorted(rows, key=lambda x: x['label']):
        print(f'  {rw["label"]:16s} {rw["pin"]:5s} {rw["ball"]:4s} ring{rw["ring"]} {rw["edge"]:13s} AF{rw["af"]}')
    n_periph = len([r for r in rows if not r['label'].startswith(('QUADSPI', 'UART'))])
    print('  peripheral signals:', n_periph, ' QSPI 6  UART 2')
    for k, v in d['aux'].items():
        print('  aux', k, v)
    rg = Counter(r['ring'] for r in rows)
    ed = Counter(r['edge'].split('/')[0] for r in rows)
    print('  this set (QSPI+UART+periph): rings', sorted(rg.items()), ' edges', sorted(ed.items()))
    allb = [(v['ring'], v['edge']) for v in d['sdram'].values()] + \
           [(r['ring'], r['edge']) for r in rows] + \
           [(ring(ctx.p2b[p]), edge(ctx.p2b[p])) for p in list(SWD.values()) + list(HSE.values()) + list(LSE.values())]
    print('  everything used (SDRAM+set+SWD/HSE/LSE): rings', sorted(Counter(a for a, _ in allb).items()),
          ' edges', sorted(Counter(b.split('/')[0] for _, b in allb).items()))
    gp = [p for p in ctx.p2b if re.match(r'P[A-I]\d+$', p) or p in ('PC2_C', 'PC3_C')]
    print('  capacity (all 140 GPIO balls): rings', sorted(Counter(ring(ctx.p2b[p]) for p in gp).items()),
          ' edges', sorted(Counter(edge(ctx.p2b[p]).split('/')[0] for p in gp).items()))
    print('  SDRAM alone: rings', sorted(Counter(v['ring'] for v in d['sdram'].values()).items()),
          ' edges', sorted(Counter(v['edge'].split('/')[0] for v in d['sdram'].values()).items()))
    nsd = len(d['sdram'])
    io = nsd + len(rows) + 6              # + SWD 2, HSE 2, LSE 2
    print(f'  IO used = SDRAM {nsd} + QSPI/UART/periph {len(rows)} + SWD/HSE/LSE 6 = {io}  ({io / 140:.1%} of 140);'
          f' with aux {io + len(d["aux"])} ({(io + len(d["aux"])) / 140:.1%})')
    sig = io + 3
    print(f'  balls: signal balls {sig}/201 = {sig / 201:.1%};  with all 58 power/ground balls {sig + 58}/201 = {(sig + 58) / 201:.1%}')


if __name__ == '__main__':
    ctx = Ctx(load(sys.argv[1]))
    out = {}
    for k in (sys.argv[3:] or COMBOS):
        d = run(ctx, k)
        out[k] = d
        show(ctx, d)
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
