"""Pin-conflict solver for the H743IIK6 test board.

Assigns every signal of the chosen peripherals (plus QSPI and a debug UART) to one pin from the
CubeMX pin DB so that no pin is used twice and none of the SDRAM / SWD / HSE / LSE pins is taken.
Backtracking in candidate order: the first solution found is the "most preferred" one.

Usage: python -I solve.py <balls.json> --explore     feasibility of every peripheral subset
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403


def sigs(prefix, names):
    return [(f'{prefix}.{n}', f'{prefix}_{n}') for n in names]


PERIPH = {
    'ETH': [('ETH.REF_CLK', 'ETH_REF_CLK'), ('ETH.CRS_DV', 'ETH_CRS_DV'), ('ETH.RXD0', 'ETH_RXD0'),
            ('ETH.RXD1', 'ETH_RXD1'), ('ETH.TX_EN', 'ETH_TX_EN'), ('ETH.TXD0', 'ETH_TXD0'),
            ('ETH.TXD1', 'ETH_TXD1'), ('ETH.MDC', 'ETH_MDC'), ('ETH.MDIO', 'ETH_MDIO')],
    'SD1': sigs('SDMMC1', ['CK', 'CMD', 'D0', 'D1', 'D2', 'D3']),
    'SD1CTL': sigs('SDMMC1', ['CKIN', 'CDIR', 'D0DIR', 'D123DIR']),
    'SD2': sigs('SDMMC2', ['CK', 'CMD', 'D0', 'D1', 'D2', 'D3']),
    'SD2X': sigs('SDMMC2', ['D4', 'D5', 'D6', 'D7']),            # added to SD2: 8-bit eMMC
    'ULPI': [('ULPI.CK', 'USB_OTG_HS_ULPI_CK')] +
            [(f'ULPI.D{i}', f'USB_OTG_HS_ULPI_D{i}') for i in range(8)] +
            [('ULPI.DIR', 'USB_OTG_HS_ULPI_DIR'), ('ULPI.NXT', 'USB_OTG_HS_ULPI_NXT'),
             ('ULPI.STP', 'USB_OTG_HS_ULPI_STP')],
    'LCD565': sigs('LTDC', ['R3', 'R4', 'R5', 'R6', 'R7', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7',
                            'B3', 'B4', 'B5', 'B6', 'B7', 'CLK', 'DE', 'HSYNC', 'VSYNC']),
    'LCD888X': sigs('LTDC', ['R0', 'R1', 'R2', 'G0', 'G1', 'B0', 'B1', 'B2']),   # added to LCD565
    'DCMI8': sigs('DCMI', ['D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'HSYNC', 'VSYNC', 'PIXCLK']),
    'DCMI10X': sigs('DCMI', ['D8', 'D9']),
    'DCMI12X': sigs('DCMI', ['D10', 'D11']),
    'SAI1': [('SAI1.MCLK_A', 'SAI1_MCLK_A'), ('SAI1.FS_A', 'SAI1_FS_A'), ('SAI1.SCK_A', 'SAI1_SCK_A'),
             ('SAI1.SD_A', 'SAI1_SD_A'), ('SAI1.SD_B', 'SAI1_SD_B')],
    # SRAM on the NOR/PSRAM side of the FMC, sharing D0-D15, A0-A12, A14/A15 (= BA0/BA1) and NBL0/1
    # with the SDRAM: only the signals the SDRAM does not use are new
    'SRAM': [('SRAM.A13', 'FMC_A13'), ('SRAM.A16', 'FMC_A16'), ('SRAM.A17', 'FMC_A17'),
             ('SRAM.A18', 'FMC_A18'), ('SRAM.A19', 'FMC_A19'), ('SRAM.NOE', 'FMC_NOE'),
             ('SRAM.NWE', 'FMC_NWE'), ('SRAM.NE3', 'FMC_NE3')],
    'CAN1': [('FDCAN1.TX', 'FDCAN1_TX'), ('FDCAN1.RX', 'FDCAN1_RX')],
    'CAN2': [('FDCAN2.TX', 'FDCAN2_TX'), ('FDCAN2.RX', 'FDCAN2_RX')],
}
QSPI = [(k, k) for k in QSPI_OPT]
# forced choices: ETH_TXD1 on PG12 as on the ST H743I-EVAL (UM2198 Table 68); PG14 would also work
RESTRICT = {'ETH.TXD1': ['PG12']}
# debug UART options (TX pin, RX pin), tried in this order
UARTS = [('USART1', 'PA9', 'PA10', 'USART1_TX', 'USART1_RX'),
         ('USART3', 'PB10', 'PB11', 'USART3_TX', 'USART3_RX'),
         ('USART6', 'PC6', 'PC7', 'USART6_TX', 'USART6_RX'),
         ('USART2', 'PA2', 'PA3', 'USART2_TX', 'USART2_RX'),
         ('UART4', 'PB9', 'PB8', 'UART4_TX', 'UART4_RX'),
         ('UART4', 'PC10', 'PC11', 'UART4_TX', 'UART4_RX'),
         ('USART1', 'PB14', 'PB15', 'USART1_TX', 'USART1_RX'),
         ('USART1', 'PB6', 'PB7', 'USART1_TX', 'USART1_RX'),
         ('UART5', 'PC12', 'PD2', 'UART5_TX', 'UART5_RX'),
         ('UART7', 'PF7', 'PF6', 'UART7_TX', 'UART7_RX')]


class Ctx:
    def __init__(self, balls):
        self.balls = balls
        self.p2b = pin_of(balls)
        self.sdram = {s: sig_pins(balls, s)[0][0] for s in SDRAM_SIGS}
        self.sdram.update(SDRAM_CHOICE)
        self.reserved = set(self.sdram.values()) | set(SWD.values()) | set(HSE.values()) | set(LSE.values())

    def cand(self, sig, blocked, only=None):
        return [(p, b, a) for p, b, a in sig_pins(self.balls, sig)
                if p not in blocked and (only is None or p in only)]

    def solve(self, periph, uart=None, qspi=None, extra_blocked=(), best=False):
        """periph: list of PERIPH keys. uart: tuple from UARTS (its two pins are reserved).
        qspi: None = let the solver pick from QSPI_OPT, or dict signal->pin (reserved).
        best: minimise the sum of ring numbers instead of returning the first solution."""
        blocked = set(self.reserved) | set(extra_blocked)
        if uart:
            blocked |= {uart[1], uart[2]}
        cl = {}
        for n in periph:
            for lab, sg in PERIPH[n]:
                cl[lab] = self.cand(sg, blocked, only=RESTRICT.get(lab))
        if qspi is None:
            for s, opts in QSPI_OPT.items():
                cl[s] = self.cand(s, blocked, only=opts)
        else:
            blocked |= set(qspi.values())
            for lab in list(cl):                          # re-filter against the fixed QSPI pins
                cl[lab] = [c for c in cl[lab] if c[0] not in qspi.values()]
        if any(not c for c in cl.values()):
            return None
        labs = sorted(cl, key=lambda l: len(cl[l]))
        res, used = {}, set()
        if not best:
            def bt(i):
                if i == len(labs):
                    return True
                for p, b, a in cl[labs[i]]:
                    if p in used:
                        continue
                    used.add(p)
                    res[labs[i]] = (p, b, a)
                    if bt(i + 1):
                        return True
                    used.discard(p)
                    del res[labs[i]]
                return False
            return res if bt(0) else None

        # branch and bound: minimise the sum of ring numbers (outer ring = 0 = top-layer escape)
        for l in cl:
            cl[l].sort(key=lambda c: (ring(c[1]), c[1]))
        floor = [min(ring(c[1]) for c in cl[l]) for l in labs]
        suffix = [sum(floor[i:]) for i in range(len(labs) + 1)]
        top = {'cost': 10 ** 9, 'sol': None}

        def bb(i, cost):
            if cost + suffix[i] >= top['cost']:
                return
            if i == len(labs):
                top['cost'], top['sol'] = cost, dict(res)
                return
            for p, b, a in cl[labs[i]]:
                if p in used:
                    continue
                used.add(p)
                res[labs[i]] = (p, b, a)
                bb(i + 1, cost + ring(b))
                used.discard(p)
                del res[labs[i]]

        bb(0, 0)
        return top['sol']


if __name__ == '__main__':
    ctx = Ctx(load(sys.argv[1]))
    if sys.argv[2] == '--try':                      # e.g. --try ETH,ULPI,DCMI8,DCMI10X
        sub = sys.argv[3].split(',')
        for u in UARTS:
            if ctx.solve(sub, u):
                print('OK', sum(len(PERIPH[x]) for x in sub), u[:3])
                break
        else:
            print('FAIL')
        sys.exit()
    pool = ['ETH', 'SD1', 'SD1CTL', 'SD2', 'ULPI', 'LCD565', 'DCMI8', 'SAI1', 'CAN1', 'CAN2']
    print('N = peripheral signals (QSPI 6 and debug UART 2 come on top)')
    for r in range(1, len(pool) + 1):
        for sub in itertools.combinations(pool, r):
            if 'SD1CTL' in sub and 'SD1' not in sub:
                continue
            if 'SD1' in sub and 'SD2' in sub:
                continue
            n = sum(len(PERIPH[x]) for x in sub)
            if n < 13:
                continue
            ok = None
            for u in UARTS:
                if ctx.solve(list(sub), u):
                    ok = u
                    break
            print('OK  ' if ok else 'FAIL', f'N={n:2d}', ' + '.join(sub), ok[:3] if ok else '')
