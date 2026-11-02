"""Extract native copper polygons for independent CAM comparison (KiCad Python)."""
from pathlib import Path
import os
import json
import shutil
import sys
import pcbnew as p
ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[1] if len(sys.argv)>1 else 'R3'
OUT=Path(os.environ['PROJECT3_BUILD_DIR']).resolve()
NAME='Project3_array_'+REV
b=p.LoadBoard(str(OUT/(NAME+'.kicad_pcb')))
data={}
for name,layer in [('F.Cu',p.F_Cu),('In1.Cu',p.In1_Cu),('In2.Cu',p.In2_Cu),('B.Cu',p.B_Cu)]:
    poly=p.SHAPE_POLY_SET();b.ConvertBrdLayerToPolygonalContours(layer,poly);poly.Simplify()
    def points(c):return [[c.CPoint(i).x/1e6,c.CPoint(i).y/1e6] for i in range(c.PointCount())]
    data[name]=[dict(outline=points(poly.Outline(i)),holes=[points(poly.Hole(i,j)) for j in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())]
diag=OUT/'diagnostics';diag.mkdir(exist_ok=True)
(diag/'native_copper.json').write_text(json.dumps(data),encoding='utf8')
# Negative control: verify the 0.5 mm ordinary-copper edge rule is active.
s=p.PCB_SHAPE(b);s.SetShape(p.SHAPE_T_RECT);s.SetLayer(p.F_Cu);s.SetStart(p.VECTOR2I(p.FromMM(1),p.FromMM(.1)));s.SetEnd(p.VECTOR2I(p.FromMM(2),p.FromMM(.2)));s.SetFilled(True);s.SetWidth(0);s.SetNetCode(1);b.Add(s)
control=diag/(NAME+'.kicad_pcb');p.SaveBoard(str(control),b)
for ext in ['.kicad_pro','.kicad_dru']:shutil.copy2(OUT/(NAME+ext),diag/(NAME+ext))
print({k:len(v) for k,v in data.items()})
