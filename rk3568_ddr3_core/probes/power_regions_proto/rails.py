"""PROTOTYPE (issue 52): rail of each RK3568 supply pin group, after the official AIoT reference schematic
(RK3568_AIoT_REF_SCH V1.0, sheets 5, 11-18, 22; read from the text extract, bead-to-net pairing by list order).
VDD_CPU_COM (feedback pin) and DDR_VREFOUT are track nets, not here.
"""
RAIL_OF = {
    "VDD_CPU": "VDD_CPU", "VDD_LOGIC": "VDD_LOGIC", "VDD_GPU": "VDD_GPU", "VDD_NPU": "VDD_NPU",
    "DDRPHY_VDDQ": "VCC_DDR", "DDRPHY_VDDQL": "VCC_DDR",
    "PMU_VDD_LOGIC_0V9": "VDDA0V9_PMU", "PMUPLL_AVDD_0V9": "VDDA0V9_PMU", "PMUPLL_AVDD_1V8": "VCCA1V8_PMU",
    "PMUIO1": "VCC3V3_PMU", "PMUIO2": "VCC3V3_PMU",
    "SYSPLL_AVDD_0V9": "VDDA_0V9", "MULTI_PHY_AVDD_0V9": "VDDA_0V9", "PCIE30_AVDD_0V9": "VDDA_0V9",
    "SYSPLL_AVDD_1V8": "VCCA_1V8", "MULTI_PHY_AVDD_1V8": "VCCA_1V8", "PCIE30_AVDD_1V8": "VCCA_1V8",
    "SARADC_AVDD_1V8": "VCCA_1V8",
    "USB2_AVDD_0V9": "USB_AVDD_0V9", "USB3_AVDD_0V9": "USB_AVDD_0V9",
    "USB2_AVDD_1V8": "USB_AVDD_1V8", "USB3_AVDD_1V8": "USB_AVDD_1V8",
    "USB2_AVDD_3V3": "VCC_3V3", "USB3_AVDD_3V3": "VCC_3V3", "VCCIO5": "VCC_3V3", "VCCIO7": "VCC_3V3",
    "VCCIO6": "VCC_1V8", "OTP_VCC18": "VCC_1V8",
    "VCCIO1": "VCCIO_ACODEC", "VCCIO2": "VCCIO_FLASH", "VCCIO3": "VCCIO_SD", "VCCIO4": "VCCIO_WL",
    "EDP_TX_AVDD_0V9": "VDDA0V9_IMAGE", "HDMI_TX_AVDD_0V9": "VDDA0V9_IMAGE",
    "EDP_TX_AVDD_1V8": "VCCA1V8_IMAGE", "HDMI_TX_AVDD_1V8": "VCCA1V8_IMAGE",
    "MIPI_CSI_RX_AVDD_0V9": "MIPI_AVDD_0V9", "MIPI_DSI_TX0/LVDS_TX0_AVDD_0V9": "MIPI_AVDD_0V9",
    "MIPI_DSI_TX1_AVDD_0V9": "MIPI_AVDD_0V9",
    "MIPI_CSI_RX_AVDD_1V8": "MIPI_AVDD_1V8", "MIPI_DSI_TX0/LVDS_TX0_AVDD_1V8": "MIPI_AVDD_1V8",
    "MIPI_DSI_TX1_AVDD_1V8": "MIPI_AVDD_1V8",
}

# peak current (A) and the design guide's copper rules: (peak A, min width near the SoC mm, min width outside mm,
# layer-change vias outside the SoC). Hardware Design Guide V1.2 sections 2.2.2 and 3.2.2.5-3.2.2.9.
BIG = {
    "VDD_CPU": (3.0, 2.286, 5.08, 12), "VDD_LOGIC": (1.2, 1.524, 5.08, 12), "VDD_GPU": (1.2, 1.27, 5.08, 5),
    "VDD_NPU": (1.0, 1.27, 5.08, 5), "VCC_DDR": (1.0, 3.048, 5.08, 8),
}
# peak mA per small rail, summed from the guide's Table 2-14 (IO rails are "TBD" there)
SMALL_MA = {
    "VDDA0V9_PMU": 60, "VCCA1V8_PMU": 9, "VCC3V3_PMU": None, "VDDA_0V9": 340, "VCCA_1V8": 100.5,
    "USB_AVDD_0V9": 10, "USB_AVDD_1V8": 60, "VCC_3V3": None, "VCC_1V8": None, "VCCIO_ACODEC": None,
    "VCCIO_FLASH": None, "VCCIO_SD": None, "VCCIO_WL": None, "VDDA0V9_IMAGE": 175, "VCCA1V8_IMAGE": 116,
    "MIPI_AVDD_0V9": 110, "MIPI_AVDD_1V8": 32.5,
}
