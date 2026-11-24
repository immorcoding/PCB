"""Pictures of the silkscreen over the copper (stop 8, qualitative review only, PROC-14).

    D:\\KiCad\\bin\\python.exe stm32h743_sdram\\finish_view.py <board> <out dir>

KiCad draws them (kicad-cli pcb export svg: copper, solder mask, silkscreen with the mask subtracted as the fab will
print it, board edge; KiCad's colours), Edge (headless) turns the SVG into a PNG. Writes silk_top.png, silk_bottom.png
(the bottom seen from below, mirrored) and close-ups of the top cut from a finer picture: the title block, the
north-east connectors, the DC input, the LCD / UART edge, the codec / MCU north area and the west side.
"""
import os, subprocess, sys
from PIL import Image

CLI = r"D:\KiCad\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W_MM, H_MM = 85.0, 75.0
CLOSE = {"title": (3.5, 32.0, 27.5, 41.0), "northeast": (61.0, 0.0, 85.0, 30.0), "dc_input": (56.0, 46.0, 85.0, 62.0),
         "lcd_uart": (24.0, 59.0, 70.0, 75.0), "codec_mcu_north": (20.0, 12.0, 50.0, 33.0), "west": (0.0, 0.0, 26.0, 42.0)}


def shot(svg, png, px_per_mm, mirror=False):
    w, h = int(W_MM * px_per_mm), int(H_MM * px_per_mm)
    html = os.path.splitext(png)[0] + ".html"
    open(html, "w", encoding="utf-8").write(
        '<html><body style="margin:0;background:#0c2412"><img src="%s" style="width:%dpx;height:%dpx"></body></html>'
        % (os.path.basename(svg), w, h))
    url = "file:///" + os.path.abspath(html).replace("\\", "/")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=%d,%d" % (w, h),
                    "--screenshot=" + os.path.abspath(png), url], capture_output=True)
    os.remove(html)
    return png


def svg(board, out, side):
    layers = "F.Cu,F.Mask,F.SilkS,Edge.Cuts" if side == "F" else "B.Cu,B.Mask,B.SilkS,Edge.Cuts"
    path = os.path.join(out, "silk_%s.svg" % ("top" if side == "F" else "bottom"))
    args = [CLI, "pcb", "export", "svg", "--layers", layers, "--mode-single", "--page-size-mode", "2", "--exclude-drawing-sheet",
            "--subtract-soldermask", "-o", path, board]
    if side == "B":
        args.insert(-1, "--mirror")
    subprocess.run(args, capture_output=True)
    return path


def main(board, out):
    os.makedirs(out, exist_ok=True)
    top = svg(board, out, "F")
    print(shot(top, os.path.join(out, "silk_top.png"), 24))
    print(shot(svg(board, out, "B"), os.path.join(out, "silk_bottom.png"), 24))
    fine = shot(top, os.path.join(out, "silk_top_fine.png"), 48)
    im = Image.open(fine)
    for name, (x0, y0, x1, y1) in CLOSE.items():
        p = os.path.join(out, "silk_top_%s.png" % name)
        im.crop((int(x0 * 48), int(y0 * 48), int(x1 * 48), int(y1 * 48))).save(p)
        print(p)
    im.close()
    os.remove(fine)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
