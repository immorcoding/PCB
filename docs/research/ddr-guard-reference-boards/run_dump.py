"""System python launcher: run_dump.py <repo_root> <in.brd> <out.json>. Goes through core/heavy.run."""
import sys, os

repo, src, dst = sys.argv[1:4]
sys.path.insert(0, repo)
from Tools.KiCadDesignTools.core import heavy

here = os.path.dirname(os.path.abspath(__file__))
r = heavy.run([r"D:\KiCad\bin\python.exe", os.path.join(here, "dump_board.py"), src, dst], timeout=1500, cwd=repo)
print(r.returncode, (r.stdout or b"").decode(errors="replace")[-1500:], (r.stderr or b"").decode(errors="replace")[-1500:])
