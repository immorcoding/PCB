"""PROTOTYPE debug: where does a block's copper stay joined to its board edge? Sampled at half-pitch steps.
    python dbg.py <variant index> <net> [half width]
'#' copper joined to the edge, '+' copper not joined, ' ' no copper; own vias 'O', foreign vias 'x' (at sites)."""
import sys
import numpy as np
from scipy import ndimage
from matplotlib.path import Path as MPath
import draw as D
import model as M

v = D.VARIANTS[int(sys.argv[1])]
net = sys.argv[2]
h = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
blocks = {n: D.inset(D.resolve(verts)) for n, layer, verts in v["regions"]}
vias, _ = D.place_vias(blocks)
verts = [r for r in v["regions"] if r[0] == net][0][2]
ext = D.inset(D.resolve(verts, D.EXT), D.EXT)
G = D.G
x0, y0, x1, y1 = -11.0, -11.0, 18.0, 18.0
nx, ny = int((x1 - x0) / G), int((y1 - y0) / G)
X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) * G, y0 + (np.arange(ny) + 0.5) * G)
mask = MPath(ext).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(ny, nx)
site = {}
for x, y, hole, pad, vnet, what in vias:
    if not (x0 < x < x1 and y0 < y < y1):
        continue
    site[(round(y / D.P), round(x / D.P))] = "O" if vnet == net else "x"
    if vnet == net:
        continue
    r = hole / 2 + M.HOLE_CU
    mask &= ~((X - x) ** 2 + (Y - y) ** 2 <= r * r)
d = ndimage.distance_transform_edt(mask) * G
lab, _ = ndimage.label(d >= h)
src = set(np.unique(lab[((X > D.BX1) | (Y > D.BY1)) & (d >= h)])) - {0}
joined = np.isin(lab, list(src))
lo, hi = -16, 17
print("     " + "".join(f"{j:2d}" if j % 2 == 0 else "  " for j in range(lo, hi)))
for i2 in range(lo * 2, hi * 2 + 1):
    row = ""
    for j2 in range(lo * 2, hi * 2 + 1):
        y, x = i2 * D.P / 2, j2 * D.P / 2
        if i2 % 2 == 0 and j2 % 2 == 0 and (i2 // 2, j2 // 2) in site:
            row += site[(i2 // 2, j2 // 2)]
            continue
        ii, jj = int((y - y0) / G), int((x - x0) / G)
        if not (0 <= ii < ny and 0 <= jj < nx):
            row += " "
            continue
        w = slice(max(0, ii - 3), ii + 4), slice(max(0, jj - 3), jj + 4)
        row += "#" if joined[w].any() else ("+" if (d[w] >= h).any() else " ")
    print(f"{i2 / 2:5.1f}" + row)
