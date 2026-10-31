"""Plot original reported hardware aggregates; never reconstruct raw samples."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
d=pd.read_csv(root/'data/hardware_reported_metrics.csv').iloc[:3]
plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','pdf.fonttype':42,
 'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,
 'axes.labelcolor':'#243648','text.color':'#243648','axes.edgecolor':'#8898a0'})
fig,axs=plt.subplots(1,2,figsize=(7.2,3.0),layout='constrained')
for ax,top,a,b in [(axs[0],'Series-assisted','passive_series_A','controlled_series_1'),
                   (axs[1],'Parallel-assisted','passive_parallel_B','controlled_parallel_2')]:
 ax.plot(range(3),d[a].astype(float),'o--',c='#788391',lw=1.2,label='Passive temporal reference')
 ax.plot(range(3),d[b].astype(float),'s-',c='#087e69',lw=1.7,label='Controlled hardware case')
 for j,val in enumerate(d[b].astype(float)):
  ax.annotate(f'{val:.2f}',(j,val),xytext=(0,8 if j!=1 else -15),textcoords='offset points',
              ha='center',fontsize=8,color='#087e69')
 ax.set_xticks(range(3),['Pre\n0–15 s','Middle\n15–40 s','Recovery\n40–60 s'])
 ax.set(title=top,ylabel='Reported mean bus power (W)',ylim=(0,25 if top.startswith('Series') else 9))
 ax.axvspan(.75,1.25,color='#e0eee8',zorder=-2)
 ax.grid(axis='y',color='#dde4e7',alpha=.8)
 ax.text(1,.92,'Shading in controlled case only',transform=ax.get_xaxis_transform(),
         ha='center',va='top',fontsize=6.4,color='#53676c')
handles,labels=axs[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=8)
fig.savefig(root/'figures/hardware_summary.pdf',bbox_inches='tight')
fig.savefig(root/'figures/hardware_summary.png',bbox_inches='tight',dpi=200)
