# Additional file 1: simulation package

Simulation package of the UC3843-SEPIC repository; the same files are supplied as Additional file 1
of the associated journal article.

All time series and performance values produced by this package are **simulated**. They are
not measurements of the STM32/UC3843 prototype. The only hardware values in the package are
the window means of the measured tests (`data/hardware_reported_metrics.csv`, Table 4 of the
article), which `plot_hardware_summary.py` redraws as Fig. 9 without reconstructing any trace.

## Reproduce

From the package root:

```bash
python -m pip install -r requirements.txt
python data/export_module_parameters.py      # module record -> data/module_parameters.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python data/reproduce.py   # 576 runs + 216 stress runs, figures
python data/verify_numerics.py               # writes data/numerical_verification.json
python data/verify_interface.py              # writes data/interface_verification.json
python data/plot_hardware_summary.py         # Fig. 9
```

`reproduce.py` takes about 35 s on one core. No online data access is needed once the
dependencies are installed. The seeds are fixed, so the numbers in the article are reproduced
exactly; `requirements.txt` lists the versions used for the published results.

## Module record

`export_module_parameters.py` takes the Canadian Solar CS5C-80M record (36-cell
mono-crystalline silicon, 80.15 W, not building-integrated, positive short-circuit-current
temperature coefficient) from the CEC database bundled with pvlib python 0.16.1 and scales it to
20 W at standard test conditions by cell-area scaling with k = 0.2495: the photocurrent,
saturation current, short-circuit and maximum-power currents and the current temperature
coefficient are multiplied by k, and the series and shunt resistances are divided by k. This
multiplies the current at every voltage by k at all irradiances and temperatures (pvlib CEC
translation) and leaves the voltage characteristic unchanged. The scaled module (Voc 21.8 V,
Vmp 17.5 V, Imp 1.143 A, Isc 1.240 A, +0.089 %/K, −0.374 %/K) represents the nominal 20 W,
36-cell prototype panels but is not an identification of them. The source and scaled
parameters are both stored in `module_parameters.json`.

## Model assumptions

Irradiance and cell-temperature profiles are designed inputs defined by `conditions()` in
`reproduce.py` (Table 5 of the article); no measured weather series is used. The affine
bias-to-duty map (D = 0.8 − 0.6 b), the feedback loading of the bias filter, the duty response
pole (80 ms nominal; 20 and 200 ms in the stress test), ideal bypass/branch blocking and
lossless load matching are declared assumptions shared by all controllers. The simulated plant
is one converter behind the whole two-module array; it does not reproduce the branch-assisted
hardware arrangements.

Noise is added directly to power with standard deviation 0.12 W; it is not a full
INA238/shunt/ADC error model. The state observer never receives the actual duty, irradiance or
cell temperature. The nominal physical prior is fixed at reference conditions, and the
observer's 80 ms constant stays fixed during the stress tests. The paired bootstrap resamples
twelve noise-seed clusters, each keeping all eight topology/profile cases; it quantifies
uncertainty under the stated noise model, not field generalization.

## Checks

* `reproduce.py` asserts command bounds, the 0.025 slew limit, power/load consistency and the
  ideal voltage ratio for every run.
* `verify_numerics.py` recomputes every energy total and capture ratio from the exported traces,
  checks bounds and slew limits, refines the array (8001 points) and duty (4801 points) grids to
  bound the oracle discretization error, checks the 20 W rating at standard conditions, and
  records the SHA-256 of the **uncompressed** trace CSV. The `.gz` container itself can differ
  between zlib versions, so it is not fingerprinted.
* `verify_interface.py` checks the feedback-node KCL and the series/parallel bus-sensitivity
  equations of the article on ideal constitutive examples (mathematical verification, not
  prototype calibration).

## Files and units

| File | Contents |
|---|---|
| `data/module_parameters.json` | Source and scaled module parameters, scaling factor, checks |
| `data/simulated_traces.csv.gz` | All 576 nominal runs, 600 samples each (345,600 rows) |
| `data/representative_traces.csv` | Seed 100 for every topology/profile/controller |
| `data/run_metrics.csv` | One row per nominal run |
| `data/summary.csv` | Case means and SDs of capture, energy, loss, command activity, resets |
| `data/paired_comparisons.csv` | Proposed minus comparator, percentage points, bootstrap intervals |
| `data/lag_sensitivity.csv` | 216 stress runs (the 72 rows at 80 ms repeat nominal settings) |
| `data/provenance.json` | Module record, assumptions, seeds, settings, software versions |
| `data/numerical_verification.json` | Output of `verify_numerics.py` |
| `data/interface_verification.json` | Output of `verify_interface.py` |
| `data/hardware_reported_metrics.csv` | Measured window means of the hardware tests (Table 4) |
| `figures/` | Figs. 5, 9, 10, 11 and 12 of the article (PDF, with PNG previews) |

Trace columns: `topology` and `scenario` identify the case, `method` the controller and `seed`
the noise realization. `time_s` is the end of a model sample (0.05–30 s). `u`, `filtered_u`,
`estimated_effective_u` and `D` are dimensionless. Voltages are in V, powers in W, irradiance in
W/m², cell temperature in °C; `resets` is cumulative. `P_oracle_W` is the command-reachable
steady reference without slew or transient restrictions, not an implemented controller.
`energy_J` and `regret_J` are in J.

## Licence

Code: MIT (see `LICENSE`). Data and documentation: CC BY 4.0. The module record comes from the
CEC/SAM database distributed with pvlib python (BSD-3-Clause).
