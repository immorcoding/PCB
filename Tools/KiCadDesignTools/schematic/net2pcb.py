"""Bring a board in line with a schematic netlist (the scripted equivalent of
KiCad's "Update PCB from Schematic" / AD's "Update PCB Document").

    D:\\KiCad\\bin\\python.exe -m Tools.KiCadDesignTools.schematic.net2pcb <netlist.net> <board.kicad_pcb>

- Footprints missing on the board are loaded from the stock libraries (or from a
  project library <lib>.pretty next to the board) and dropped at the board origin
  (placement is a separate step).
- Footprints already on the board keep their position; value, schematic link,
  pad nets and the "do not populate" attribute (the symbol's `dnp`, a netlist
  property) are refreshed. If the schematic names a different footprint,
  the old one is replaced in place (same position, rotation and side).
- Footprints on the board that are no longer in the netlist are reported,
  not deleted.

The netlist is the kicadsexpr export:
    kicad-cli sch export netlist --format kicadsexpr -o x.net x.kicad_sch
"""
import os, sys
import pcbnew

from Tools.KiCadDesignTools.schematic.kisch import parse, find, find_all

FP_DIR = r"D:\KiCad\share\kicad\footprints"


def read_netlist(path):
    t = parse(open(path, encoding="utf-8").read())
    comps = {}
    for c in find_all(find(t, "components"), "comp"):
        sp = find(c, "sheetpath")
        props = {str(find(pr, "name")[1]) for pr in find_all(c, "property")}
        comps[str(find(c, "ref")[1])] = {
            "value": str(find(c, "value")[1]),
            "footprint": str(find(c, "footprint")[1]),
            "path": str(find(sp, "tstamps")[1]) + str(find(c, "tstamps")[1]),
            "dnp": "dnp" in props,
        }
    pads = {}
    for n in find_all(find(t, "nets"), "net"):
        name = str(find(n, "name")[1])
        for node in find_all(n, "node"):
            pads[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return comps, pads


def main(net_path, pcb_path):
    comps, pads = read_netlist(net_path)
    board = pcbnew.LoadBoard(pcb_path)
    existing = {fp.GetReference(): fp for fp in board.GetFootprints()}
    nets = {}

    def net(name):
        if name not in nets:
            item = board.FindNet(name)
            if item is None:
                item = pcbnew.NETINFO_ITEM(board, name)
                board.Add(item)
            nets[name] = item
        return nets[name]

    added = 0
    for ref, c in sorted(comps.items()):
        fp = existing.get(ref)
        lib, name = c["footprint"].split(":")
        old = None
        if fp is not None and str(fp.GetFPID().GetLibItemName()) != name:
            old, fp = fp, None
        if fp is None:
            local = os.path.join(os.path.dirname(os.path.abspath(pcb_path)), lib + ".pretty")
            fp = pcbnew.FootprintLoad(local if os.path.isdir(local) else os.path.join(FP_DIR, lib + ".pretty"), name)
            if fp is None:
                raise SystemExit(f"{ref}: footprint {c['footprint']} not found")
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            fp.SetReference(ref)
            board.Add(fp)
            if old is not None:
                fp.SetPosition(old.GetPosition())
                if old.GetLayer() == pcbnew.B_Cu:
                    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
                fp.SetOrientation(old.GetOrientation())
                board.Remove(old)
                print(f"{ref}: footprint replaced by {name}")
            else:
                added += 1
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH(c["path"]))
        if fp.IsDNP() != c["dnp"]:
            fp.SetDNP(c["dnp"])
            print(f"{ref}: DNP {'set' if c['dnp'] else 'cleared'}")
        for pad in fp.Pads():
            name = pads.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net(name))
            else:
                pad.SetNetCode(0)
    stale = sorted(set(existing) - set(comps))
    pcbnew.SaveBoard(pcb_path, board)
    print(f"{len(comps)} components, {added} added, {len(nets)} nets" +
          (f", NOT IN NETLIST: {' '.join(stale)}" if stale else ""))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
