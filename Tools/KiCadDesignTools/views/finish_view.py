"""Pictures of the silkscreen over the copper (finishing stop 8, qualitative review only, PROC-14).

    python -m Tools.KiCadDesignTools.views.finish_view <board dir> <board> <out dir>

KiCad draws them (kicad-cli pcb export svg: copper, solder mask, silkscreen with the mask subtracted as the fab will
print it, board edge; KiCad's colours), Edge (headless) turns the SVG into a PNG. Writes silk_top.png, silk_bottom.png
(the bottom seen from below, mirrored) and close-ups of the top cut from a finer picture: silk_top_<name>.png for each
box of board.toml [finish.view] close ({name: [x0, y0, x1, y1]}, local mm). The page is the board extent of
place.toml [outline].
"""
import os, sys
from PIL import Image

from Tools.KiCadDesignTools.core import config, heavy, paths

CLI = paths.KICAD_CLI
EDGE = paths.EDGE


def shot(svg, png, px_per_mm, W_MM, H_MM):
    w, h = int(W_MM * px_per_mm), int(H_MM * px_per_mm)
    html = os.path.splitext(png)[0] + ".html"
    open(html, "w", encoding="utf-8").write(
        '<html><body style="margin:0;background:#0c2412"><img src="%s" style="width:%dpx;height:%dpx"></body></html>'
        % (os.path.basename(svg), w, h))
    url = "file:///" + os.path.abspath(html).replace("\\", "/")
    heavy.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=%d,%d" % (w, h),
               "--screenshot=" + os.path.abspath(png), url], check=True, ok=None, outputs=[png])     # Edge: the PNG decides
    os.remove(html)
    return png


def svg(board, out, side):
    layers = "F.Cu,F.Mask,F.SilkS,Edge.Cuts" if side == "F" else "B.Cu,B.Mask,B.SilkS,Edge.Cuts"
    path = os.path.join(out, "silk_%s.svg" % ("top" if side == "F" else "bottom"))
    args = [CLI, "pcb", "export", "svg", "--layers", layers, "--mode-single", "--page-size-mode", "2", "--exclude-drawing-sheet",
            "--subtract-soldermask", "-o", path, board]
    if side == "B":
        args.insert(-1, "--mirror")
    heavy.run(args, check=True, outputs=[path])
    return path


def main(cfg, board, out):
    outline = cfg.datafile("place.toml")["outline"]
    W_MM, H_MM = outline["width"], outline["height"]
    close = cfg.need("finish.view.close")
    os.makedirs(out, exist_ok=True)
    top = svg(board, out, "F")
    print(shot(top, os.path.join(out, "silk_top.png"), 24, W_MM, H_MM))
    print(shot(svg(board, out, "B"), os.path.join(out, "silk_bottom.png"), 24, W_MM, H_MM))
    fine = shot(top, os.path.join(out, "silk_top_fine.png"), 48, W_MM, H_MM)
    im = Image.open(fine)
    for name, (x0, y0, x1, y1) in close.items():
        p = os.path.join(out, "silk_top_%s.png" % name)
        im.crop((int(x0 * 48), int(y0 * 48), int(x1 * 48), int(y1 * 48))).save(p)
        print(p)
    im.close()
    os.remove(fine)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(config.load(sys.argv[1]), sys.argv[2], sys.argv[3])
