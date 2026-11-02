"""Build the fabrication revision; run with KiCad's bundled Python.

The course RF geometry is a real, connected custom copper pad, not decorative
graphics. Connector land dimensions follow Wurth 60312202114509 sheet 1.
"""
from pathlib import Path
import os
import argparse
import csv
import json
import re
import shutil
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent / 'assets/rf_template'
ap=argparse.ArgumentParser();ap.add_argument('--revision',default='R3');ap.add_argument('--extension',type=float,default=6.0);ap.add_argument('--match-width',type=float)
ap.add_argument('--launch-match-width',type=float);ap.add_argument('--launch-match-length',type=float)
args=ap.parse_args()
OUT = Path(os.environ['PROJECT3_BUILD_DIR']).resolve()
OUT.mkdir(parents=True, exist_ok=True)
NAME = 'Project3_array_'+args.revision
W, OLD_L, EXT = 56.0, 52.17, args.extension
L = OLD_L + EXT
MM = pcb.FromMM
def xy(x, y): return pcb.VECTOR2I(MM(x), MM(y))
def layers(*ids):
    s=pcb.LSET()
    for layer in ids:s.AddLayer(layer)
    return s
def rect_poly(x0,y0,x1,y1):
    chain=pcb.SHAPE_LINE_CHAIN()
    for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]: chain.Append(xy(x,y))
    chain.SetClosed(True)
    poly=pcb.SHAPE_POLY_SET();poly.AddOutline(chain)
    return poly

board=pcb.BOARD()
board.SetCopperLayerCount(4)
board.GetDesignSettings().SetCopperLayerCount(4)
board.GetDesignSettings().SetBoardThickness(MM(1.6))
rf=pcb.NETINFO_ITEM(board,'RF',1);gnd=pcb.NETINFO_ITEM(board,'GND',2)
board.Add(rf);board.Add(gnd)
old=pcb.LoadBoard(str(SOURCE/'Project3_array.kicad_pcb'))
original=next(s for s in old.GetDrawings() if s.GetLayer()==pcb.F_Cu).GetPolyShape()
copper=pcb.SHAPE_POLY_SET();copper.BooleanAdd(original)
if args.match_width:
    # Preserve radiator, slots, divider and branch geometry; replace only the
    # center input below the T junction with the synthesized matching section.
    copper.BooleanSubtract(rect_poly(27.4,50.42,28.6,52.18))
    copper.BooleanAdd(rect_poly(28-args.match_width/2,50.17,28+args.match_width/2,L-5.59))
    if args.launch_match_width is not None:
        assert 0<args.launch_match_length<EXT-3.6
        interface_y=L-5.6-args.launch_match_length
        half=max(args.match_width,args.launch_match_width)/2+.000002
        copper.BooleanSubtract(rect_poly(28-half,interface_y,28+half,L-5.59))
        copper.BooleanAdd(rect_poly(28-args.launch_match_width/2,interface_y,28+args.launch_match_width/2,L-5.59))
else:
    taper=pcb.SHAPE_LINE_CHAIN()
    for x,y in [(27.46,52.16),(28.54,52.16),(28.45,52.58),(27.55,52.58)]: taper.Append(xy(x,y))
    taper.SetClosed(True)
    tp=pcb.SHAPE_POLY_SET();tp.AddOutline(taper);copper.BooleanAdd(tp)
copper.Simplify()
assert copper.OutlineCount()==1

antenna=pcb.FOOTPRINT(board);antenna.SetReference('ANT1');antenna.SetValue('5.8GHz_1x2_Uslot_Array')
antenna.SetFPIDAsString('Project3_RF:Array_1x2_Uslot_'+args.revision)
antenna.SetAttributes(pcb.FP_SMD | pcb.FP_EXCLUDE_FROM_BOM | pcb.FP_EXCLUDE_FROM_POS_FILES | pcb.FP_BOARD_ONLY)
antenna.SetPosition(xy(28,52.0));antenna.Reference().SetVisible(False);antenna.Value().SetVisible(False)
pad=pcb.PAD(antenna);pad.SetNumber('1');pad.SetAttribute(pcb.PAD_ATTRIB_SMD)
pad.SetShape(pcb.PAD_SHAPE_CUSTOM);pad.SetAnchorPadShape(pcb.F_Cu,pcb.PAD_SHAPE_RECT)
pad.SetSize(xy(.2,.2));pad.SetLayerSet(layers(pcb.F_Cu));pad.SetPosition(xy(28,52))
local=pcb.SHAPE_POLY_SET();local.BooleanAdd(copper);local.Move(xy(-28,-52))
pad.AddPrimitivePoly(pcb.F_Cu,local,0,True);pad.SetNet(rf);antenna.Add(pad);board.Add(antenna)

connector=pcb.FOOTPRINT(board);connector.SetReference('J1');connector.SetValue('60312202114509')
connector.SetFPIDAsString('Project3_RF:SMA_Wurth_60312202114509_EdgeMount')
connector.SetAttributes(pcb.FP_SMD)
# Datum: board edge, connector centerline. +Y points outside the board.
connector.SetPosition(xy(28,L))
connector.Reference().SetPosition(xy(35,L-3));connector.Reference().SetTextSize(xy(1,1));connector.Reference().SetLayer(pcb.B_SilkS);connector.Reference().SetMirrored(True)
connector.Value().SetVisible(False)
def smd(number,x,y,w,h,layer,net):
    p=pcb.PAD(connector);p.SetNumber(number);p.SetAttribute(pcb.PAD_ATTRIB_SMD)
    p.SetShape(pcb.PAD_SHAPE_RECT);p.SetSize(xy(w,h));p.SetPosition(xy(x,y))
    # No stencil apertures: connector is soldered on both board faces.
    ls=layers(layer,pcb.F_Mask if layer==pcb.F_Cu else pcb.B_Mask)
    p.SetLayerSet(ls);p.SetNet(net);connector.Add(p)
    return p
# Overall width 9.9, clear span between ground lands 6.6 -> width 1.65.
smd('1',28,L-2.8,.9,5.6,pcb.F_Cu,rf)
for x in [28-4.125,28+4.125]:
    for layer in [pcb.F_Cu,pcb.B_Cu]: smd('2',x,L-2.8,1.65,5.6,layer,gnd)
def fp_line(fp,a,b,layer,width=.1):
    s=pcb.PCB_SHAPE(fp);s.SetShape(pcb.SHAPE_T_SEGMENT);s.SetStart(xy(*a));s.SetEnd(xy(*b));s.SetLayer(layer);s.SetWidth(MM(width));fp.Add(s)
for layer in [pcb.F_CrtYd,pcb.B_CrtYd]:
    for a,b in [((22.55,L-6.1),(33.45,L-6.1)),((33.45,L-6.1),(33.45,L+9.6)),((33.45,L+9.6),(22.55,L+9.6)),((22.55,L+9.6),(22.55,L-6.1))]:fp_line(connector,a,b,layer,.05)
for a,b in [((23.24,L-5.38),(23.24,L+1.27)),((23.24,L+1.27),(32.76,L+1.27)),((32.76,L+1.27),(32.76,L-5.38))]:fp_line(connector,a,b,pcb.F_Fab)
# Manufacturer model is registered to its pad-centre datum. Our placement datum
# is the board edge, 2.8 mm farther out. KiCad's model Y axis opposes board Y.
model_dir=OUT/'Project3_RF.3dshapes';model_dir.mkdir(exist_ok=True)
shutil.copy2(Path(__file__).resolve().parent/'assets/vendor/kicad/J_Wurth_WR-SMA_60312202114509.step',model_dir/'SMA_60312202114509.step')
model=pcb.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/Project3_RF.3dshapes/SMA_60312202114509.step'
model.m_Offset=pcb.VECTOR3D(0,2.8,0);connector.Add3DModel(model)
for a,b in [((24.825,L+1.27),(24.825,L+8.89)),((24.825,L+8.89),(31.175,L+8.89)),((31.175,L+8.89),(31.175,L+1.27))]:fp_line(connector,a,b,pcb.F_Fab)
board.Add(connector)

via_positions=[]
for x in [23.875,32.125]:
    for y in [L-4.9,L-3.9,L-2.9,L-1.9,L-.9]:
        v=pcb.PCB_VIA(board);v.SetPosition(xy(x,y));v.SetWidth(MM(.6));v.SetDrill(MM(.3))
        v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(gnd);board.Add(v)
        via_positions.append([x,y])
# Plane is a connected zone, with ordinary copper-edge setback everywhere.
zone=pcb.ZONE(board);zone.SetLayer(pcb.In1_Cu);zone.SetNet(gnd)
zone.SetLocalClearance(MM(.2));zone.SetMinThickness(MM(.1));zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
plane_outline=zone.Outline();plane_outline.NewOutline()
for x,y in [(.5,.5),(W-.5,.5),(W-.5,L-.5),(.5,L-.5)]:plane_outline.Append(xy(x,y))
board.Add(zone)

for a,b in [((0,0),(W,0)),((W,0),(W,L)),((W,L),(0,L)),((0,L),(0,0))]:
    s=pcb.PCB_SHAPE(board);s.SetShape(pcb.SHAPE_T_SEGMENT);s.SetStart(xy(*a));s.SetEnd(xy(*b));s.SetLayer(pcb.Edge_Cuts);s.SetWidth(MM(.05));board.Add(s)
# Courtyard denotes the planar antenna's protected region. The short feed
# transition outside it intentionally joins J1; ANT1 is board copper, no body.
for a,b in [((2.5,19.5),(53.5,19.5)),((53.5,19.5),(53.5,51.9)),((53.5,51.9),(2.5,51.9)),((2.5,51.9),(2.5,19.5))]:fp_line(antenna,a,b,pcb.F_CrtYd,.05)
# Top remains completely without soldermask, as in the RF design.
mask=pcb.PCB_SHAPE(board);mask.SetShape(pcb.SHAPE_T_RECT);mask.SetStart(xy(0,0));mask.SetEnd(xy(W,OLD_L));mask.SetLayer(pcb.F_Mask);mask.SetFilled(True);mask.SetWidth(0);board.Add(mask)
mask_half_width=max(.6,max(args.match_width or 1.08,args.launch_match_width or 0)/2+.1)
transition_mask=pcb.PCB_SHAPE(board);transition_mask.SetShape(pcb.SHAPE_T_RECT);transition_mask.SetStart(xy(28-mask_half_width,52.1));transition_mask.SetEnd(xy(28+mask_half_width,L-5.5));transition_mask.SetLayer(pcb.F_Mask);transition_mask.SetFilled(True);transition_mask.SetWidth(0);board.Add(transition_mask)
for text,x,y,layer in [('PROJECT3 '+args.revision+'  5.8GHz',28,3,pcb.B_SilkS),('1.6mm 4L  L1-L2=0.2104mm',28,5,pcb.B_SilkS),('J1: SMA 60312202114509',28,8,pcb.B_SilkS)]:
    t=pcb.PCB_TEXT(board);t.SetText(text);t.SetPosition(xy(x,y));t.SetTextSize(xy(1,1));t.SetTextThickness(MM(.15));t.SetLayer(layer);t.SetMirrored(True);board.Add(t)

lib=OUT/'Project3_RF.pretty';lib.mkdir(exist_ok=True)
# FootprintSave expects coordinates in board space and normalizes on save.
plugin=pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP)
plugin.FootprintSave(str(lib),antenna)
plugin.FootprintSave(str(lib),connector)
(OUT/'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "Project3_RF")(type "KiCad")(uri "${KIPRJMOD}/Project3_RF.pretty")(options "")(descr "Course array and datasheet-derived SMA"))\n)\n',encoding='utf8')
project=json.loads((SOURCE/'Project3_array.kicad_pro').read_text(encoding='utf8'))
project['meta']['filename']=NAME+'.kicad_pro'
settings=project['board']['design_settings']
settings['rules'].update(min_clearance=.2,min_copper_edge_clearance=0,min_track_width=.2,min_via_diameter=.6,min_through_hole_diameter=.3,min_via_annular_width=.15,min_silk_clearance=.15)
settings['rule_severities']['missing_courtyard']='warning'
settings['drc_exclusions']=[]
(OUT/(NAME+'.kicad_pro')).write_text(json.dumps(project,indent=2),encoding='utf8')
(OUT/(NAME+'.kicad_dru')).write_text('''(version 1)
(rule "Ordinary copper must remain 0.5 mm from every board edge"
  (constraint edge_clearance (min 0.5mm)))
(rule "J1 datasheet end-launch lands only; intentional copper to routed edge"
  (condition "(A.Type == 'Pad' && A.memberOfFootprint('J1')) || (B.Type == 'Pad' && B.memberOfFootprint('J1'))")
  (constraint edge_clearance (min -0.05mm)))
''',encoding='utf8')
board.BuildConnectivity()
pcb.ZONE_FILLER(board).Fill(board.Zones())
path=OUT/(NAME+'.kicad_pcb');pcb.SaveBoard(str(path),board)
# Course sheet 12: outer 35um, inner 15.2um, core 1.065mm.
stack='''(stackup
  (layer "F.Cu" (type "copper") (thickness 0.035))
  (layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4 7628x1") (epsilon_r 4.4) (loss_tangent 0.02))
  (layer "In1.Cu" (type "copper") (thickness 0.0152))
  (layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
  (layer "In2.Cu" (type "copper") (thickness 0.0152))
  (layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4 7628x1") (epsilon_r 4.4) (loss_tangent 0.02))
  (layer "B.Cu" (type "copper") (thickness 0.035))
  (copper_finish "OSP") (dielectric_constraints yes))'''
txt=path.read_text(encoding='utf8').replace('\t(setup\n','\t(setup\n'+stack+'\n',1)
path.write_text(txt,encoding='utf8')
reopened=pcb.LoadBoard(str(path))
# LoadBoard/SaveBoard share KiCad's project manager; write the deliberate rules
# after these calls so the source project's defaults cannot overwrite them.
(OUT/(NAME+'.kicad_pro')).write_text(json.dumps(project,indent=2),encoding='utf8')
ant=next(f for f in reopened.GetFootprints() if f.GetReference()=='ANT1')
check=next(iter(ant.Pads())).GetEffectivePolygon(pcb.F_Cu)
delta=pcb.SHAPE_POLY_SET();delta.BooleanAdd(copper);delta.BooleanXor(check)
assert abs(delta.Area())<1, f'Custom-pad copper changed {delta.Area()}'
baseline=pcb.SHAPE_POLY_SET();baseline.BooleanAdd(check)
baseline.BooleanSubtract(rect_poly(0,OLD_L,W,L+.1))
original_diff=pcb.SHAPE_POLY_SET();original_diff.BooleanAdd(original);original_diff.BooleanXor(baseline)
protected_diff=pcb.SHAPE_POLY_SET();protected_diff.BooleanAdd(original_diff)
if args.match_width:
    allowed_half_width=max(.6,max(args.match_width,args.launch_match_width or 0)/2+.000002)
    protected_diff.BooleanSubtract(rect_poly(28-allowed_half_width,50.419999,28+allowed_half_width,52.18))
assert abs(protected_diff.Area())<1, 'Protected antenna/divider copper changed'
data=dict(board_file=path.name,kicad_version=pcb.GetBuildVersion(),board_size_mm=[W,L],original_board_size_mm=[W,OLD_L],extension_mm=EXT,
 connector=dict(manufacturer='Wurth Elektronik',mpn='60312202114509',interface='SMA jack 50 ohm',board_thickness_mm=1.6,signal_pad_mm=[.9,5.6],ground_pad_mm=[1.65,5.6],ground_centers_mm=[-4.125,4.125],land_pattern_source='https://www.we-online.com/components/products/datasheet/60312202114509.pdf'),
 nominal_board_thickness_mm=1.6,stackup_sum_mm=1.5862,course_stackup_preserved=True,
 original_antenna_copper_difference_mm2=original_diff.Area()/1e12,protected_antenna_divider_copper_difference_mm2=protected_diff.Area()/1e12,input_matching_width_mm=args.match_width,input_matching_length_mm=(L-5.6-50.17) if args.match_width else None,roundtrip_difference_mm2=delta.Area()/1e12,
 antenna_copper_mm2=copper.Area()/1e12,ordinary_copper_edge_clearance_mm=.5,
 edge_rule_exception='Only J1 physical connector pads, exactly per end-launch land pattern; no DRC exclusions',
 vias=dict(count=len(via_positions),drill_mm=.3,pad_mm=.6,positions_mm=via_positions),
 rf_validation='not_yet_revalidated_with_connector',fabricator_stackup_confirmation=False,manufacturing_release=False)
if args.launch_match_width is not None:
    data['input_matching_sections_mm']=[dict(position='connector_side',width=args.launch_match_width,length=args.launch_match_length),
        dict(position='antenna_side',width=args.match_width,length=EXT-3.6-args.launch_match_length)]
(OUT/'design_validation.json').write_text(json.dumps(data,indent=2),encoding='utf8')
with (OUT/'BOM.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['Reference','Quantity','Manufacturer','MPN','Description','Assembly'])
    w.writerow(['J1',1,'Wurth Elektronik','60312202114509','50 ohm SMA female end launch; 1.6 mm PCB','Solder center and four ground feet; no stencil'])
with (OUT/'stackup.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['Top to bottom','Material','Thickness_mm','Function'])
    for row in [('F.Cu','Copper',.035,'RF array and J1'),('PP1','FR4 7628x1',.2104,'Critical RF dielectric'),('In1.Cu','Copper',.0152,'RF reference ground'),('Core','FR4',1.065,'Course core'),('In2.Cu','Copper',.0152,'Only via annuli; no plane'),('PP2','FR4 7628x1',.2104,'Course lower prepreg'),('B.Cu','Copper',.035,'J1 ground lands and via annuli')]:w.writerow(row)
shutil.copy2(Path(__file__).resolve().parent/'assets/vendor/connector_datasheet.pdf',OUT/'connector_datasheet.pdf')
print(json.dumps(data,indent=2))
