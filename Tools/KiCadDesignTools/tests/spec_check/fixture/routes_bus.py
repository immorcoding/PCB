"""The spec_check benchmark's routes data: only what spec_check reads (no geometry)."""
VIA_LIMIT = 3
ADDR_WINDOW = 10
TUNING = {"groups": {"lane0": {"nets": ["D%d" % i for i in range(8)] + ["DM0"], "spread": 0.5},
                     "addr": {"nets": ["A0", "A1", "A2", "A3"], "ref": ["CK"], "lo": -ADDR_WINDOW, "hi": ADDR_WINDOW}},
          "margin": 0.3, "radius": 0.25, "amp": 0.5, "amp_max": 2.0, "pitch": {"default": 0.3, "CK": 0.5},
          "end": 0.35, "clr": 0.19, "area_gap": 0.127, "keep": 0.7}
