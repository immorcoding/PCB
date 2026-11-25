"""A board's configuration: <board dir>/board.toml, read with tomllib and checked.

    from Tools.KiCadDesignTools.core import config
    cfg = config.load("stm32h743_sdram")        # a folder (relative to the repository or absolute) or a board.toml
    cfg.name, cfg.dir, cfg.pcb, cfg.pro, cfg.dru  # stem and the three KiCad files
    cfg.layers                                    # [Layer(L="L1", kicad="F.Cu", id=0, role="signal", user=None), ...]
    cfg.kicad("L5") -> "In4.Cu";  cfg.L("In4.Cu") -> "L5";  cfg.signal_layers() -> ["L1", "L3", "L4", "L6"]
    cfg.groups                                    # [[route.group]] in build order (dicts)
    cfg.get("layout.edges", {})                   # any value by dotted path
    cfg.rules()                                   # the rule values of the board's .kicad_pro / .kicad_dru (busroute Profile)
    cfg.copper_sketch(), cfg.copper_plane()       # the copper sketch; its plane clearance and minimum width (mm)
    python -m Tools.KiCadDesignTools.core.config <board dir>       # print the checked configuration

Layer roles: signal, ground, power, mixed (a ground or power layer is a plane layer: busroute refuses tracks on it,
docs/tools.md). L1 is F.Cu and Ln is B.Cu; the inner layers are In1.Cu .. In(n-2).Cu top to bottom; KiCad's layer
ids are 0 for F.Cu, 2 for B.Cu and 2 + 2k for Ink.Cu. Every board.toml key is described in Tools/KiCadDesignTools/README.md.
"""
import os, sys, tomllib
from dataclasses import dataclass

from Tools.KiCadDesignTools.core import paths

ROLES = {"signal", "ground", "power", "mixed"}
KICAD_TYPE = {"signal": "signal", "ground": "power", "power": "power", "mixed": "mixed"}


class ConfigError(ValueError):
    pass


@dataclass
class Layer:
    L: str
    kicad: str
    id: int
    role: str
    user: str | None

    @property
    def plane(self):
        return self.role in ("ground", "power")

    @property
    def kicad_type(self):
        return KICAD_TYPE[self.role]


class Board:
    def __init__(self, path):
        if os.path.isdir(path):
            path = os.path.join(path, "board.toml")
        if not os.path.isabs(path) and not os.path.exists(path):
            path = os.path.join(paths.REPO, path)
        self.toml = os.path.abspath(path)
        self.dir = os.path.dirname(self.toml)
        try:
            with open(self.toml, "rb") as f:
                self.data = tomllib.load(f)
        except FileNotFoundError:
            raise ConfigError("no board.toml in %s" % self.dir)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError("%s: %s" % (self.toml, e))
        self._check()

    # ------------------------------------------------------------------ access
    def get(self, dotted, default=None):
        d = self.data
        for k in dotted.split("."):
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        return d

    def need(self, dotted):
        v = self.get(dotted)
        if v is None:
            raise ConfigError("%s: %s is missing" % (self.toml, dotted))
        return v

    @property
    def name(self):
        return self.data["board"]["name"]

    def file(self, ext):
        return os.path.join(self.dir, self.name + ext)

    @property
    def pcb(self):
        return self.file(".kicad_pcb")

    @property
    def pro(self):
        return self.file(".kicad_pro")

    @property
    def dru(self):
        return self.file(".kicad_dru")

    @property
    def origin(self):
        return tuple(self.data["board"].get("origin", (0.0, 0.0)))

    def path(self, rel):
        """A path written in board.toml, relative to the board folder."""
        return rel if os.path.isabs(rel) else os.path.join(self.dir, rel)

    def kicad(self, L):
        return self._byL[L].kicad

    def L(self, kicad):
        return self._byK[kicad].L

    def signal_layers(self):
        return [l.L for l in self.layers if l.role in ("signal", "mixed")]

    def plane_layers(self):
        return [l.L for l in self.layers if l.plane]

    @property
    def groups(self):
        return list(self.get("route.group", []))

    def datafile(self, name):
        """Another TOML data file of the board folder (place.toml, silk.toml, bga_block.toml), read once; {} when the
        file does not exist."""
        cache = self.__dict__.setdefault("_data", {})
        if name not in cache:
            p = os.path.join(self.dir, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    try:
                        cache[name] = tomllib.load(f)
                    except tomllib.TOMLDecodeError as e:
                        raise ConfigError("%s: %s" % (p, e))
            else:
                cache[name] = {}
        return cache[name]

    @property
    def package(self):
        """The board folder as a Python package name, relative to the repository root ("stm32h743_sdram",
        "templates.demo_board"): routes files, rules_cases.py and schematic pages are imported as its modules."""
        rel = os.path.relpath(self.dir, paths.REPO)
        if rel.startswith(".."):
            raise ConfigError("%s is not inside the repository %s" % (self.dir, paths.REPO))
        return rel.replace(os.sep, ".").replace("/", ".")

    def module(self, name):
        """Import a Python data module of the board folder (e.g. "rules_cases", "routes_sdram", "sch.mcu")."""
        import importlib
        return importlib.import_module(self.package + "." + name)

    def rules(self):
        """The rule values of the board's .kicad_pro (floors, net classes) and .kicad_dru (rule-area widths,
        clearances and vias, plated holes, limits) as a routing.busroute.profile.Profile, read once: the one source
        of the rule profile's numbers for a tool (RUL-1; make_project writes them from templates/<[board] template>)."""
        if "_rules" not in self.__dict__:
            from Tools.KiCadDesignTools.routing.busroute.profile import Profile
            self._rules = Profile.from_project(self.pcb)
        return self._rules

    def copper_sketch(self):
        """The board's copper sketch ([copper] sketch) parsed by copper.cu_sketch, read once (its parameters in nm:
        .p["gap"], ["clearance"], ["plane_clearance"], ["minwidth"]; its regions)."""
        if "_sketch" not in self.__dict__:
            from Tools.KiCadDesignTools.copper import cu_sketch
            self._sketch = cu_sketch.load_sketch(self.path(self.need("copper.sketch")), len(self.layers))
        return self._sketch

    def copper_plane(self):
        """(plane clearance, minimum width) in mm of the board's copper sketch: the zone clearance its plane layers
        are written with (a foreign via's antipad) and the narrowest copper a zone keeps."""
        p = self.copper_sketch().p
        return p["plane_clearance"] / 1e6, p["minwidth"] / 1e6

    # ------------------------------------------------------------------ checks
    def _check(self):
        d = self.data
        for k in ("board", "layers"):
            if k not in d:
                raise ConfigError("%s: section [%s] is missing" % (self.toml, k))
        b = d["board"]
        for k in ("name",):
            if k not in b:
                raise ConfigError("%s: board.%s is missing" % (self.toml, k))
        roles = d["layers"].get("roles")
        if not roles or not isinstance(roles, list):
            raise ConfigError("%s: layers.roles must list one role per copper layer, top to bottom" % self.toml)
        n = len(roles)
        if n < 2 or n % 2:
            raise ConfigError("%s: %d copper layers (an even number >= 2 expected)" % (self.toml, n))
        bad = [r for r in roles if r not in ROLES]
        if bad:
            raise ConfigError("%s: unknown layer role(s) %s (one of %s)" % (self.toml, bad, sorted(ROLES)))
        users = d["layers"].get("names", [None] * n)
        if len(users) != n:
            raise ConfigError("%s: layers.names has %d entries for %d layers" % (self.toml, len(users), n))
        self.layers = []
        for i, role in enumerate(roles):
            if i == 0:
                kname, lid = "F.Cu", 0
            elif i == n - 1:
                kname, lid = "B.Cu", 2
            else:
                kname, lid = "In%d.Cu" % i, 2 + 2 * i
            self.layers.append(Layer("L%d" % (i + 1), kname, lid, role, users[i] or None))
        self._byL = {l.L: l for l in self.layers}
        self._byK = {l.kicad: l for l in self.layers}
        for g in d.get("route", {}).get("group", []):
            for k in ("name", "file"):
                if k not in g:
                    raise ConfigError("%s: a [[route.group]] without %s: %r" % (self.toml, k, g))
            if not os.path.isfile(self.path(g["file"])):
                raise ConfigError("%s: route group %s: %s does not exist" % (self.toml, g["name"], g["file"]))
        names = [g["name"] for g in d.get("route", {}).get("group", [])]
        dup = sorted({x for x in names if names.count(x) > 1})
        if dup:
            raise ConfigError("%s: route groups named twice: %s" % (self.toml, dup))


def load(path):
    return Board(path)


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    try:
        cfg = load(argv[0])
    except ConfigError as e:
        print("board.toml: %s" % e)
        return 1
    print("board %s in %s" % (cfg.name, cfg.dir))
    print("layers: " + ", ".join("%s=%s %s%s" % (l.L, l.kicad, l.role, " (%s)" % l.user if l.user else "") for l in cfg.layers))
    print("signal layers: %s; plane layers: %s" % (" ".join(cfg.signal_layers()), " ".join(cfg.plane_layers())))
    print("route groups in build order: %s" % ", ".join("%s (%s)" % (g["name"], g["file"]) for g in cfg.groups))
    print("sections: %s" % ", ".join(sorted(cfg.data)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
