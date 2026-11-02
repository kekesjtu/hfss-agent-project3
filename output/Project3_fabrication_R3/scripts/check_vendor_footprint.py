"""Compare native J1 copper lands to manufacturer's official KiCad library."""
from pathlib import Path
import os
import hashlib,json,sys
import pcbnew as p
ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[1] if len(sys.argv)>1 else 'R3'
OUT=Path(os.environ['PROJECT3_BUILD_DIR']).resolve()
VENDOR=Path(__file__).resolve().parent/'assets/vendor/kicad'
official=p.FootprintLoad(str(VENDOR),'J_Wurth_WR-SMA_60312202114509')
board=p.LoadBoard(str(OUT/('Project3_array_'+REV+'.kicad_pcb')))
actual=next(f for f in board.GetFootprints() if f.GetReference()=='J1')
origin=actual.GetPosition()
official.SetPosition(p.VECTOR2I(origin.x,origin.y-p.FromMM(2.8)))
def rows(fp):
    result=[]
    for pad in fp.Pads():
        layer=p.F_Cu if pad.IsOnLayer(p.F_Cu) else p.B_Cu
        box=pad.GetEffectivePolygon(layer).BBox()
        result.append(dict(number=pad.GetNumber(),layer=board.GetLayerName(layer),
            bounds_mm=[p.ToMM(v) for v in [box.GetX(),box.GetY(),box.GetRight(),box.GetBottom()]]))
    return sorted(result,key=lambda r:(r['number'],r['layer'],r['bounds_mm']))
a,b=rows(actual),rows(official)
assert len(a)==len(b)==5
maxdiff=max(abs(x-y) for r,s in zip(a,b) for x,y in zip(r['bounds_mm'],s['bounds_mm']))
assert maxdiff<1e-6,(a,b)
data=dict(passed=True,official_land_count=5,maximum_coordinate_difference_mm=maxdiff,
    actual_lands=a,official_lands=b,board_edge_datum_offset_mm=2.8,
    model_offset_xyz_mm=[0,2.8,0],model_rotation_xyz_deg=[0,0,0],
    source='https://www.we-online.com/components/products/download/KiCad_WR-SMA%20%28rev26a%29.zip',
    official_footprint_sha256=hashlib.sha256((VENDOR/'J_Wurth_WR-SMA_60312202114509.kicad_mod').read_bytes()).hexdigest(),
    model_sha256=hashlib.sha256((OUT/'Project3_RF.3dshapes/SMA_60312202114509.step').read_bytes()).hexdigest(),
    assembly_step_contains_j1="'J1'" in (OUT/'assembly.step').read_text())
assert data['assembly_step_contains_j1']
(OUT/'vendor_footprint_validation.json').write_text(json.dumps(data,indent=2),encoding='utf8')
print(json.dumps(data,indent=2))
