"""PROTOTYPE (issue 47, throwaway): cross-section of one DDR3 byte lane on an outer layer.

Run: python xsection.py
Prints, per variant, the copper objects across the bundle and the total width.
All numbers in mm. Rules: docs/rule-profiles/if-ddr3.md (edge-to-edge multiples of w).
"""
W = 0.15            # 50 ohm outer-layer width (issue 46)
DW, DG = 0.104, 0.15  # 100 ohm outer-layer pair: width, gap
S_SS = 2 * W        # DQ-DQ inside a G-S-S-G cell
S_GS = 1 * W        # guard to signal
S_DQS = 3 * W       # DQ/DM to DQS when nothing is between them
VIA_CLR = 0.15      # DDR line to foreign via pad outside the rule areas (issue 48)


def lane(guard_w, pattern, gs=S_GS):
    """pattern: string of G (guard), S (single-ended line), D (DQS pair).
    Returns (objects, width). Gap between neighbours picked from the rules."""
    objs, x, prev = [], 0.0, None
    for c in pattern:
        if prev is not None:
            pair = prev + c
            if "G" in pair:
                gap = gs
            elif "D" in pair:
                gap = S_DQS
            else:
                gap = S_SS
            x += gap
        if c == "G":
            wid = guard_w
        elif c == "S":
            wid = W
        else:
            wid = 2 * DW + DG
        objs.append((c, round(x, 4), wid))
        x += wid
        prev = c
    return objs, round(x, 4)


VARIANTS = {
    # name: (guard width, pattern, note)
    "V0 no guard (spacing rules only)": (0, "SSSSSSSSSD", "baseline, not allowed by RTE-17"),
    "V1 guard 0.40, via 0.4/0.2 inline": (0.40, "GSSGSSGDGSSGSSGSG", "guard = via pad; straight lines"),
    "V2 guard 0.30, via 0.30/0.15 inline": (0.30, "GSSGSSGDGSSGSSGSG", "min pour width; small via costs extra"),
    "V3 guard 0.15 track, vias only where bundle opens": (0.15, "GSSGSSGDGSSGSSGSG", "needs via stations every <=5.08"),
}

if __name__ == "__main__":
    for name, (g, pat, note) in VARIANTS.items():
        objs, width = lane(g, pat)
        n_g = pat.count("G")
        print(f"{name}: width {width:.2f} mm, guards {n_g}  ({note})")
    # gap needed between two signals for an inline via of pad d: d + 2*VIA_CLR
    for d in (0.40, 0.30):
        print(f"inline via pad {d}: signals must be {d + 2 * VIA_CLR:.2f} apart; guard copper {d + 2 * VIA_CLR - 2 * S_GS:.2f}")
