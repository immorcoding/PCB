"""Shared helpers: load balls.json, ring/edge of a ball, SDRAM / QSPI / required pin sets."""
import json
import re

ROWS = 'ABCDEFGHJKLMNPR'          # 15 rows, I/O/Q skipped, A at the top of the top view


def load(path):
    return json.load(open(path))


def pin_of(balls):
    """pin name (PA0...) -> ball"""
    return {d['pin'].split(' ')[0].split('-')[0]: b for b, d in balls.items()}


def rc(ball):
    m = re.match(r'([A-R])(\d+)$', ball)
    return ROWS.index(m.group(1)), int(m.group(2)) - 1


def ring(ball):
    r, c = rc(ball)
    return min(r, c, 14 - r, 14 - c)


def edge(ball):
    """which edge of the top view the ball is closest to (top = row A, left = column 1)"""
    r, c = rc(ball)
    d = {'top': r, 'bottom': 14 - r, 'left': c, 'right': 14 - c}
    m = min(d.values())
    e = [k for k, v in d.items() if v == m]
    return '/'.join(e)


def sig_pins(balls, sig):
    """signal name -> list of (pin, ball, AF)"""
    out = []
    for b, d in balls.items():
        if sig in d['sig']:
            out.append((d['pin'].split(' ')[0].split('-')[0], b, d['sig'][sig]))
    return sorted(out)


# ---- fixed parts ------------------------------------------------------------
SDRAM_SIGS = (['FMC_D%d' % i for i in range(32)] + ['FMC_A%d' % i for i in range(13)] +
              ['FMC_BA0', 'FMC_BA1', 'FMC_NBL0', 'FMC_NBL1', 'FMC_NBL2', 'FMC_NBL3',
               'FMC_SDCLK', 'FMC_SDNCAS', 'FMC_SDNRAS'])
# pins with a choice: pinned by ticket #7 / this ticket
SDRAM_CHOICE = {'FMC_SDCKE0': 'PH2', 'FMC_SDNE0': 'PH3', 'FMC_SDNWE': 'PH5'}

# QUADSPI Bank1, DS12110 Table 9/10, listed in ticket #7
QSPI_OPT = {
    'QUADSPI_CLK': ['PF10', 'PB2'],
    'QUADSPI_BK1_NCS': ['PG6', 'PB6', 'PB10'],
    'QUADSPI_BK1_IO0': ['PF8', 'PD11', 'PC9'],
    'QUADSPI_BK1_IO1': ['PF9', 'PD12', 'PC10'],
    'QUADSPI_BK1_IO2': ['PF7', 'PE2'],
    'QUADSPI_BK1_IO3': ['PF6', 'PD13', 'PA1'],
}

# mandatory pins
SWD = {'DEBUG_JTMS-SWDIO': 'PA13', 'DEBUG_JTCK-SWCLK': 'PA14'}
HSE = {'RCC_OSC_IN': 'PH0', 'RCC_OSC_OUT': 'PH1'}
LSE = {'RCC_OSC32_IN': 'PC14', 'RCC_OSC32_OUT': 'PC15'}
