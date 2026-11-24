"""Where things are: the repository, KiCad's programs and libraries, Edge (for screenshots of local HTML pages).

KiCad 10 is not on PATH on this machine. Its folder is taken from, in this order: the environment variable KICAD_BIN,
the folder of the running interpreter when that is KiCad's own python.exe (it sits next to kicad-cli.exe), and
D:\\KiCad\\bin. Every tool reads these names from here instead of writing the path itself.

Tools run as modules from the repository root: `python -m Tools.KiCadDesignTools.<category>.<tool>`. `tool_cmd` builds that command
line for a subprocess and `REPO` is the folder to run it in, so a tool that starts another tool passes absolute paths
as its arguments.
"""
import os, sys

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # Tools/KiCadDesignTools
REPO = os.path.dirname(os.path.dirname(PACKAGE))
TOOLS = os.path.join(REPO, "Tools")
TEMPLATES = os.path.join(REPO, "templates")
DATA = os.path.join(PACKAGE, "data")                                       # shared data files (stackups/)


def _kicad_bin():
    env = os.environ.get("KICAD_BIN")
    if env:
        return env
    here = os.path.dirname(sys.executable)
    if os.path.isfile(os.path.join(here, "kicad-cli.exe")):
        return here
    return r"D:\KiCad\bin"


KICAD_BIN = _kicad_bin()
KICAD_CLI = os.path.join(KICAD_BIN, "kicad-cli.exe")
KICAD_PY = os.path.join(KICAD_BIN, "python.exe")
KICAD_SHARE = os.path.join(os.path.dirname(KICAD_BIN), "share", "kicad")
KICAD_FP = os.path.join(KICAD_SHARE, "footprints")
KICAD_SYM = os.path.join(KICAD_SHARE, "symbols")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def tool_cmd(module, *args, python=None):
    """Command line that runs Tools.KiCadDesignTools.<module> (e.g. "analysis.track_shape") as a module; run it with
    cwd=REPO and absolute paths as arguments."""
    return [python or sys.executable, "-m", "Tools.KiCadDesignTools." + module] + [str(a) for a in args]
