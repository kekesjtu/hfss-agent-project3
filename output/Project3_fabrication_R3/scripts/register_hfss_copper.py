"""Register nominal screened RF copper against the native fabrication board."""
from pathlib import Path
import os
import json
import sys
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from shapely import make_valid
ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[2] if len(sys.argv)>2 else 'R3'
OUT=Path(os.environ['PROJECT3_BUILD_DIR']).resolve()
run=Path(sys.argv[1])
r=json.loads((run/'model_geometry.json').read_text(encoding='utf8'));p=r['parameters']
saved=r
ytop=p['y_bottom']+p['board_l']
def convert(q):return box(q['x']+28,ytop-q['y']-q['l'],q['x']+28+q['w'],ytop-q['y'])
model=unary_union([convert(q) for q in saved['top']]).difference(unary_union([convert(q) for q in saved['cuts']]))
data=json.loads((OUT/'diagnostics/native_copper.json').read_text())
native=max([make_valid(Polygon(q['outline'],q['holes'])) for q in data['F.Cu']],key=lambda q:q.area)
diff=model.symmetric_difference(native).area
assert model.difference(native.buffer(.000002)).area<1e-8
assert native.difference(model.buffer(.000002)).area<1e-8
result={'screened_model_run':str(run.resolve()),'model_full_rf_copper_mm2':model.area,'native_rf_copper_mm2':native.area,'symmetric_difference_mm2':diff,'coordinate_tolerance_mm':.000002,'passes':True,
        'scope':'Nominal RF top copper only, including antenna, matching section and connector signal land. Not the SMA body, ground stack or solver accuracy.'}
(OUT/'hfss_pcb_registration.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
