# Hardware

| File | Contents |
|---|---|
| `SEPIC_UC3843_schematic.png` | SEPIC power stage, UC3843 control circuit and the STM32 bias-injection network (Fig. 1 of the article; drawn in LTspice with the pin-compatible LT1243 symbol because LTspice has no UC3843 symbol) |
| `testbed_configurations.jpg` | Wiring of Baseline A, Baseline B, Case 1 and Case 2 (Fig. 2 of the article) |
| `BOM.csv` | Bill of materials collected from the article text and the schematic |

Optional additions by the authors: the LTspice `.asc` file of the schematic and
photographs of the testbed.

Points to check before uploading (they also affect the article):

* The text names the output diode MBR10100CT; the schematic label reads MBRF10100CT
  (same die, isolated TO-220 package). Use one name consistently.
* With RT = 10 kΩ and CT = 1 nF, the UC3843 datasheet relation f ≈ 1.72 / (RT·CT) gives
  about 170 kHz, whereas the article states f_s ≈ 20 kHz. CT = 10 nF would give about
  17 kHz. Confirm the fitted timing capacitor.
