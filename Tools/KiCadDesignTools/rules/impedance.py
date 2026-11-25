"""Trace impedance on the JLCPCB six-layer stackup JLC06161H-3313E (2D field solver).

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.impedance z0   --layer L1 --width 0.156
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.impedance z0   --layer L4 --target 50
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.impedance diff --layer L1 --width 0.11 --gap 0.10
    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.rules.impedance diff --layer L1 --target 100 --gap 0.15
    options: --copper MM  --mask intl|domestic|none  --tol PCT  --res MM  --box MM

Method: quasi-TEM. Solve div(eps grad phi) = 0 on the cross-section with a
finite-volume 5-point scheme on a graded tensor grid (fine at the trace corners),
trace at 1 V, reference planes and the outer box at 0 V. The linear system is
eliminated directly (block-tridiagonal, numpy only, no scipy).
C is taken from the field energy, once with the dielectrics and once with
everything replaced by air:  Z0 = eta0 / sqrt(C * C_air), C in units of eps0.
Differential: half the cross-section with the symmetry plane at 0 V (odd mode),
Zdiff = 2 * Zodd. Single-ended and even mode use a Neumann symmetry plane.

Assumptions (all lengths in mm):
- Lossless, zero frequency dispersion; Er values are the fab's back-fitted ones.
- Width is the trace BOTTOM width; the top is narrower by `etch` (trapezoid,
  staircased on the grid). Gap is edge to edge at the bottom.
- Outer layers: solder mask = a flat coat on the laminate plus a conformal coat
  over the trace (top and sides). Inner layers: no mask, the trace sits on the
  dielectric below it and is embedded in the one above it.
- Reference planes are solid and infinite; the box walls are far enough not to
  matter (see Tools/KiCadDesignTools/tests/impedance/check.py for the benchmark).
Results are CALCULATED values. The fab's own calculator is the authority; widths
used on a board are confirmed there by the user (RUL-3).
"""
import argparse
import math
import os
import sys

# The solve is hundreds of small dense inversions. Multithreaded OpenBLAS makes
# those 100-1000x slower on this machine (0.1 s becomes minutes), so BLAS is held
# to one thread: by environment variable if numpy is not loaded yet, and around
# each solve through the OpenBLAS library numpy ships (see _one_blas_thread).
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np

MIL = 0.0254
ETA0 = 376.730313668

# ---------------------------------------------------------------------------
# Stackup table. Source: JLCPCB stackup page for JLC06161H-3313E and the
# impedance-calculator parameter page, as recorded in
# docs/research/jlc-6layer-capability.md (branch research/jlc-6layer-capability),
# sections 5 and 6. Prepreg thickness is after lamination.
#   below / above: dielectric layers (thickness, Er) from the trace outwards to
#                  the reference plane. above=None means solder mask and air.
#   t:    copper thickness. The calculator page gives 1 oz = 1.6 mil outer and
#         0.5 oz = 0.6 mil inner; the stackup table prints 0.035 / 0.0152.
#   etch: bottom width minus top width; None = the figure in the MASKS set below.
#         The calculator page quotes one figure without naming layers, so it is
#         applied to inner layers too. A rectangular L4 trace (etch=0) reads
#         about 2 % lower (50 ohm width 0.121 instead of 0.127 mm).
# ---------------------------------------------------------------------------
_OUTER = dict(below=[(0.0994, 4.1)], above=None, t=1.6 * MIL, etch=None)
STACKUP = {
    "L1": _OUTER,                                   # microstrip over L2, 3313 prepreg
    "L6": _OUTER,                                   # microstrip over L5, same build
    # Inner layers: L3 and L4 are both signal layers since 2026-11-23 (layer order signal / GND / signal / signal /
    # power / signal); each is a stripline between its near plane (L2 for L3, L5 for L4, 0.1 mm core) and the other
    # inner signal layer 1.12 mm away, taken as a plane as the fab's calculator does. The stackup is symmetric, so
    # the two give the same numbers (SPEC 6: 50 ohm 0.135 mm on L3 and L4 from the user's run of that calculator).
    "L4": dict(below=[(0.1, 4.6)],                  # 0.1 mm core down to L5
               above=[(0.2104, 4.4), (0.7, 4.6), (0.2104, 4.4)],   # 7628 / core / 7628 up to L3
               t=0.6 * MIL, etch=None),
    "L3": dict(below=[(0.1, 4.6)],                  # 0.1 mm core up to L2
               above=[(0.2104, 4.4), (0.7, 4.6), (0.2104, 4.4)],   # 7628 / core / 7628 down to L4
               t=0.6 * MIL, etch=None),
}
# Fab parameter sets, one per site: solder mask thickness on laminate and on
# copper, mask Er, and the etch taper (bottom width minus top width).
MASKS = {
    "intl":     dict(base=1.2 * MIL, coat=0.6 * MIL, er=3.8, etch=0.7 * MIL),   # jlcpcb.com
    "domestic": dict(base=1.0 * MIL, coat=1.0 * MIL, er=3.8, etch=0.5 * MIL),   # jlc.com
    "none":     dict(base=0.0, coat=0.0, er=1.0, etch=0.7 * MIL),
}

RES = 0.00075    # finest cell size at the trace corners
GROW = 0.08      # cell size grows by this fraction of the distance to a corner
BOX = 3.0        # clear distance from the trace to the side wall / air lid


# --------------------------------------------------------------------------- grid
def _find_openblas():
    """(get, set) thread-count functions of numpy's bundled OpenBLAS, or None."""
    try:
        import ctypes, glob
        libs = os.path.join(os.path.dirname(os.path.dirname(np.__file__)), "numpy.libs")
        for path in glob.glob(os.path.join(libs, "*openblas*")):
            lib = ctypes.CDLL(path)
            for prefix, suffix in (("scipy_", "64_"), ("scipy_", ""), ("", "64_"), ("", "")):
                try:
                    return (getattr(lib, prefix + "openblas_get_num_threads" + suffix),
                            getattr(lib, prefix + "openblas_set_num_threads" + suffix))
                except AttributeError:
                    pass
    except Exception:
        pass
    return None


_OPENBLAS = _find_openblas()


class _one_blas_thread:
    """Context: one BLAS thread inside, the caller's setting restored after."""
    def __enter__(self):
        self.n = None
        if _OPENBLAS:
            self.n = _OPENBLAS[0]()
            _OPENBLAS[1](1)

    def __exit__(self, *exc):
        if self.n:
            _OPENBLAS[1](self.n)


def _mesh(breaks, corners, res, hmax):
    """Graded 1D mesh through every breakpoint, cell size res at `corners`."""
    breaks = sorted(set(round(b, 9) for b in breaks))
    corners = np.array(sorted(corners))
    t = np.geomspace(1e-6, 0.5, 120)
    t = np.concatenate(([0.0], t, 1 - t[-2::-1], [1.0]))
    out = [breaks[0]]
    for a, b in zip(breaks[:-1], breaks[1:]):
        p = a + (b - a) * t
        size = np.minimum(hmax, res + GROW * np.abs(p[:, None] - corners[None, :]).min(axis=1))
        n_cum = np.concatenate(([0.0], np.cumsum(np.diff(p) * 0.5 * (1 / size[1:] + 1 / size[:-1]))))
        n = max(1, math.ceil(n_cum[-1] - 1e-9))
        out.extend(np.interp(np.linspace(0, n_cum[-1], n + 1)[1:], n_cum, p))
        out[-1] = b
    return np.array(out)


def _energy(g_x, g_y, fixed, value):
    """Field energy of the 5-point system = capacitance per length in units of eps0.

    g_x[i,j] links nodes (i,j)-(i+1,j), g_y[i,j] links (i,j)-(i,j+1). With the nodes
    split into fixed (f) and free (u):  E = v'K_ff v - r' K_uu^-1 r,  r = -K_uf v.
    The second term comes from a block-tridiagonal elimination along the first
    axis (one dense block per grid column), so no potential map is stored.
    """
    nx, ny = fixed.shape
    free = ~fixed
    diag = np.zeros((nx, ny))
    rhs = np.zeros((nx, ny))
    diag[:-1] += g_x; diag[1:] += g_x; diag[:, :-1] += g_y; diag[:, 1:] += g_y
    rhs[:-1] += g_x * value[1:]; rhs[1:] += g_x * value[:-1]      # value is 0 at free nodes
    rhs[:, :-1] += g_y * value[:, 1:]; rhs[:, 1:] += g_y * value[:, :-1]
    diag[fixed] = 1.0
    rhs[fixed] = 0.0
    bx = g_x * (free[:-1] & free[1:])
    by = g_y * (free[:, :-1] & free[:, 1:])
    energy = (g_x * np.diff(value, axis=0) ** 2).sum() + (g_y * np.diff(value, axis=1) ** 2).sum()

    idx = np.arange(ny)
    inv = r = None
    for i in range(nx):
        s = np.zeros((ny, ny))
        s[idx, idx] = diag[i]
        s[idx[:-1], idx[1:]] = -by[i]
        s[idx[1:], idx[:-1]] = -by[i]
        r_i = rhs[i]
        if i:
            b = bx[i - 1]
            s -= b[:, None] * inv * b[None, :]
            r_i = r_i + b * (inv @ r)
        inv = np.linalg.inv(s)
        inv[np.abs(inv) < 1e-100] = 0.0          # far couplings decay into denormals, which are very slow
        r = np.where(np.abs(r_i) < 1e-100, 0.0, r_i)
        energy -= r @ (inv @ r)
    return float(energy)


def _capacitance(x, y, eps, fixed, value):
    """Capacitance per length of the 1 V trace, in units of eps0."""
    dx, dy = np.diff(x), np.diff(y)
    ex = np.zeros((len(x) - 1, len(y)))          # eps * dy summed over the two cells beside an x-link
    ex[:, :-1] += eps * dy[None, :] / 2
    ex[:, 1:] += eps * dy[None, :] / 2
    ey = np.zeros((len(x), len(y) - 1))
    ey[:-1] += eps * dx[:, None] / 2
    ey[1:] += eps * dx[:, None] / 2
    g_x, g_y = ex / dx[:, None], ey / dy[None, :]
    with _one_blas_thread():
        if len(x) < len(y):                      # keep the dense blocks small
            return _energy(g_y.T, g_x.T, fixed.T, value.T)
        return _energy(g_x, g_y, fixed, value)


# --------------------------------------------------------------------------- geometry
def _params(layer, copper, mask, etch):
    st = STACKUP[layer]
    mk = MASKS[mask]
    t = st["t"] if copper is None else copper
    if etch is None:
        etch = st["etch"] if st["etch"] is not None else mk["etch"]
    if st["above"] is not None:                 # inner layer: no mask
        mk = MASKS["none"]
    return st, mk, t, etch


def _mode_z(layer, width, gap, mode, copper, mask, etch, res, box):
    """Impedance of one trace. gap None: single-ended. mode 'odd' / 'even' for a pair."""
    st, mk, t, etch = _params(layer, copper, mask, etch)
    if width - etch <= 0:
        raise ValueError("width %.4f mm is not wider than the etch taper %.4f mm" % (width, etch))
    x_in = 0.0 if gap is None else gap / 2      # inner bottom edge of the trace (half-domain x >= 0)
    x_c = x_in + width / 2 if gap is not None else 0.0
    x_out = x_c + width / 2
    x_max = x_out + box
    y_b = sum(h for h, _ in st["below"])        # trace bottom
    y_t = y_b + t
    coat, base = mk["coat"], mk["base"]
    if st["above"] is None:
        y_max = y_t + box
        above = []
    else:
        above = st["above"]
        y_max = y_t + sum(h for h, _ in above)

    xs = [0.0, x_out, x_out - etch / 2, x_out + coat, x_max]
    x_corners = [x_out, x_out - etch / 2]
    if gap is not None:
        xs += [x_in, x_in + etch / 2, max(0.0, x_in - coat)]
        x_corners += [x_in, x_in + etch / 2]
    ys = [0.0, y_b, y_t, y_b + base, y_t + coat, y_max]
    acc = 0.0
    for h, _ in st["below"]:
        acc += h; ys.append(acc)
    acc = y_t
    for h, _ in above:
        acc += h; ys.append(acc)
    x = _mesh(xs, x_corners, res, box / 12)
    y = _mesh(ys, [y_b, y_t], res, box / 12)

    def half_width(yy):                         # trapezoid half width at height yy
        return width / 2 - etch / 2 * np.clip((yy - y_b) / t, 0, 1)

    tiny = 1e-9
    X, Y = np.meshgrid(x, y, indexing="ij")
    trace = (Y >= y_b - tiny) & (Y <= y_t + tiny) & (np.abs(X - x_c) <= half_width(Y) + tiny)
    fixed = trace.copy()
    value = trace.astype(float)
    fixed[:, 0] = fixed[:, -1] = fixed[-1, :] = True
    if mode == "odd":
        fixed[0, :] = True

    xc_, yc_ = np.meshgrid((x[:-1] + x[1:]) / 2, (y[:-1] + y[1:]) / 2, indexing="ij")
    eps = np.ones_like(xc_)
    acc = 0.0
    for h, er in st["below"]:
        eps[(yc_ > acc) & (yc_ < acc + h)] = er
        acc += h
    if above:
        eps[(yc_ > y_b) & (yc_ < y_t)] = above[0][1]        # trace is embedded in the first layer
        acc = y_t
        for h, er in above:
            eps[(yc_ > acc) & (yc_ < acc + h)] = er
            acc += h
    elif coat or base:
        m = (yc_ > y_b) & (yc_ < y_b + base)
        m |= (yc_ > y_b) & (yc_ < y_t + coat) & (np.abs(xc_ - x_c) < half_width(yc_) + coat)
        eps[m] = mk["er"]

    c = _capacitance(x, y, eps, fixed, value)
    c_air = _capacitance(x, y, np.ones_like(eps), fixed, value)
    if gap is None:                             # half of a symmetric single trace
        c, c_air = 2 * c, 2 * c_air
    return ETA0 / math.sqrt(c * c_air), c / c_air


# --------------------------------------------------------------------------- public API
def z0(layer, width, copper=None, mask="intl", etch=None, res=RES, box=BOX):
    """Single-ended characteristic impedance in ohms. width = bottom width, mm."""
    return _mode_z(layer, width, None, "even", copper, mask, etch, res, box)[0]


def zdiff(layer, width, gap, copper=None, mask="intl", etch=None, res=RES, box=BOX):
    """Differential impedance (2 * Zodd) in ohms. gap = edge to edge at the bottom, mm."""
    return 2 * _mode_z(layer, width, gap, "odd", copper, mask, etch, res, box)[0]


def pair(layer, width, gap, copper=None, mask="intl", etch=None, res=RES, box=BOX):
    """Dict with zodd, zeven, zdiff, zcomm (ohms) and eeff_odd, eeff_even for a coupled pair."""
    zo, eo = _mode_z(layer, width, gap, "odd", copper, mask, etch, res, box)
    ze, ee = _mode_z(layer, width, gap, "even", copper, mask, etch, res, box)
    return dict(zodd=zo, zeven=ze, zdiff=2 * zo, zcomm=ze / 2, eeff_odd=eo, eeff_even=ee)


def eeff(layer, width, copper=None, mask="intl", etch=None, res=RES, box=BOX):
    """Effective permittivity of a single-ended trace (delay = sqrt(eeff) / c)."""
    return _mode_z(layer, width, None, "even", copper, mask, etch, res, box)[1]


def _solve_width(f, target, lo=0.03, hi=2.0, xtol=1e-5):
    """Width where f(width) = target. f falls smoothly as width grows: secant in log(width)."""
    x0, x1 = math.log(0.12), math.log(0.18)
    f0, f1 = f(math.exp(x0)) - target, f(math.exp(x1)) - target
    for _ in range(30):
        if f1 == f0:
            break
        x2 = min(math.log(hi), max(math.log(lo), x1 - f1 * (x1 - x0) / (f1 - f0)))
        if abs(math.exp(x2) - math.exp(x1)) < xtol and abs(f1) < 0.01 * target:
            return math.exp(x2)
        if x2 == x1:                            # stuck on a limit
            break
        x0, f0, x1 = x1, f1, x2
        f1 = f(math.exp(x1)) - target
    raise ValueError("no width between %.2f and %.2f mm gives %.1f ohm (last try: %.4f mm -> %.1f ohm)"
                     % (lo, hi, target, math.exp(x1), f1 + target))


def width_for_z0(layer, target, **kw):
    """Bottom width (mm) giving the target single-ended impedance."""
    return _solve_width(lambda w: z0(layer, w, **kw), target)


def width_for_zdiff(layer, target, gap, **kw):
    """Bottom width (mm) of each trace giving the target differential impedance at this gap."""
    return _solve_width(lambda w: zdiff(layer, w, gap, **kw), target)


def hammerstad_jensen(w, h, er, t=0.0):
    """Closed-form microstrip Z0 (Hammerstad and Jensen 1980, with their thickness correction)."""
    def z01(u):
        f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
        return ETA0 / (2 * math.pi) * math.log(f / u + math.sqrt(1 + 4 / u ** 2))

    def e_eff(u):
        a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
        b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
        return (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)

    u = w / h
    u1 = ur = u
    if t > 0:
        tn = t / h
        du1 = tn / math.pi * math.log(1 + 4 * math.e / (tn / math.tanh(math.sqrt(6.517 * u)) ** 2))
        u1 = u + du1
        ur = u + du1 * (1 + 1 / math.cosh(math.sqrt(er - 1))) / 2
    ee = e_eff(ur) * (z01(u1) / z01(ur)) ** 2
    return z01(ur) / math.sqrt(e_eff(ur)), ee


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Trace impedance on JLC06161H-3313E (calculated, confirm on the fab calculator).")
    ap.add_argument("what", choices=["z0", "diff"])
    ap.add_argument("--layer", required=True, choices=sorted(STACKUP))
    ap.add_argument("--width", type=float, help="bottom width, mm")
    ap.add_argument("--gap", type=float, help="edge-to-edge gap, mm (diff)")
    ap.add_argument("--target", type=float, help="solve for the width giving this impedance, ohm")
    ap.add_argument("--copper", type=float, help="copper thickness, mm (default from the stackup table)")
    ap.add_argument("--mask", default="intl", choices=sorted(MASKS), help="fab parameter set: mask thicknesses and etch taper")
    ap.add_argument("--tol", type=float, help="also print the impedance at width -/+ this percent")
    ap.add_argument("--res", type=float, default=RES, help="finest grid cell, mm")
    ap.add_argument("--box", type=float, default=BOX, help="distance to the side wall and air lid, mm")
    a = ap.parse_args(argv)
    kw = dict(copper=a.copper, mask=a.mask, res=a.res, box=a.box)
    if a.what == "diff" and a.gap is None:
        ap.error("diff needs --gap")
    if (a.width is None) == (a.target is None):
        ap.error("give exactly one of --width and --target")
    f = (lambda w: z0(a.layer, w, **kw)) if a.what == "z0" else (lambda w: zdiff(a.layer, w, a.gap, **kw))
    w = a.width
    try:
        if a.target is not None:
            w = _solve_width(f, a.target)
        z = f(w)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    name = "Z0" if a.what == "z0" else "Zdiff"
    gap = "" if a.what == "z0" else "  gap %.4f mm" % a.gap
    print("%s  width %.4f mm%s  %s %.2f ohm" % (a.layer, w, gap, name, z))
    if a.what == "diff":
        p = pair(a.layer, w, a.gap, **kw)
        print("    Zodd %.2f  Zeven %.2f  Zcommon %.2f ohm  eeff odd %.3f even %.3f"
              % (p["zodd"], p["zeven"], p["zcomm"], p["eeff_odd"], p["eeff_even"]))
    if a.tol:
        for sign in (-1, 1):
            ww = w * (1 + sign * a.tol / 100)
            print("    width %+.0f%% = %.4f mm  %s %.2f ohm" % (sign * a.tol, ww, name, f(ww)))
    print("    calculated value; confirm on the fab's impedance calculator before use")
    return 0


if __name__ == "__main__":
    sys.exit(main())
