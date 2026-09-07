# OBD1 Honda / Acura engine profiles

Use with `igngen new --engine <CODE> --show`.
Factory SAE peaks for USDM OBD1-era (~1992–1995). Timing/vacuum/boost defaults match IgnGen starters (edit for your build).

| Code | Car | Disp | HP @ RPM | TQ @ RPM | Redline |
|------|-----|------|----------|----------|---------|
| D15B7 | Civic DX/LX, del Sol S | 1493 | 102 @ 5900 | 98 @ 5000 | 6500 |
| D15Z1 | Civic VX | 1493 | 92 @ 5500 | 97 @ 4500 | 7000 |
| D15B8 | Civic CX | 1493 | 70 @ 5000 | 91 @ 2000 | 6500 |
| D16Z6 | Civic EX/Si, del Sol Si | 1590 | 125 @ 6600 | 106 @ 5200 | 7200 |
| B16A3 | del Sol VTEC | 1595 | 160 @ 7600 | 111 @ 7000 | 8200 |
| B17A1 | Integra GS-R 92–93 | 1678 | 160 @ 7600 | 117 @ 7000 | 8000 |
| B18A1 | Integra LS 92–93 | 1834 | 140 @ 6300 | 121 @ 5200 | 7200 |
| B18B1 | Integra LS 94–95 | 1834 | 142 @ 6300 | 127 @ 5200 | 6800 |
| B18C1 | Integra GS-R 94–95 | 1797 | 170 @ 7600 | 128 @ 6200 | 8000 |
| F22A1 | Prelude S / Accord | 2156 | 135 @ 5200 | 142 @ 4500 | 6500 |
| F22B1 | Accord EX 94–95 | 2156 | 145 @ 5500 | 147 @ 4500 | 6500 |
| F22B2 | Accord DX/LX 94–95 | 2156 | 130 @ 5300 | 139 @ 4200 | 6500 |
| H22A1 | Prelude VTEC | 2157 | 190 @ 6800 | 158 @ 5500 | 7500 |
| H23A1 | Prelude Si | 2259 | 160 @ 5800 | 156 @ 5300 | 6500 |

Notes:
- New profiles are **stock NA** (`boost_psi = 0`). D16Z6 keeps its existing mild-boost starter values.
- Idle defaults **750 ± 50 RPM**; base timing **16°**; edit freely at the prompts.
- Peak mechanical timing is an IgnGen curve starter (32–36°), not a copied OEM distributor table.
