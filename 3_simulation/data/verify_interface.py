"""Independent numerical checks of the new bias/bus derivative relations.

These checks validate the stated equations on ideal constitutive examples.
They are not additional prototype measurements or calibration estimates.
"""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import brentq
import pvlib

root=Path(__file__).resolve().parents[1]
m=json.loads((root/'data/module_parameters.json').read_text())['parameters']
par=pvlib.pvsystem.calcparams_cec(1000,25,**{k:m[k] for k in
 ['alpha_sc','a_ref','I_L_ref','I_o_ref','R_sh_ref','R_s','Adjust']})
rt,rb,rf,ri,cf,vh,vref,R=39000.,10000.,10000.,22000.,1e-6,3.3,2.5,50.
ref=lambda u:vref*(1+rt/rb+rt/(rf+ri))-rt*vh/(rf+ri)*u
du=1e-5;u=.525
va=lambda i:float(pvlib.pvsystem.v_from_i(i,*par))
def series_bus(u):
 i=brentq(lambda i:R*i-va(i)-ref(u),1e-6,1.3,xtol=1e-12)
 return R*i
v=series_bus(u);i=v/R
vprime=(va(i+1e-6)-va(i-1e-6))/2e-6
pred_series=(-rt*vh/(rf+ri))/(1-vprime/R)
num_series=(series_bus(u+du)-series_bus(u-du))/(2*du)
# A smooth current-controlled branch example for the implicit parallel relation.
ia=lambda v:float(pvlib.pvsystem.i_from_v(v,*par))
ic=lambda v,u:.3+.4*u-.005*v
def parallel_bus(u):return brentq(lambda v:ia(v)+ic(v,u)-v/R,0,25,xtol=1e-12)
vpar=parallel_bus(u)
iaprime=(ia(vpar+1e-5)-ia(vpar-1e-5))/2e-5
pred_parallel=.4/(1/R-iaprime+.005)
num_parallel=(parallel_bus(u+du)-parallel_bus(u-du))/(2*du)
vb=(ri*vh*u+rf*vref)/(rf+ri)
kcl=(ref(u)-vref)/rt+(vb-vref)/ri-vref/rb
assert abs(kcl)<1e-12
assert np.isclose(pred_series,num_series,rtol=1e-7)
assert np.isclose(pred_parallel,num_parallel,rtol=1e-7)
rth=rt*rb/(rt+rb)
out={'scope':'Ideal circuit/constitutive verification, not physical prototype validation',
 'setpoint_intercept_V':ref(0),'setpoint_slope_V_per_command':-rt*vh/(rf+ri),
 'fixed_output_filter_tau_s':cf*rf*(ri+rth)/(rf+ri+rth),
 'feedback_clamped_filter_tau_s':cf*rf*ri/(rf+ri),
 'feedback_KCL_residual_A':kcl,
 'series_bus_sensitivity_analytic':pred_series,'series_bus_sensitivity_numerical':num_series,
 'parallel_bus_sensitivity_analytic':pred_parallel,'parallel_bus_sensitivity_numerical':num_parallel,
 'parallel_check_branch_model':'Ic(V,u) = 0.3 + 0.4*u - 0.005*V A, illustrative only'}
(root/'data/interface_verification.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
