"""Independent Gerber/Excellon round trip and fabrication previews."""
from pathlib import Path
import os
import json
import sys
import warnings
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM
from shapely import make_valid
from shapely.geometry import Polygon, GeometryCollection, Point, box
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon, Rectangle, Circle

ROOT=Path(__file__).resolve().parents[3]
REV=sys.argv[1] if len(sys.argv)>1 else 'R3'
OUT=Path(os.environ['PROJECT3_BUILD_DIR']).resolve()
NAME='Project3_array_'+REV
native=json.loads((OUT/'diagnostics/native_copper.json').read_text())
design=json.loads((OUT/'design_validation.json').read_text())
L=design['board_size_mm'][1]
geoms={};report={'layers':{},'parser':'gerbonara 1.6.3 + shapely 2.2.0','curve_tolerance_mm':.006}
def polygons(g):
    if g.geom_type=='Polygon':return [g]
    return [p for part in getattr(g,'geoms',[]) for p in polygons(part)]
def from_native(records):return unary_union([make_valid(Polygon(x['outline'],x['holes'])) for x in records])
def from_gerber(path):
    f=GerberFile.open(path);g=GeometryCollection()
    for obj in f.objects:
        for primitive in obj.to_primitives(MM):
            poly=primitive.to_arc_poly().approximate_arcs(max_error=.000001)
            # Gerber Y is upward, KiCad board coordinates are downward.
            part=make_valid(Polygon([(x,-y) for x,y in poly.outline]))
            g=g.union(part) if primitive.polarity_dark else g.difference(part)
    return g
for name,ext in [('F.Cu','F_Cu.gtl'),('In1.Cu','In1_Cu.g1'),('In2.Cu','In2_Cu.g2'),('B.Cu','B_Cu.gbl')]:
    actual=from_gerber(OUT/'Gerber'/f'{NAME}-{ext}');expected=from_native(native[name]);geoms[name]=actual
    difference=actual.symmetric_difference(expected).area
    ok=actual.difference(expected.buffer(.006)).area<1e-8 and expected.difference(actual.buffer(.006)).area<1e-8
    assert ok,(name,difference)
    report['layers'][name]={'native_area_mm2':expected.area,'gerber_area_mm2':actual.area,'symmetric_difference_mm2':difference,'within_curve_tolerance':ok,'islands_before_drilling':len(polygons(actual))}
rf_actual=max(polygons(geoms['F.Cu']),key=lambda g:g.area)
rf_expected=max(polygons(from_native(native['F.Cu'])),key=lambda g:g.area)
report['rf_gerber_native_difference_mm2']=rf_actual.symmetric_difference(rf_expected).area
assert report['rf_gerber_native_difference_mm2']<1e-5
assert len(rf_actual.interiors)==2,'Two U slots must survive CAM export'
with warnings.catch_warnings(record=True) as warning_list:
    drills=ExcellonFile.open(OUT/'Gerber'/f'{NAME}.drl')
positions=sorted((round(o.x,6),round(-o.y,6),round(o.aperture.diameter,6)) for o in drills.objects)
expected_positions=sorted((round(x,6),round(y,6),.3) for x,y in design['vias']['positions_mm'])
assert positions==expected_positions
report['drills']={'count':len(positions),'diameter_mm':.3,'positions_match_native':True,'parser_warnings':[str(w.message) for w in warning_list]}
assert max(abs(a-b) for a,b in zip(geoms['In1.Cu'].bounds,(.5,.5,55.5,L-.5)))<.001,geoms['In1.Cu'].bounds
report['l2_ground_bounds_mm']=list(geoms['In1.Cu'].bounds)
assert rf_actual.intersection(box(0,L-5.6,56,L-5.59)).area>0
drc=json.loads((OUT/'drc.json').read_text(encoding='utf8'))
assert not drc['violations'] and not drc['unconnected_items']
control=json.loads((OUT/'diagnostics/edge_rule_negative_control.json').read_text(encoding='utf8'))
assert any(x['type']=='copper_edge_clearance' for x in control['violations'])
report['drc']={'violations':0,'unconnected':0,'ordinary_edge_rule_negative_control_passed':True,'excluded_violations':0}
(OUT/'cam_validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')

def draw(ax,g,color):
    for poly in polygons(g):
        ax.add_patch(PatchPolygon(list(poly.exterior.coords),fc=color,ec='none'))
        for hole in poly.interiors:ax.add_patch(PatchPolygon(list(hole.coords),fc='#e9f1eb',ec='none'))
def setup(ax,xlim=(-2,58),ylim=None):
    if ylim is None:ylim=(L+4,-2)
    ax.add_patch(Rectangle((0,0),56,L,fc='#e9f1eb',ec='#243c35',lw=1))
    ax.set(xlim=xlim,ylim=ylim,aspect='equal',xlabel='x / mm',ylabel='y / mm')
fig,axs=plt.subplots(1,3,figsize=(13,5.5),layout='constrained')
for ax,name in zip(axs,['F.Cu','In1.Cu','B.Cu']):
    setup(ax);draw(ax,geoms[name],'#b77a2d')
    for x,y,d in positions:ax.add_patch(Circle((x,y),d/2,fc='white',ec='#233b33',lw=.4))
    ax.set_title(name+' / actual exported Gerber')
fig.suptitle(f'Project3 {REV} | 56 x {L:g} mm | SMA 60312202114509',fontsize=13)
fig.savefig(OUT/'fabrication_preview.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,6),layout='constrained');setup(ax,(20.5,35.5),(L+1.8,48.5));draw(ax,geoms['F.Cu'],'#b77a2d')
for x,y,d in positions:ax.add_patch(Circle((x,y),d/2,fc='white',ec='#233b33',lw=.8))
ax.axhline(52.17,color='#698879',ls='--',lw=1);ax.text(21,51.8,'Original board edge',fontsize=10)
ax.annotate('0.9 x 5.6 mm RF land',xy=(28,L-3),xytext=(20.9,49.3),arrowprops={'arrowstyle':'->'},fontsize=10)
ax.annotate('10 plated vias / 0.3 mm drill',xy=(32.125,L-1.9),xytext=(24,L+1.2),arrowprops={'arrowstyle':'->'},fontsize=10)
ax.set_title('SMA launch lands / top view / dimensions in mm')
fig.savefig(OUT/'connector_detail.png',dpi=180);plt.close(fig)
print(json.dumps(report,indent=2))
