"""Page 4: QSPI NOR flash (SPEC 2.1, 3). Also the worked example of the page style.

W25Q128JVEIM pins (Winbond W25Q128JV datasheet Rev D p.7; KiCad symbol Memory_Flash:W25Q128JVE):
  1 /CS, 2 DO (IO1), 3 /WP (IO2), 4 GND, 5 DI (IO0), 6 CLK, 7 /HOLD or /RESET (IO3), 8 VCC, 9 EP.
The -IM part ships with QE = 0: until firmware sets QE, pins 3 and 7 are /WP and /HOLD, so both get a
pull-up. /CS is pulled up so the flash stays deselected while the MCU is in reset.
The exposed pad carries no signal; it is grounded, with no vias or tracks under it (datasheet p.96-97).
"""
from .common import FP


def build(sh):
    sh.title("QSPI NOR Flash 128 Mbit", 6, 8)
    sh.title("Bring-up link", 116, 8)
    sh.link("R404", "+3V3", "+3V3_QSPI", 124, 14)
    sh.rails = {"+3V3": "+3V3_QSPI"}
    sh.ic("Memory_Flash:W25Q128JVE", "U401", "W25Q128JVEIM", 36, 24, "Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm", {
        "1": "QSPI_BK1_NCS", "6": "QSPI_CLK",
        "5": "QSPI_BK1_IO0", "2": "QSPI_BK1_IO1", "3": "QSPI_BK1_IO2", "7": "QSPI_BK1_IO3",
        "8": "+3V3", "4": "GND", "9": "GND",
    }, stub=3, fields={"MPN": "W25Q128JVEIM", "Manufacturer": "Winbond"})
    sh.R("R401", "10k", 70, 14, "+3V3", "QSPI_BK1_NCS")
    sh.R("R402", "10k", 78, 14, "+3V3", "QSPI_BK1_IO2")
    sh.R("R403", "10k", 86, 14, "+3V3", "QSPI_BK1_IO3")
    sh.caps(401, ["100nF", "1uF"], 100, 14, "+3V3")
    sh.note("R401: /CS high while the MCU is in reset.  R402, R403: /WP and /HOLD high until firmware sets QE (the -IM part ships with QE = 0).", 6, 44)
    sh.note("EP: no internal signal, grounded; no vias or tracks under it.  Alternate part, same footprint: Micron MT25QL128ABA1EW9-0SIT.", 6, 46)
