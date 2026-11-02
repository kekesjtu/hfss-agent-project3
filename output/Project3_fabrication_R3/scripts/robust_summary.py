"""Independent scalar and sampled full-sphere checks, preserving raw solver data."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.ndimage import maximum_filter
from project3_analyze import analyze,read_csv

def sphere_checks(path):
    a=read_csv(path)
    mask=(a['Theta [deg]']>=0)&(a['Phi [deg]']<359.999)
    th=np.unique(a['Theta [deg]'][mask]);ph=np.unique(a['Phi [deg]'][mask])
    grid=np.full((len(th),len(ph)),np.nan)
    for t,p,g in zip(a['Theta [deg]'][mask],a['Phi [deg]'][mask],a['dB(RealizedGainTotal) (Real)'][mask]):
        grid[np.argmin(abs(th-t)),np.argmin(abs(ph-p))]=g
    assert np.isfinite(grid).all()
    candidates=[]
    local=maximum_filter(grid,size=3,mode=('nearest','wrap'))
    maxima=(grid>=local-1e-10)
    # All azimuths coincide at a spherical pole. A pole that rises in any
    # neighboring azimuth is not a local maximum, even if it falls along some
    # other azimuths. Rectangular filtering alone falsely counts a tilted
    # main-beam shoulder at theta=0 as a separate side lobe.
    if abs(th[0])<1e-8 and grid[0].max()<grid[1].max()-1e-10:maxima[0,:]=False
    if abs(th[-1]-180)<1e-8 and grid[-1].max()<grid[-2].max()-1e-10:maxima[-1,:]=False
    for i,j in np.argwhere(maxima):
        candidates.append((float(grid[i,j]),float(th[i]),float(ph[j])))
    def vector(t,p):
        t,p=np.deg2rad([t,p]);return np.array([np.sin(t)*np.cos(p),np.sin(t)*np.sin(p),np.cos(t)])
    peaks=[]
    for g,t,p in sorted(candidates,reverse=True):
        if all(np.rad2deg(np.arccos(np.clip(np.dot(vector(t,p),vector(q['theta_deg'],q['phi_deg'])),-1,1)))>10 for q in peaks):
            peaks.append(dict(theta_deg=t,phi_deg=p,gain_dbi=g,below_global_db=float(grid.max()-g)))
    broad=(abs(a['Theta [deg]'])<1e-8)&(abs(a['Phi [deg]'])<1e-8)
    pol=abs(float(a['dB(RealizedGainTheta) (Real)'][broad][0]-a['dB(RealizedGainPhi) (Real)'][broad][0]))
    return dict(angular_grid_deg=[float(np.diff(th).min()),float(np.diff(ph).min())],
        broadside_linear_component_difference_db=pol,
        broadside_below_peak_db=float(grid.max()-grid[0].mean()),
        maximum_rear_hemisphere_below_peak_db=float(grid.max()-grid[th>90].max()),
        local_peak_list=peaks,
        secondary_peak_suppression_db=peaks[1]['below_global_db'] if len(peaks)>1 else None)

def summary(run):
    run=Path(run);m=analyze(run)
    if (run/'farfield_full.csv').exists():
        m['full_sphere_checks']=sphere_checks(run/'farfield_full.csv')
    m['band_field_checks']={p.stem.rsplit('_',1)[1]:sphere_checks(p) for p in sorted(run.glob('farfield_full_*.csv'))}
    if m.get('antenna_58') and 's11_58_db' in m:
        ant=m['antenna_58'];expected=ant['IncidentPower']*(1-10**(m['s11_58_db']/10))
        m['power_balance_check']=dict(expected_accepted_power_from_s11=expected,
            accepted_power_difference=ant['AcceptedPower']-expected,
            radiated_power_not_above_accepted=bool(0<=ant['RadiatedPower']<=ant['AcceptedPower']),
            total_efficiency_difference=ant['TotalEfficiency']-ant['RadiatedPower']/ant['IncidentPower'])
    (run/'metrics.json').write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding='utf8')
    return dict(run=run.name,converged=m.get('strict_convergence_met',m.get('converged')),delta=m.get('delta_s'),mesh=m.get('mesh_elements'),
        s11=m.get('s11_58_db'),worst=m.get('target_150mhz_worst_s11_db'),bands=m.get('bands_10db'),
        sphere=m.get('full_sphere_checks'),eff=m.get('antenna_58',{}).get('RadiationEfficiency'))

if __name__=='__main__':
    for r in sys.argv[1:]:print(json.dumps(summary(r),ensure_ascii=False,indent=2))
