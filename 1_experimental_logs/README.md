# Experimental testbed logs

**Authors: put your own recorded files here before making the repository public, then delete this note.** This folder is
empty on purpose; no data have been created for it.

## 1. Raw logs → `csv/`

One CSV file per 60 s run, exactly as streamed by the STM32 over USART2 (convert to CSV
if needed, but do not edit or filter the values). Use these names:

| Scenario | Files |
|---|---|
| Baseline A, series, passive | `Baseline_A_series_run1.csv`, `_run2`, `_run3` |
| Baseline B, parallel, passive | `Baseline_B_parallel_run1.csv`, `_run2`, `_run3` |
| Case 1, series + bias-injection SEPIC | `Case1_series_run1.csv`, `_run2`, `_run3` |
| Case 2, parallel + bias-injection SEPIC | `Case2_parallel_run1.csv`, `_run2`, `_run3` |

If a baseline was recorded only once, include `_run1` only.

Expected columns (rename the headers, or edit `COLUMNS` at the top of the script):

| Column | Unit | Description |
|---|---|---|
| `time_ms` | ms | time since the start of the run (s is also accepted) |
| `V_bus_V` | V | bus voltage from the INA238 |
| `I_shunt_A` | A | shunt current from the INA238 |
| `P_bus_W` | W | computed bus-side power, V x I |
| `P_filtered_W` | W | moving-average filtered power used by the supervisor |
| `pwm_duty_pct` | % | supervisory PWM command u_k |
| `valid` | 0/1 | sample-validity flag |

## 2. Reference sweeps → `iv_pv_sweeps/`

The outdoor I-V and P-V sweeps taken with the programmable resistive load
(reference sweeps taken outdoors with a programmable resistive load), one CSV per sweep with columns `V_V`, `I_A`, `P_W` and
the date and time in the file name.

## 3. Recompute Table 4

```
pip install numpy pandas
python compute_table4_metrics.py
```

It writes `metrics_per_run.csv` (each run) and `metrics_table4.csv` (mean and standard
deviation per scenario) and prints a note if two runs have identical command traces.
The script applies the metric definitions given with Table 4 of the article (shading
window 15-40 s, command bounds 5 % and 93 %, ±10 % band, five consecutive samples).
Compare its output with Table 4 before uploading; the standard deviations can be added
to Table 4.
