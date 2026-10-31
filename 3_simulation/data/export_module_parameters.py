"""Export the PV module record used by the simulations to data/module_parameters.json.

Source: CEC module database bundled with pvlib python 0.16.1 (SAM 2018.11.11 r2).
Record: Canadian Solar CS5C-80M, a standard 36-cell mono-crystalline silicon module
(not building-integrated) with a positive short-circuit-current temperature coefficient.

The prototype uses nominal 20 W, 36-cell panels. No 20 W, 36-cell crystalline-silicon
record exists in the database, so the 80 W record is scaled to 20 W at standard test
conditions by cell-area (current) scaling with factor k:

    I_L_ref, I_o_ref, alpha_sc, I_sc_ref, I_mp_ref, A_c  ->  k * value
    R_s, R_sh_ref                                         ->  value / k
    a_ref, V_oc_ref, V_mp_ref, beta_oc, gamma_r, Adjust, N_s, T_NOCT  unchanged

Substituting these into the single-diode equation multiplies the current at every voltage
by k; pvlib's CEC translation (calcparams_cec) preserves this at every irradiance and
temperature. The scaled module is therefore the same cell technology with smaller cells.
"""
from pathlib import Path
import json

import numpy as np
import pvlib

RECORD = 'Canadian_Solar_Inc__CS5C_80M'
P_TARGET = 20.0     # W at standard test conditions
SDM = ['alpha_sc', 'a_ref', 'I_L_ref', 'I_o_ref', 'R_sh_ref', 'R_s', 'Adjust']
SCALE_I = ['I_L_ref', 'I_o_ref', 'alpha_sc', 'I_sc_ref', 'I_mp_ref', 'A_c']
SCALE_R = ['R_s', 'R_sh_ref']


def stc_pmp(p):
    par = pvlib.pvsystem.calcparams_cec(1000, 25, **{k: p[k] for k in SDM})
    return float(pvlib.pvsystem.max_power_point(*par, method='newton')['p_mp'])


def main():
    rec = pvlib.pvsystem.retrieve_sam('CECMod')[RECORD]
    src = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v))
           for k, v in rec.items()}
    k = P_TARGET / stc_pmp(src)
    scaled = dict(src)
    for key in SCALE_I:
        scaled[key] = src[key] * k
    for key in SCALE_R:
        scaled[key] = src[key] / k
    scaled['STC'] = P_TARGET
    out = {
        'module_name': RECORD + ' (current-scaled to 20 W)',
        'source': 'pvlib %s bundled CECMod database (%s)' % (pvlib.__version__, src.get('Version', '')),
        'source_record': RECORD,
        'scaling': {'factor_k': k, 'rule': __doc__.split('conditions by cell-area (current) scaling with factor k:')[1]
                    .split('Substituting')[0].strip()},
        'source_parameters': src,
        'parameters': scaled,
        'checks': {'source_STC_model_Pmp_W': stc_pmp(src), 'scaled_STC_model_Pmp_W': stc_pmp(scaled)},
    }
    path = Path(__file__).resolve().parent / 'module_parameters.json'
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out['checks'], indent=2), 'k =', k)


if __name__ == '__main__':
    main()
