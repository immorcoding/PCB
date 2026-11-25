"""A fab stackup: Tools/KiCadDesignTools/data/stackups/<name>.toml, shared by the boards that name it in board.toml
([board] stackup = "<name>").

    from Tools.KiCadDesignTools.core import stackup
    st = stackup.for_board(cfg)                   # or stackup.load("JLC06161H-3313E")
    st.rows                                       # top to bottom: ("mask", name, t, material, er), ("cu", name, t),
                                                  # ("di", "prepreg" | "core", [(t, material, er), ...])
    st.thickness()                                # board thickness: copper and dielectric, mm (4 decimals)
    st.via_height("F.Cu", "In3.Cu")               # what KiCad adds to a net length for such a via, mm
"""
import os, tomllib

from Tools.KiCadDesignTools.core import paths


class StackupError(ValueError):
    pass


class Stackup:
    def __init__(self, name, rows):
        self.name, self.rows = name, rows

    def thickness(self):
        t = 0.0
        for row in self.rows:
            if row[0] == "cu":
                t += row[2]
            elif row[0] == "di":
                t += sum(s[0] for s in row[2])
        return round(t, 4)

    def via_height(self, a, b):
        """Height KiCad adds to a net's length for a via between copper layers a and b (BOARD_STACKUP::GetLayerDistance):
        everything strictly between, plus the full thickness of an outer end layer and half of an inner end layer."""
        names = [r[1] if r[0] == "cu" else None for r in self.rows]
        i, j = sorted((names.index(a), names.index(b)))
        h = 0.0
        for k in range(i, j + 1):
            r = self.rows[k]
            if r[0] == "di":
                h += sum(s[0] for s in r[2])
            elif r[0] == "cu":
                end = k in (i, j)
                h += r[2] / 2 if end and r[1] not in ("F.Cu", "B.Cu") else r[2]
        return round(h, 4)


def _row(path, d):
    kind = d.get("kind")
    if kind == "mask":
        return ("mask", d["name"], d["thickness"], d["material"], d["epsilon_r"])
    if kind == "cu":
        return ("cu", d["name"], d["thickness"])
    if kind == "di":
        return ("di", d["type"], [tuple(s) for s in d["sublayers"]])
    raise StackupError("%s: unknown row kind %r" % (path, kind))


def load(name):
    path = os.path.join(paths.DATA, "stackups", name + ".toml")
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise StackupError("no stackup %s (%s)" % (name, path))
    return Stackup(name, [_row(path, d) for d in data["rows"]])


def for_board(cfg):
    return load(cfg.need("board.stackup"))
