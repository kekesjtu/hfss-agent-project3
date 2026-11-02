import argparse
import csv
import json
from pathlib import Path
import re
import numpy as np
from scipy.signal import find_peaks


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.reader(f,delimiter=";")
        header=next(reader)
        rows=np.array([[float(x) for x in row] for row in reader if row],dtype=float)
    return {name:rows[:,i] for i,name in enumerate(header)}


def analyze(run):
    run=Path(run)
    result=json.loads((run/"result.json").read_text(encoding="utf-8"))
    metrics=dict(run=str(run),parameters=result["parameters"],success=result["success"])
    model=next(run.glob("*.aedt"),run/"Project3.aedt")
    if model.exists():
        text=model.read_text(encoding="utf-8",errors="ignore")
        order=re.search(r"BasisOrder=(-?\d+)",text)
        if order:
            metrics["basis_order"]=int(order.group(1))
        metrics["two_sided_shell_copper"]="IsTwoSided=true" in text and "IsShellElement=true" in text
    if (run/"convergence.txt").exists():
        text=(run/"convergence.txt").read_text()
        metrics["converged"]="Converged : Yes" in text
        current=re.search(r"Current\s+:\s+([\d.]+)",text)
        if current:
            metrics["delta_s"]=float(current.group(1))
        target=re.search(r"Target\s+:\s+([\d.]+)",text)
        if target:
            metrics["target_delta_s"]=float(target.group(1))
        tc=re.search(r"Target Consecutive Passes\s+:\s+(\d+)",text)
        cc=re.search(r"Current Consecutive Passes\s+:\s+(\d+)",text)
        if tc and cc:
            metrics["target_consecutive_passes"]=int(tc.group(1))
            metrics["current_consecutive_passes"]=int(cc.group(1))
            metrics["strict_convergence_met"]=(metrics.get("delta_s",1)<=metrics.get("target_delta_s",0) and int(cc.group(1))>=int(tc.group(1)))
    if (run/"mesh_stats.txt").exists():
        text=(run/"mesh_stats.txt").read_text()
        m=re.search(r"Total number of mesh elements:\s+(\d+)",text)
        if m:
            metrics["mesh_elements"]=int(m.group(1))
    if (run/"sparameters.csv").exists():
        a=read_csv(run/"sparameters.csv")
        f=a["Freq [GHz]"]
        s=a["dB(S(P1,P1)) (Real)"]
        metrics["minimum_s11_db"]=float(s.min())
        metrics["resonance_ghz"]=float(f[s.argmin()])
        metrics["s11_58_db"]=float(np.interp(5.8,f,s))
        target_f=np.linspace(5.725,5.875,151)
        metrics["target_150mhz_worst_s11_db"]=float(np.interp(target_f,f,s).max())
        metrics["covers_centered_150mhz_window"]=bool(np.interp(target_f,f,s).max()<-10)
        groups=np.split(np.flatnonzero(s<=-10),np.where(np.diff(np.flatnonzero(s<=-10))>1)[0]+1)
        bands=[]
        for group in groups:
            if len(group)==0:
                continue
            first,last=group[0],group[-1]
            lo=float(f[first]) if first==0 else float(np.interp(-10,[s[first],s[first-1]],[f[first],f[first-1]]))
            hi=float(f[last]) if last==len(f)-1 else float(np.interp(-10,[s[last],s[last+1]],[f[last],f[last+1]]))
            bands.append(dict(low_ghz=lo,high_ghz=hi,bandwidth_mhz=(hi-lo)*1000,
                              contains_58=bool(lo<=5.8<=hi),edge_limited=bool(first==0 or last==len(f)-1)))
        metrics["bands_10db"]=bands
        if (run/"sparameters_discrete.csv").exists():
            discrete=read_csv(run/"sparameters_discrete.csv")
            fd=discrete["Freq [GHz]"]
            sd=discrete["dB(S(P1,P1)) (Real)"]
            # Compare complex S, since dB differences exaggerate very deep nulls.
            reference=a["re(S(P1,P1)) (Real)"]+1j*a["im(S(P1,P1)) (Real)"]
            actual=discrete["re(S(P1,P1)) (Real)"]+1j*discrete["im(S(P1,P1)) (Real)"]
            interp=np.interp(fd,f,reference.real)+1j*np.interp(fd,f,reference.imag)
            metrics["discrete_verification"]=dict(points=len(fd),
                    centered_window_worst_s11_db=float(sd[(fd>=5.725-1e-9)&(fd<=5.875+1e-9)].max()),
                    centered_window_all_samples_below_minus10=bool((sd[(fd>=5.725-1e-9)&(fd<=5.875+1e-9)]<-10).all()),
                    max_complex_s_difference=float(np.max(abs(actual-interp))),
                    max_db_difference=float(np.max(abs(sd-np.interp(fd,f,s)))))
        if result["parameters"]["kind"]=="divider":
            t2=a["dB(S(P2,P1)) (Real)"]
            t3=a["dB(S(P3,P1)) (Real)"]
            phase2=a["ang_deg(S(P2,P1)) (Real) [deg]"]
            phase3=a["ang_deg(S(P3,P1)) (Real) [deg]"]
            metrics["divider_58"]=dict(s21_db=float(np.interp(5.8,f,t2)),
                  s31_db=float(np.interp(5.8,f,t3)),
                  amplitude_imbalance_db=float(abs(np.interp(5.8,f,t2-t3))),
                  phase_imbalance_deg=float(abs(np.interp(5.8,f,(phase2-phase3+180)%360-180))),
                  output_isolation_db=float(-np.interp(5.8,f,a["dB(S(P2,P3)) (Real)"])))
    cuts=[]
    for phi in [0,90]:
        if not (run/f"farfield_phi{phi}.csv").exists():
            continue
        a=read_csv(run/f"farfield_phi{phi}.csv")
        th=a["Theta [deg]"]
        gain=a["dB(RealizedGainTotal) (Real)"]
        directivity=a["dB(DirTotal) (Real)"]
        g=a["dB(GainTotal) (Real)"]
        idx=np.argmax(gain)
        front=(th>=-90)&(th<=90)
        x=th[front]
        y=gain[front]
        main=np.argmax(y)
        nulls,_=find_peaks(-y)
        left=nulls[nulls<main]
        right=nulls[nulls>main]
        li=int(left[-1]) if len(left) else 0
        ri=int(right[0]) if len(right) else len(y)-1
        peaks,_=find_peaks(y)
        side=peaks[(peaks<li)|(peaks>ri)]
        sidelobe=float(y[main]-y[side].max()) if len(side) else None
        all_peaks,_=find_peaks(gain)
        if gain[0]>=gain[1] and gain[-1]>=gain[-2]:
            all_peaks=np.unique(np.append(all_peaks,0))
        all_nulls,_=find_peaks(-gain)
        al=all_nulls[all_nulls<idx]
        ar=all_nulls[all_nulls>idx]
        left_bound=int(al[-1]) if len(al) else 0
        right_bound=int(ar[0]) if len(ar) else len(gain)-1
        secondary=all_peaks[(all_peaks<left_bound)|(all_peaks>right_bound)]
        secondary_suppression=float(gain[idx]-gain[secondary].max()) if len(secondary) else None
        orth=a["dB(RealizedGainPhi) (Real)"]
        parallel=a["dB(RealizedGainTheta) (Real)"]
        cuts.append(dict(phi_deg=phi,peak_theta_deg=float(th[idx]),peak_realized_gain_dbi=float(gain[idx]),
                         broadside_gain_dbi=float(np.interp(0,th,gain)),
                         peak_directivity_dbi=float(directivity.max()),
                         radiation_efficiency_percent=float(100*10**((g[idx]-directivity[idx])/10)),
                         broadside_linear_pol_discrimination_db=float(abs(np.interp(0,th,orth)-np.interp(0,th,parallel))),
                         front_sidelobe_suppression_db=sidelobe,
                         secondary_lobe_suppression_including_back_db=secondary_suppression,
                         front_sidelobe_status="no_secondary_local_maximum" if sidelobe is None else "measured_between_first_nulls_and_horizon"))
    metrics["farfield_cuts"]=cuts
    if (run/"antenna_parameters.csv").exists():
        a=read_csv(run/"antenna_parameters.csv")
        metrics["antenna_58"]={key:float(a[key+" (Real)"][0])
            for key in ["AcceptedPower","IncidentPower","PeakDirectivity","PeakGain",
                        "PeakRealizedGain","RadiatedPower","RadiationEfficiency","TotalEfficiency"]}
    if (run/"farfield_full.csv").exists():
        a=read_csv(run/"farfield_full.csv")
        gain=a["dB(RealizedGainTotal) (Real)"]
        theta=a["Theta [deg]"]
        phi=a["Phi [deg]"]
        mask=theta>=0
        idx=np.flatnonzero(mask)[np.argmax(gain[mask])]
        metrics["full_sphere_peak"]=dict(theta_deg=float(theta[idx]),phi_deg=float(phi[idx]),
                                        realized_gain_dbi=float(gain[idx]))
    (run/"metrics.json").write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding="utf-8")
    return metrics


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("runs",nargs="+")
    args=p.parse_args()
    for run in args.runs:
        print(json.dumps(analyze(run),ensure_ascii=False,indent=2))
