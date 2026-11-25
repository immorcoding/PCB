"""Deterministic uuids for what the board writers add: the same build gives the same board file, byte for byte.

    make(key)                  the uuid (text) of a stable key: uuid5 in this module's namespace
    stamp(item, key)           sets a pcbnew item's uuid to make(key) (EDA_ITEM.SetUuid(KIID(...))); before board.Add
    stamp_footprint(fp, key)   the footprint and everything in it: fields by name, graphics, pads and zones by index
    Keys()                     a run's keys made unique: Keys().unique(key) gives key, then key#2, key#3 ... for repeats

A key names the item, not the run: kind + name / reference / net + rounded coordinates, or a reference + an index in
a fixed order ("place:outline:seg:0", "stitch:via:110.25,52.8", "finish:fiducial:FID1"). Writers that write the
file as text put make(key) into the (uuid ...) row. busroute, cu_sketch, finishing.pour and kisch have namespaces of
their own (they were deterministic before this module).
"""
import uuid

NS = uuid.UUID("562f5d27-e069-4085-9169-472959319107")


def make(key):
    return str(uuid.uuid5(NS, key))


def stamp(item, key):
    import pcbnew
    item.SetUuid(pcbnew.KIID(make(key)))
    return item


def stamp_footprint(fp, key):
    """A footprint loaded from a library has no uuids in its file: pcbnew gives it and each child a random one."""
    stamp(fp, key)
    for f in fp.GetFields():
        stamp(f, "%s/field/%s" % (key, f.GetName()))
    for i, g in enumerate(fp.GraphicalItems()):
        stamp(g, "%s/item/%d" % (key, i))
    for i, p in enumerate(fp.Pads()):
        stamp(p, "%s/pad/%d" % (key, i))
    for i, z in enumerate(fp.Zones()):
        stamp(z, "%s/zone/%d" % (key, i))
    return fp


class Keys:
    """Keys of one run made unique (two equal items at the same place get key and key#2)."""

    def __init__(self):
        self.seen = {}

    def unique(self, key):
        n = self.seen.get(key, 0) + 1
        self.seen[key] = n
        return key if n == 1 else "%s#%d" % (key, n)
