"""Inspect half-power connectivity before labelling shallow local peaks."""
from pathlib import Path
from collections import deque
import json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from project3_analyze import read_csv
run=Path(sys.argv[1]);m=json.loads((run/'metrics.json').read_text(encoding='utf8'))
fig,axes=plt.subplots(1,3,figsize=(13,4.2),layout='constrained');reports={}
for ax,(freq,metric) in zip(axes,m['band_field_checks'].items()):
    a=read_csv(run/f'farfield_full_{freq}.csv')
    mask=(a['Theta [deg]']>=0)&(a['Phi [deg]']<359.999)
    th=np.unique(a['Theta [deg]'][mask]);ph=np.unique(a['Phi [deg]'][mask])
    grid=np.full((len(th),len(ph)),np.nan)
    for t,p,g in zip(a['Theta [deg]'][mask],a['Phi [deg]'][mask],a['dB(RealizedGainTotal) (Real)'][mask]):
        grid[np.argmin(abs(th-t)),np.argmin(abs(ph-p))]=g
    allowed=grid>=grid.max()-3
    seen=np.zeros_like(allowed);start=np.unravel_index(grid.argmax(),grid.shape)
    queue=deque([start]);seen[start]=True
    while queue:
        i,j=queue.popleft()
        neighbors=[(ii,(j+dj)%len(ph)) for ii in range(max(0,i-1),min(len(th),i+2)) for dj in [-1,0,1]]
        if i in [0,len(th)-1]:neighbors += [(i,jj) for jj in range(len(ph))]
        for ii,jj in neighbors:
            if allowed[ii,jj] and not seen[ii,jj]:seen[ii,jj]=True;queue.append((ii,jj))
    rows=[]
    for peak in metric['local_peak_list']:
        i=np.argmin(abs(th-peak['theta_deg']));j=np.argmin(abs(ph-peak['phi_deg']))
        rows.append(dict(**peak,in_connected_half_power_main_region=bool(seen[i,j])))
    reports[freq]=rows
    for phi,color in [(0,'#176d87'),(90,'#b65b3a')]:
        pos=grid[:,np.argmin(abs(ph-phi))];neg=grid[:,np.argmin(abs(ph-(phi+180)))]
        x=np.r_[-th[::-1],th[1:]];y=np.r_[neg[::-1],pos[1:]]-grid.max()
        ax.plot(x,y,label=f'Phi {phi}/{phi+180}',color=color)
    ax.axhline(-3,color='#666',ls=':',lw=1);ax.axhline(-10,color='#777',ls='--',lw=1)
    ax.set(xlim=(-90,90),ylim=(-35,1),title=freq+' GHz',xlabel='Signed angle from broadside / deg',ylabel='Relative realized gain / dB')
    ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.savefig(run/'mainbeam_diagnostic.png',dpi=180);plt.close(fig)
(run/'mainbeam_connectivity.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
print(json.dumps(reports,indent=2))
