"""Reproduce the reduced-order study; all time traces are SIMULATED.

Run: OPENBLAS_NUM_THREADS=1 python data/reproduce.py (from the package root).
Dependencies and provenance are recorded in provenance.json. No network required.
"""
from pathlib import Path
import json, time, platform, hashlib, sys
import numpy as np
import pandas as pd
import scipy
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.signal import find_peaks
import pvlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA, FIG = ROOT/'data', ROOT/'figures'
FIG.mkdir(exist_ok=True)
MODREC = json.loads((DATA/'module_parameters.json').read_text())
MOD = MODREC['parameters']
TS, HOLD, N, R = .05, 5, 600, 50.
TAUB = .01*27/37  # 10 kohm || (22+5) kohm, times 1 uF
GRID = np.linspace(.05, .95, 91)
DMAX = .025
METHODS = ['Adaptive P&O', 'Periodic scan', 'Raw GP', 'Aligned GP', 'Zero-prior aligned GP', 'Physics-aligned GP + reset']
COLORS = dict(zip(METHODS, ['#788391','#a76a19','#ae4271','#377eaa','#8b6db3','#087e69']))
CACHE = {}

def conditions(scenario, t):
    """Designed inputs, not observations of weather. Units W/m2 and degC."""
    if scenario == 'Uniform step':
        g = 1000 if t < 10 or t >= 20 else 500
        return g, g, 25.
    if scenario == 'Deep shade':
        return 1000, (1000 if t < 10 or t >= 20 else 200), 25.
    if scenario == 'Moving shade':
        if t < 7.5: return 1000, 650, 25.
        if t < 15: return 350, 1000, 25.
        if t < 22.5: return 1000, 180, 25.
        return 750, 1000, 25.
    if scenario == 'Hot mismatch':
        return 800, (500 if t < 10 else (150 if t < 20 else 800)), 50.
    raise ValueError(scenario)

SCENARIOS = ['Uniform step', 'Deep shade', 'Moving shade', 'Hot mismatch']

def pars(g, temp):
    return pvlib.pvsystem.calcparams_cec(g, temp, **{k:MOD[k] for k in
        ['alpha_sc','a_ref','I_L_ref','I_o_ref','R_sh_ref','R_s','Adjust']})

def curve(topology, g1, g2, temp, dense=4001):
    p1,p2=pars(g1,temp),pars(g2,temp)
    if topology == 'Series':
        ii=np.linspace(0,max(p1[0],p2[0])*1.02,dense)
        v1=np.maximum(pvlib.pvsystem.v_from_i(ii,*p1),-.5)
        v2=np.maximum(pvlib.pvsystem.v_from_i(ii,*p2),-.5)
        vv=v1+v2
        ix=np.argsort(vv)
        vv,ii=vv[ix],ii[ix]
        ok=vv>=0
        vv,ii=vv[ok],ii[ok]
    else:
        voc=max(pvlib.pvsystem.v_from_i(0,*p1),pvlib.pvsystem.v_from_i(0,*p2))
        vv=np.linspace(0,voc,dense)
        # Ideal branch blocking: a shaded branch cannot absorb current.
        ii=np.maximum(pvlib.pvsystem.i_from_v(vv,*p1),0)+np.maximum(pvlib.pvsystem.i_from_v(vv,*p2),0)
    return vv,ii

def plant_map(topology, g1, g2, temp):
    key=(topology,g1,g2,temp)
    if key in CACHE: return CACHE[key]
    vv,ii=curve(*key)
    # Monotone I(V) and the resistive load line give one intersection for each D.
    dd=np.linspace(.20,.80,2401)
    rin=R*((1-dd)/dd)**2
    ratio=np.divide(vv,ii,out=np.full_like(vv,np.inf),where=ii>1e-12)
    # Interpolate the monotonically increasing input resistance V/I.
    vin=np.interp(rin,ratio,vv)
    iin=np.interp(vin,vv,ii)
    pp=vin*iin
    allowed=(dd>=.23)&(dd<=.77)
    oracle=pp[allowed].max()
    result=(dd,pp,vin,oracle,vv,ii)
    CACHE[key]=result
    return result

def kernel(x,y):
    r=np.sqrt(3)*np.abs(np.asarray(x)[:,None]-np.asarray(y)[None,:])/.12
    return .2**2*(1+r)*np.exp(-r)

def prior(query,topology,zero=False):
    if zero: return np.zeros(len(query))
    dd,pp,*_=plant_map(topology,1000,1000,25.)
    return np.interp(.8-.6*np.asarray(query),dd,pp)/40

def posterior(x,y,query,topology,zero=False):
    mq=prior(query,topology,zero)
    if len(x)==0: return mq,np.full(len(query),.2)
    x=np.asarray(x);y=np.asarray(y)
    kk=kernel(x,x)+(.003**2+1e-9)*np.eye(len(x))
    ch=cho_factor(kk,lower=True,check_finite=False)
    kq=kernel(x,query)
    mu=mq+kq.T@cho_solve(ch,y-prior(x,topology,zero),check_finite=False)
    z=solve_triangular(ch[0],kq,lower=True,check_finite=False)
    sd=np.sqrt(np.maximum(.04-np.sum(z*z,axis=0),1e-10))
    return mu,sd

def simulate(topology,scenario,method,seed,tau=.08,save=False):
    rng=np.random.default_rng(seed)
    # Same noise stream, startup command, action opportunities and slew limit.
    noise=rng.normal(0,.12,N)
    b=u=.5; d=.8-.6*b; what=.5
    x=[];y=[];rows=[];resets=0;flag=0;direction=1;prevp=None
    gp='GP' in method
    for k in range(N):
        t=k*TS
        if k%HOLD==0:
            if k>0:
                if gp:
                    zero=method=='Zero-prior aligned GP'
                    if method=='Physics-aligned GP + reset' and len(x)>=4:
                        mu,sd=posterior(x,y,[what],topology)
                        # Two consecutive innovation exceedances, including model uncertainty.
                        bad=abs(pobs/40-mu[0]) > 3*np.sqrt(sd[0]**2+.003**2)+.05
                        flag=flag+1 if bad else 0
                        if flag>=2:
                            x=[];y=[];resets+=1;flag=0
                    # All GP variants receive the same first sample, with different labels.
                    val=firstobs
                    x.append(u if method=='Raw GP' else firstw);y.append(val/40)
                    x=x[-64:];y=y[-64:]
                elif method=='Adaptive P&O':
                    if prevp is not None:
                        delta=pobs-prevp
                        if abs(delta)>.08:
                            direction*=1 if delta>0 else -1
                    step=.025 if prevp is not None and abs(pobs-prevp)>2 else .005
                    prevp=pobs
            if gp:
                mu,sd=posterior(x,y,GRID,topology,method=='Zero-prior aligned GP')
                # UCB target; project target onto the one-step reachable interval.
                score=mu+2*sd-.02*(GRID-u)**2
                target=GRID[np.argmax(score)]
                unew=np.clip(target,u-DMAX,u+DMAX)
            elif method=='Periodic scan':
                # A deterministic triangle scan; samples at common opportunities.
                if u>=.95-1e-9: direction=-1
                elif u<=.05+1e-9: direction=1
                unew=u+direction*DMAX
            else:
                if k==0: step=.005
                unew=u+direction*step
                if unew<.05 or unew>.95:
                    direction*=-1;unew=u+direction*step
            u=float(np.clip(unew,.05,.95))
        b=np.exp(-TS/TAUB)*b+(1-np.exp(-TS/TAUB))*u
        # Nominal filter-state observer: no true duty, irradiance or temperature supplied.
        what=np.exp(-TS/.08)*what+(1-np.exp(-TS/.08))*b
        d=np.exp(-TS/tau)*d+(1-np.exp(-TS/tau))*(.8-.6*b)
        g1,g2,temp=conditions(scenario,t)
        dd,pp,vv,oracle,_,_=plant_map(topology,g1,g2,temp)
        power=float(np.interp(d,dd,pp))
        vin=float(np.interp(d,dd,vv));vout=np.sqrt(R*power)
        pobs=power+noise[k]
        if k%HOLD==0:firstobs=pobs;firstw=what
        rows.append((topology,scenario,method,seed,t+TS,u,b,what,d,vin,vout,power,pobs,oracle,g1,g2,temp,resets,tau))
    df=pd.DataFrame(rows,columns=['topology','scenario','method','seed','time_s','u','filtered_u','estimated_effective_u','D','V_pv_V','V_bus_V','P_bus_W','P_measured_W','P_oracle_W','G1_W_m2','G2_W_m2','T_cell_C','resets','tau_loop_s'])
    du=np.diff(df.u.to_numpy()[::HOLD],prepend=.5)
    metric=dict(topology=topology,scenario=scenario,method=method,seed=seed,tau_loop_s=tau,
        energy_J=TS*df.P_bus_W.sum(),oracle_energy_J=TS*df.P_oracle_W.sum(),
        capture_pct=100*df.P_bus_W.sum()/df.P_oracle_W.sum(),
        regret_J=TS*(df.P_oracle_W-df.P_bus_W).sum(),
        total_variation=np.abs(du).sum(),max_delta_u=np.abs(du).max(),
        min_u=df.u.min(),max_u=df.u.max(),resets=resets,
        late_capture_pct=100*df.loc[df.time_s>25,'P_bus_W'].sum()/df.loc[df.time_s>25,'P_oracle_W'].sum())
    assert df.u.between(.05-1e-9,.95+1e-9).all()
    assert metric['max_delta_u']<=DMAX+1e-9
    assert np.allclose(df.V_bus_V**2/R,df.P_bus_W,rtol=1e-12)
    assert np.allclose(df.D/(1-df.D)*df.V_pv_V,df.V_bus_V,rtol=.003,atol=.01)
    assert metric['capture_pct']<=100.001
    return metric,df

def plots(metrics,traces,stress):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,
        'axes.spines.right':False,'axes.titleweight':'bold','pdf.fonttype':42,'ps.fonttype':42,
        'axes.labelcolor':'#243648','text.color':'#243648','axes.edgecolor':'#8c99a2',
        'grid.color':'#dce2e6','grid.alpha':.65,'legend.frameon':False})
    def finish(fig,name):
        fig.savefig(FIG/f'{name}.pdf',bbox_inches='tight')
        fig.savefig(FIG/f'{name}.png',dpi=220,bbox_inches='tight')
        plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(7.2,5.0),layout='constrained')
    for ax,top in zip(axs[0],['Series','Parallel']):
        for g,c in [(1000,'#788391'),(650,'#377eaa'),(200,'#087e69')]:
            dd,pp,vin,oracle,vv,ii=plant_map(top,1000,g,25)
            ax.plot(vv,vv*ii,label=f'$G_2={g}$',c=c)
        ax.set(title=f'{top}: PV characteristic',xlabel='PV voltage (V)',ylabel='Power (W)')
        ax.grid();ax.legend(fontsize=7)
    for ax,top in zip(axs[1],['Series','Parallel']):
        for g,c in [(1000,'#788391'),(650,'#377eaa'),(200,'#087e69')]:
            dd,pp,*_=plant_map(top,1000,g,25)
            uu=(.8-dd)/.6
            ax.plot(uu,pp,c=c)
        ax.axvspan(0,.05,color='#eee');ax.axvspan(.95,1,color='#eee')
        ax.set(xlim=(0,1),title=f'{top}: assumed bias map',xlabel='Normalized bias command $u$',ylabel='Settled bus power (W)')
        ax.grid()
    finish(fig,'characteristics')
    fig,axs=plt.subplots(3,2,figsize=(7.2,6.4),sharex=True,layout='constrained')
    for col,top in enumerate(['Series','Parallel']):
        a=traces[(traces.topology==top)&(traces.scenario=='Deep shade')&(traces.seed==100)]
        base=a[a.method==METHODS[-1]]
        axs[0,col].plot(base.time_s,base.P_oracle_W,c='#243648',ls='--',lw=1,label='Reachable oracle')
        for m in METHODS:
            b=a[a.method==m]
            axs[0,col].plot(b.time_s,b.P_bus_W,c=COLORS[m],lw=.9,label=m)
            axs[1,col].plot(b.time_s,b.u,c=COLORS[m],lw=.9)
            loss=TS*np.cumsum(b.P_oracle_W.to_numpy()-b.P_bus_W.to_numpy())
            axs[2,col].plot(b.time_s,loss,c=COLORS[m],lw=1)
        for ax in axs[:,col]:
            ax.axvspan(10,20,color='#dceae6',alpha=.55);ax.grid()
        axs[0,col].set_title(top)
        axs[0,col].set_ylabel('Bus power (W)')
        axs[1,col].set_ylabel('Bias command $u$')
        axs[2,col].set(ylabel='Accumulated loss (J)',xlabel='Time (s)')
    handles,labels=axs[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=7,ncol=3,loc='outside lower center')
    finish(fig,'transients')
    fig,axs=plt.subplots(1,2,figsize=(7.2,3.25),layout='constrained')
    for ax,top in zip(axs,['Series','Parallel']):
        for j,m in enumerate(METHODS):
            ss=metrics[(metrics.topology==top)&(metrics.method==m)]
            vals=[];ses=[]
            for sc in SCENARIOS:
                x=ss[ss.scenario==sc].capture_pct
                vals.append(x.mean());ses.append(1.96*x.std(ddof=1)/np.sqrt(len(x)))
            ax.errorbar(np.arange(4)+(j-2.5)*.12,vals,yerr=ses,fmt='o',ms=4,
                capsize=2,c=COLORS[m],label=m)
        ax.set_xticks(range(4),['Uniform\nstep','Deep\nshade','Moving\nshade','Hot\nmismatch'])
        ax.set(title=top,ylabel='Reachable energy capture (%)',ylim=(0,103))
        ax.grid(axis='y')
    axs[1].legend(fontsize=7,loc='lower right')
    finish(fig,'capture')
    fig,axs=plt.subplots(1,2,figsize=(7.2,3.2),layout='constrained')
    for ax,top in zip(axs,['Series','Parallel']):
        for m in ['Raw GP','Aligned GP','Physics-aligned GP + reset']:
            sub=stress[(stress.topology==top)&(stress.method==m)]
            means=sub.groupby('tau_loop_s').capture_pct.mean()
            lo=sub.groupby('tau_loop_s').capture_pct.std()/np.sqrt(12)*1.96
            ax.errorbar(means.index*1000,means,yerr=lo,c=COLORS[m],marker='o',capsize=3,label=m)
        ax.set(title=top,xlabel='Assumed inner-response time constant (ms)',ylabel='Energy capture (%)',ylim=(0,103))
        ax.grid()
    axs[0].legend(fontsize=7,loc='lower left')
    finish(fig,'lag_sensitivity')

def main():
    start=time.perf_counter();metrics=[];representative=[];alltraces=[]
    for top in ['Series','Parallel']:
        for sc in SCENARIOS:
            for method in METHODS:
                for seed in range(100,112):
                    met,df=simulate(top,sc,method,seed)
                    metrics.append(met);alltraces.append(df)
                    if seed==100:representative.append(df)
            print(top,sc,'done',flush=True)
    metrics=pd.DataFrame(metrics)
    metrics.to_csv(DATA/'run_metrics.csv',index=False,float_format='%.9g')
    traces=pd.concat(alltraces,ignore_index=True)
    traces.to_csv(DATA/'simulated_traces.csv.gz',index=False,float_format='%.8g',compression={'method':'gzip','mtime':0})
    rep=pd.concat(representative,ignore_index=True)
    rep.to_csv(DATA/'representative_traces.csv',index=False,float_format='%.8g')
    stress=[]
    for top in ['Series','Parallel']:
        for tau in [.02,.08,.2]:
            for m in ['Raw GP','Aligned GP','Physics-aligned GP + reset']:
                for seed in range(100,112):
                    met,_=simulate(top,'Deep shade',m,seed,tau)
                    stress.append(met)
    stress=pd.DataFrame(stress);stress.to_csv(DATA/'lag_sensitivity.csv',index=False,float_format='%.9g')
    # Cluster bootstrap: resample noise seeds, retaining all eight fixed cases per seed.
    p=metrics.pivot(index=['topology','scenario','seed'],columns='method',values='capture_pct')
    rng=np.random.default_rng(20261028)
    comp=[]
    for m in METHODS[:-1]:
        delta=(p[METHODS[-1]]-p[m]).groupby('seed').mean().to_numpy()
        bs=np.mean(rng.choice(delta,(10000,len(delta)),replace=True),axis=1)
        comp.append(dict(comparator=m,mean_gain_pp=delta.mean(),ci_low_pp=np.quantile(bs,.025),ci_high_pp=np.quantile(bs,.975)))
    pd.DataFrame(comp).to_csv(DATA/'paired_comparisons.csv',index=False,float_format='%.9g')
    summary=metrics.groupby(['topology','scenario','method'],sort=False).agg(
        capture_mean=('capture_pct','mean'),capture_sd=('capture_pct','std'),
        energy_mean_J=('energy_J','mean'),regret_mean_J=('regret_J','mean'),
        variation_mean=('total_variation','mean'),resets_mean=('resets','mean')).reset_index()
    summary.to_csv(DATA/'summary.csv',index=False,float_format='%.9g')
    plots(metrics,rep,stress)
    runtime=time.perf_counter()-start
    provenance={'study_type':'Designed simulation, not measured prototype or field data',
        'public_parameter_record':MODREC['source_record']+' (CEC database bundled with pvlib), current-scaled to 20 W',
        'module_scaling_factor':MODREC['scaling']['factor_k'],
        'public_source_url':'https://github.com/pvlib/pvlib-python/blob/v0.16.1/pvlib/data/sam-library-cec-modules-2019-03-05.csv',
        'source_license':'pvlib BSD-3-Clause; CEC/SAM source attribution retained',
        'pvlib':pvlib.__version__,'numpy':np.__version__,'scipy':scipy.__version__,
        'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'python':platform.python_version(),
        'platform':platform.platform(),'seeds':list(range(100,112)),
        'sample_period_s':TS,'decision_hold_samples':HOLD,'duration_s':TS*N,
        'assumed_bias_to_duty':'D_equilibrium = 0.8 - 0.6*filtered_u; not identified from prototype',
        'bias_filter_time_constant_s':TAUB,'nominal_loop_time_constant_s':.08,
        'gp_memory':64,'gp_kernel':'Matern 3/2','gp_length_scale':.12,
        'gp_signal_std_normalized':.2,'gp_noise_std_normalized':.003,
        'gp_ucb_multiplier':2.,'bootstrap_clusters':'12 noise seeds; 10000 resamples; seed 20261028',
        'assumed_load_ohm':R,'bypass_drop_V':.5,'noise_std_W':.12,
        'runtime_total_s':runtime,
        'limitations':['No switching waveform, DCM, saturation or thermal simulation',
            'Ideal lossless steady SEPIC loading; duty lag is a phenomenological response',
            'No STM32/UC3843 execution or timing measurements',
            'No external irradiance or measured shading timeseries',
            'Confidence intervals describe noise in fixed designed cases only']}
    provenance['module_record_sha256']=hashlib.sha256((DATA/'module_parameters.json').read_bytes()).hexdigest()
    (DATA/'provenance.json').write_text(json.dumps(provenance,indent=2))
    print(summary.to_string(index=False));print(pd.DataFrame(comp).to_string(index=False))
    print('Runtime',runtime,flush=True)

if __name__=='__main__':main()
