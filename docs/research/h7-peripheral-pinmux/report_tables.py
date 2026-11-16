"""Print markdown pin tables from solutions.json (one table per peripheral per set).
Usage: python -I report_tables.py <solutions.json> [A|B|C ...]"""
import json
import re
import sys

sol = json.load(open(sys.argv[1]))
ED = {'top': '上', 'bottom': '下', 'left': '左', 'right': '右'}


def ed(e):
    return '/'.join(ED[x] for x in e.split('/'))


def natkey(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


def group(label):
    return label.split('.')[0] if '.' in label else ('QUADSPI' if label.startswith('QUADSPI') else label)


def show(d):
    groups = {}
    for r in d['rows']:
        groups.setdefault(group(r['label']), []).append(r)
    for g in sorted(groups):
        rows = groups[g]
        print(f'\n**{g}**（{len(rows)} 脚）\n')
        print('| 信号 | 端口 | 球 | 圈 | 边 | AF |')
        print('|---|---|---|---|---|---|')
        for r in sorted(rows, key=lambda x: natkey(x['label'])):
            print(f"| {r['signal']} | {r['pin']} | {r['ball']} | {r['ring']} | {ed(r['edge'])} | {r['af']} |")
    print('\n辅助脚（示例）：', '；'.join(f'{k}={v}' for k, v in d['aux'].items()))


if __name__ == '__main__':
    for k in (sys.argv[2:] or sol):
        print(f"\n\n#### 套 {k}：{' + '.join(sol[k]['periph'])}")
        show(sol[k])
    # SDRAM (same in all sets)
    d = sol[next(iter(sol))]['sdram']
    print('\n\n#### SDRAM 57 脚\n')
    print('| 信号组 | 端口:球(圈) |')
    print('|---|---|')
    grp = [('D0–D7', [f'FMC_D{i}' for i in range(0, 8)]), ('D8–D15', [f'FMC_D{i}' for i in range(8, 16)]),
           ('D16–D23', [f'FMC_D{i}' for i in range(16, 24)]), ('D24–D31', [f'FMC_D{i}' for i in range(24, 32)]),
           ('A0–A6', [f'FMC_A{i}' for i in range(0, 7)]), ('A7–A12', [f'FMC_A{i}' for i in range(7, 13)]),
           ('BA0/BA1 NBL0–3', ['FMC_BA0', 'FMC_BA1', 'FMC_NBL0', 'FMC_NBL1', 'FMC_NBL2', 'FMC_NBL3']),
           ('SDCLK SDNCAS SDNRAS SDNWE SDCKE0 SDNE0',
            ['FMC_SDCLK', 'FMC_SDNCAS', 'FMC_SDNRAS', 'FMC_SDNWE', 'FMC_SDCKE0', 'FMC_SDNE0'])]
    for name, sigs in grp:
        print(f'| {name} | ' + '　'.join(f"{s.replace('FMC_', '')}={d[s]['pin']}:{d[s]['ball']}({d[s]['ring']})" for s in sigs) + ' |')
    assert sum(len(s) for _, s in grp) == len(d) == 57
