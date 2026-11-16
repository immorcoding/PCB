"""Q3: can a script write a `(generated (type tuning_pattern) ...)` object that KiCad accepts?

Takes lentest.kicad_pcb (net /SDRAM_D9 carries a hand-built arc meander), appends a tuning_pattern
`generated` block whose `members` are the meander's tracks/arcs, then checks:
  1. pcbnew.LoadBoard sees one generator  (b.Generators())
  2. pcbnew.SaveBoard keeps it, with the same member list
  3. kicad-cli pcb upgrade (load + save) keeps it
  4. kicad-cli pcb drc still reports the same length for /SDRAM_D9

    D:\\KiCad\\bin\\python.exe -I make_generated.py <lentest dir> <out dir>
"""
import os, re, shutil, subprocess, sys, uuid
import pcbnew

SRC = os.path.abspath(sys.argv[1]); OUT = os.path.abspath(sys.argv[2])
CLI = r"D:\KiCad\bin\kicad-cli.exe"
os.makedirs(OUT, exist_ok=True)
for ext in (".kicad_pcb", ".kicad_pro"):
    shutil.copy(os.path.join(SRC, "lentest" + ext), os.path.join(OUT, "lentest_gen" + ext))
shutil.copy(os.path.join(SRC, "rules", "e01_probe_all_lengths.kicad_dru"), os.path.join(OUT, "lentest_gen.kicad_dru"))
pcb = os.path.join(OUT, "lentest_gen.kicad_pcb")

b = pcbnew.LoadBoard(pcb)
mm = pcbnew.ToMM
members = []
for t in b.GetTracks():
    if t.GetNetname() == "/SDRAM_D9" and t.GetClass() in ("PCB_TRACK", "PCB_ARC"):
        x0, x1 = sorted((mm(t.GetStartX()), mm(t.GetEndX())))
        if x0 >= 5.0 - 1e-6 and x1 <= 15.5 + 1e-6 and not (x0 == 5.0 and x1 == 5.0):
            members.append(t.m_Uuid.AsString())
print("members chosen:", len(members))

text = open(pcb, encoding="utf-8").read()
members_q = " ".join(f'"{m}"' for m in members)
# Field names/order follow what KiCad 10.0.8 itself writes (see roundtrip_pcbnew.kicad_pcb after
# make_generated.py has run); the 7.99-era sample in KiCad's QA data uses an unquoted (id ...) and
# an unquoted members list, which 10.0.8 also reads.
gen = f'''	(generated
		(uuid "{uuid.uuid4()}")
		(type tuning_pattern)
		(name "Tuning Pattern")
		(layer "F.Cu")
		(base_line
			(pts
				(xy 5 54) (xy 15.5 54)
			)
		)
		(corner_radius_percent 100)
		(end
			(xy 15.5 54)
		)
		(initial_side "left")
		(is_time_domain no)
		(last_diff_pair_gap 0.18)
		(last_netname "/SDRAM_D9")
		(last_status "too_short")
		(last_track_width 0.1)
		(last_tuning_length 0)
		(max_amplitude 0.5)
		(min_amplitude 0.2)
		(min_spacing 0.5)
		(origin
			(xy 5 54)
		)
		(override_custom_rules no)
		(rounded yes)
		(single_sided no)
		(target_length 52.854)
		(target_length_max 52.954)
		(target_length_min 52.754)
		(target_skew 0)
		(target_skew_max 0.1)
		(target_skew_min -0.1)
		(tuning_mode "single")
		(members {members_q}
		)
	)
'''
idx = text.rstrip().rfind(")")
open(pcb, "w", encoding="utf-8").write(text[:idx] + gen + text[idx:])

def count(path):
    t = open(path, encoding="utf-8").read()
    m = re.search(r"\(generated.*?\(members(.*?)\)\s*\)", t, re.S)
    return (t.count("(generated"), len(m.group(1).split()) if m else None)

print("written, generated blocks / members:", count(pcb))
b2 = pcbnew.LoadBoard(pcb)
print("1. pcbnew.LoadBoard -> Generators():", len(b2.Generators()))
rt = os.path.join(OUT, "roundtrip_pcbnew.kicad_pcb")
pcbnew.SaveBoard(rt, b2)
print("2. after pcbnew.SaveBoard: generated blocks / members:", count(rt))
up = os.path.join(OUT, "lentest_gen_up.kicad_pcb")
shutil.copy(pcb, up)
p = subprocess.run([CLI, "pcb", "upgrade", "--force", up], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("3. after kicad-cli pcb upgrade (rc %d): generated blocks / members:" % p.returncode, count(up))
