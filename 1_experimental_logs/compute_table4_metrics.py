"""Recompute the time-domain metrics of Table 4 from the raw testbed logs.

Usage
    python compute_table4_metrics.py                 # reads ./csv/*.csv
    python compute_table4_metrics.py path/to/csv_dir

Expected file names (one CSV per 60 s run):
    Baseline_A_series_run1.csv ... Baseline_B_parallel_run3.csv
    Case1_series_run1.csv ... Case2_parallel_run3.csv
The scenario is the part before "_run"; runs of the same scenario are averaged.

Column names are mapped in COLUMNS below; edit the right-hand names if your CSV
headers differ. Time may be in ms or s (detected automatically).

Outputs (written next to this script):
    metrics_per_run.csv       one row per run
    metrics_table4.csv        mean and standard deviation per scenario
Metric definitions follow Table 4 and Section 3.2 of the article.
"""
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

# manuscript name -> column header in your CSV files (edit if needed)
COLUMNS = {
    'time': 'time_ms',
    'V': 'V_bus_V',
    'I': 'I_shunt_A',
    'P': 'P_bus_W',
    'P_filt': 'P_filtered_W',
    'u': 'pwm_duty_pct',
    'valid': 'valid',
}
T_ON, T_OFF, T_END = 15.0, 40.0, 60.0      # shading window [s]
U_MIN, U_MAX = 5.0, 93.0                   # supervisory command bounds [%]
BAND, N_CONSEC, TS = 0.10, 5, 0.05


def load(path):
    df = pd.read_csv(path)
    missing = [v for v in COLUMNS.values() if v not in df.columns and v != COLUMNS['valid']]
    if missing:
        raise SystemExit(f'{os.path.basename(path)}: missing columns {missing}; edit COLUMNS at the top of this script')
    out = pd.DataFrame({k: df[v] for k, v in COLUMNS.items() if v in df.columns})
    if 'valid' in out:
        out = out[out['valid'].astype(float) > 0]
    t = out['time'].astype(float).values
    out['t'] = t / 1000.0 if t.max() > 1000 else t          # ms -> s
    if out['P'].isna().all():
        out['P'] = out['V'] * out['I']
    return out.reset_index(drop=True)


def settle(t, p, t0, ref):
    m = t >= t0
    tt, pp = t[m], p[m]
    run = 0
    for j, ok in enumerate(np.abs(pp - ref) <= BAND * abs(ref)):
        run = run + 1 if ok else 0
        if run >= N_CONSEC:
            return float(tt[j - N_CONSEC + 1] - t0)
    return np.nan


def metrics(df):
    t, P, u = df.t.values, df.P.values.astype(float), df.u.values.astype(float)
    pre, sh, rec = t < T_ON, (t >= T_ON) & (t < T_OFF), t >= T_OFF
    late_sh, late_rec = (t >= T_OFF - 5) & (t < T_OFF), t >= T_END - 5
    m_sh = P[sh].mean()
    controlled = np.ptp(u) > 0
    return {
        'P_pre_W': P[pre].mean(), 'P_window_W': m_sh, 'P_rec_W': P[rec].mean(),
        'E_60s_J': np.trapezoid(P, t) if hasattr(np, 'trapezoid') else np.trapz(P, t),
        'E_60s_J_sum': P.sum() * TS,
        'settle_onset_s': settle(t, P, T_ON, P[late_sh].mean()) if controlled else np.nan,
        'settle_recovery_s': settle(t, P, T_OFF, P[late_rec].mean()) if controlled else np.nan,
        'mean_cmd_increment_pct': np.mean(np.abs(np.diff(u))),
        'saturation_occupancy_pct': 100 * np.mean(np.isclose(u, U_MIN) | np.isclose(u, U_MAX)),
        'persistence_pct': 100 * np.mean(np.abs(P[sh] - m_sh) <= BAND * m_sh) if controlled else np.nan,
        'ripple_W': P[sh].std(ddof=0),
        'cmd_excursion_pct': np.ptp(u),
        'n_samples': len(t),
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'csv')
    files = sorted(glob.glob(os.path.join(src, '*.csv')))
    if not files:
        raise SystemExit(f'No CSV files in {src}')
    rows = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        scen = re.split(r'_run', name)[0]
        r = metrics(load(f))
        r.update(file=os.path.basename(f), scenario=scen)
        rows.append(r)
    per = pd.DataFrame(rows)
    cols = ['scenario', 'file'] + [c for c in per.columns if c not in ('scenario', 'file')]
    per[cols].to_csv(os.path.join(here, 'metrics_per_run.csv'), index=False, float_format='%.4f')
    num = [c for c in per.columns if c not in ('scenario', 'file', 'n_samples')]
    summ = per.groupby('scenario')[num].agg(['mean', 'std'])
    summ.columns = [f'{a}_{b}' for a, b in summ.columns]
    summ.insert(0, 'n_runs', per.groupby('scenario').size())
    summ.to_csv(os.path.join(here, 'metrics_table4.csv'), float_format='%.4f')
    pd.set_option('display.width', 200)
    print(summ[[c for c in summ.columns if c.endswith('_mean') or c == 'n_runs']].round(3).T.to_string())
    # flag identical command traces between scenarios (see checklist item 2)
    us = {os.path.basename(f): load(f).u.values for f in files}
    names = list(us)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = us[names[i]], us[names[j]]
            if len(a) == len(b) and np.ptp(a) > 0 and np.allclose(a, b):
                print(f'NOTE: identical PWM command traces in {names[i]} and {names[j]}')


if __name__ == '__main__':
    main()
