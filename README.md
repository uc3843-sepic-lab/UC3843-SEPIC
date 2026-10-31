# UC3843-SEPIC

Data, firmware, hardware files and simulation code for a low-cost photovoltaic (PV) prototype in
which an STM32 microcontroller supervises a UC3843 current-mode SEPIC converter. The
microcontroller injects a bounded, RC-filtered PWM bias into the converter's feedback node; the
analog UC3843 loop keeps control of the switching. Two nominal 20 W panels and a 50 ohm load were
tested in passive series and parallel references and in series-assisted and parallel-assisted
converter arrangements under single-panel shading. A physics-informed, lag-aligned
Gaussian-process supervisor is evaluated in simulation.

These files support a research article submitted to *Energy Informatics*.

## Contents

| Folder | Contents |
|---|---|
| `1_experimental_logs/` | Raw 20 Hz testbed logs (one CSV per 60 s run), reference I-V/P-V sweeps, and `compute_table4_metrics.py`, which recomputes Table 4 of the article from the logs |
| `2_firmware/` | STM32CubeIDE project of the supervisory firmware (Section 3.2 of the article) |
| `3_hardware/` | SEPIC/UC3843 schematic with the bias-injection network (Fig. 1), wiring of the four test arrangements (Fig. 2), bill of materials |
| `4_simulation/` | Simulation package of the learning extension (same as Additional file 1 of the article): module record and export script, reproduction script, all simulated traces and results, verification scripts; see `4_simulation/README.md` |

## Experimental protocol (summary)

Outdoor tests under natural sunlight, fixed 50 ohm load, 60 s per run sampled at 20 Hz
(1200 samples), three repetitions per arrangement. Shading sequence for the controlled cases:
0-15 s unshaded, 15-40 s one panel covered, 40-60 s recovery. Arrangements: passive series
reference (A), passive parallel reference (B), series-assisted controlled case (1),
parallel-assisted controlled case (2). Irradiance and module temperature were not measured.
Bus-side power is an operating-point quantity, not a converter-efficiency measurement.

## Reproducing the article's numbers

* Table 4 (measured metrics): `python 1_experimental_logs/compute_table4_metrics.py`
* Tables 7-8 and Figs. 5 and 9-12 (simulation): see `4_simulation/README.md` (about 1 min)

## Licences

* Code (`compute_table4_metrics.py`, `2_firmware/`, `4_simulation/data/*.py`): MIT licence, see `LICENSE`.
* Data, documentation, schematic and figures: Creative Commons Attribution 4.0 International (CC BY 4.0), see `LICENSE-DATA.txt`.
* The module record in `4_simulation/data/module_parameters.json` is derived from the CEC/SAM
  database distributed with pvlib python (BSD-3-Clause).

## Funding

Deanship of Research and Graduate Studies, King Khalid University, Large Research Project,
grant RGP.2/399/47.

## Citation

Please cite the associated journal article; its reference will be added here after publication.
