"""Numerical checks of the exported simulation results; writes data/numerical_verification.json.

Run after reproduce.py, from the package root:
    python data/verify_numerics.py

Checks
1. Every run in run_metrics.csv has a complete trace (600 samples) in simulated_traces.csv.gz.
2. Energy and reachable-energy capture recomputed from the exported traces match run_metrics.csv.
3. Command bounds (0.05-0.95) and the per-decision slew limit (0.025) hold in every trace.
4. Grid refinement: doubling the array resolution (8001 points) and the duty grid (4801 points)
   changes the reachable steady oracle by a negligible relative amount at every profile state.
5. The module model reproduces the rated power at standard test conditions.
6. Fingerprint (SHA-256) of the *uncompressed* trace CSV. gzip output can differ between zlib
   versions, so the compressed file is not fingerprinted; the uncompressed data are.
"""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd
import pvlib

DATA = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reproduce', DATA / 'reproduce.py')
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

KEYS = ['topology', 'scenario', 'method', 'seed']


def oracle_refined(top, g1, g2, temp):
    vv, ii = rep.curve(top, g1, g2, temp, dense=8001)
    dd = np.linspace(.20, .80, 4801)
    rin = rep.R * ((1 - dd) / dd) ** 2
    ratio = np.divide(vv, ii, out=np.full_like(vv, np.inf), where=ii > 1e-12)
    vin = np.interp(rin, ratio, vv)
    pp = vin * np.interp(vin, vv, ii)
    return pp[(dd >= .23) & (dd <= .77)].max()


def main():
    metrics = pd.read_csv(DATA / 'run_metrics.csv')
    raw = gzip.open(DATA / 'simulated_traces.csv.gz').read()
    traces = pd.read_csv(DATA / 'simulated_traces.csv.gz')

    # 1-2. completeness, energy and capture
    g = traces.groupby(KEYS, sort=False)
    counts = g.size()
    energy = rep.TS * g.P_bus_W.sum()
    oracle = rep.TS * g.P_oracle_W.sum()
    capture = 100 * energy / oracle
    m = metrics.set_index(KEYS)
    m = m.loc[energy.index]
    rel_e = float(np.max(np.abs(energy.values - m.energy_J.values) / m.energy_J.values))
    abs_c = float(np.max(np.abs(capture.values - m.capture_pct.values)))

    # 3. bounds and slew limit at each decision
    u_ok = bool(traces.u.between(.05 - 1e-9, .95 + 1e-9).all())
    steps = []
    for _, d in g:
        u = d.u.to_numpy()[::rep.HOLD]
        steps.append(np.abs(np.diff(u, prepend=.5)).max())
    slew = float(max(steps))

    # 4. grid refinement of the reachable oracle at every profile state
    states = sorted({rep.conditions(sc, k * rep.TS) for sc in rep.SCENARIOS for k in range(rep.N)})
    worst = 0.0
    for top in ['Series', 'Parallel']:
        for st in states:
            o1 = rep.plant_map(top, *st)[3]
            worst = max(worst, abs(oracle_refined(top, *st) - o1) / o1)

    # 5. module model at standard test conditions
    par = rep.pars(1000, 25.)
    pmp = float(pvlib.pvsystem.max_power_point(*par, method='newton')['p_mp'])

    out = {
        'nominal_runs': int(len(metrics)),
        'trace_rows': int(len(traces)),
        'samples_per_run_all_600': bool((counts == rep.N).all()),
        'energy_recalculated_from_export': rel_e < 1e-6,
        'energy_max_relative_difference': rel_e,
        'energy_capture_recalculated_from_export': abs_c < 1e-4,
        'capture_max_abs_difference_pp': abs_c,
        'command_bounds_verified': u_ok,
        'max_command_step_per_decision': slew,
        'slew_limit_verified': slew <= .025 + 1e-9,
        'profile_states_checked': len(states),
        'max_relative_oracle_change_on_refinement': worst,
        'STC_module_model_Pmp_W': pmp,
        'module_record_STC_W': float(rep.MOD['STC']),
        'trace_csv_uncompressed_sha256': hashlib.sha256(raw).hexdigest(),
        'fingerprint_note': 'SHA-256 of the uncompressed CSV bytes; the .gz container itself may differ between zlib versions.',
    }
    (DATA / 'numerical_verification.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    assert out['samples_per_run_all_600'] and out['energy_recalculated_from_export']
    assert out['energy_capture_recalculated_from_export'] and u_ok and out['slew_limit_verified']


if __name__ == '__main__':
    main()
