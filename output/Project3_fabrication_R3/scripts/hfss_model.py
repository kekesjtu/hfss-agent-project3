"""Build and solve the nominal R3 array with the official SMA component."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import traceback
import sys
import hashlib

os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"
os.environ["ANSYSEMSV_ROOT252"] = r"E:\Program Files\ANSYS Student\v252\AnsysEM"
from ansys.aedt.core import Desktop, Hfss, settings

settings.use_grpc_api = True
settings.grpc_secure_mode = False
settings.grpc_local = False
settings.enable_local_log_file = True

ROOT = Path(__file__).resolve().parents[3]
C0 = 299.792458  # mm GHz


def build_single(p):
    """Patch centred at (0, 0); feed line runs to the bottom board edge."""
    w, l, inset = p["patch_w"], p["patch_l"], p["inset"]
    wf, gap, yb = p["w50"], p["gap"], p["y_bottom"]
    top, cuts = [], []
    top.append(dict(name="Patch", x=-w / 2, y=-l / 2, w=w, l=l))
    top.append(dict(name="Feed", x=-wf / 2, y=yb,
                    w=wf, l=(-l / 2 + inset + 0.02) - yb))
    cuts.append(dict(name="InsetL", x=-wf / 2 - gap, y=-l / 2 - 0.01,
                     w=gap, l=inset + 0.01))
    cuts.append(dict(name="InsetR", x=wf / 2, y=-l / 2 - 0.01,
                     w=gap, l=inset + 0.01))
    if p.get('slot_l',0)>0:
        sw=p['slot_w'];base=p['slot_span'];y=-l/2+p['slot_y']
        cuts += [dict(name='USlotBase',x=-base/2,y=y,w=base,l=sw),
                 dict(name='USlotLeft',x=-base/2,y=y,w=sw,l=p['slot_l']),
                 dict(name='USlotRight',x=base/2-sw,y=y,w=sw,l=p['slot_l'])]
    return top, cuts


def build_array(p):
    """Corporate-fed 1x2 array, patch centres at y=0, x=+-spacing/2."""
    d = p["spacing"]
    w50, w70, gap = p["w50"], p["w70"], p["gap"]
    w, l, inset = p["patch_w"], p["patch_l"], p["inset"]
    tee, trans, py = p["tee"], p["trans"], -l / 2
    yb = p["y_bottom"]
    top, cuts = [], []
    wi = p.get("winput", w50)
    wb = p.get("wbranch", w50)
    top.append(dict(name="Input50", x=-wi / 2, y=yb,
                    w=wi, l=tee + w70 / 2 - yb))
    top.append(dict(name="Horizontal70", x=-d / 2 - w70 / 2, y=tee - w70 / 2,
                    w=d + w70, l=w70))
    for i, x in enumerate([-d / 2, d / 2]):
        top.append(dict(name=f"Transformer70_{i}", x=x - w70 / 2,
                        y=tee - w70 / 2, w=w70, l=trans - tee + w70))
        if abs(wb-w50)<1e-8:
            top.append(dict(name=f"Branch50_{i}", x=x - w50 / 2, y=trans,
                            w=w50, l=py + inset + 0.02 - trans))
        else:
            top.append(dict(name=f"BranchMatch_{i}",x=x-wb/2,y=trans,w=wb,l=py-trans+0.01))
            top.append(dict(name=f"InsetTongue_{i}",x=x-w50/2,y=py-0.01,w=w50,l=inset+0.03))
        if p['kind']=='divider':
            continue
        top.append(dict(name=f"Patch_{i}", x=x - w / 2, y=py, w=w, l=l))
        for side, name in [(-1, "L"), (1, "R")]:
            x0 = x + side * w50 / 2 + (-gap if side < 0 else 0)
            cuts.append(dict(name=f"InsetGap_{i}_{name}", x=x0,
                             y=py - 0.01, w=gap, l=inset + 0.01))
    if p.get("slot_l", 0) > 0 and p['kind']!='divider':
        for i, x in enumerate([-d / 2, d / 2]):
            sw, base, y = p["slot_w"], p["slot_span"], py + p["slot_y"]
            cuts.append(dict(name=f"USlotBase_{i}", x=x - base / 2, y=y,
                             w=base, l=sw))
            cuts.append(dict(name=f"USlotLeft_{i}", x=x - base / 2, y=y,
                             w=sw, l=p["slot_l"]))
            cuts.append(dict(name=f"USlotRight_{i}", x=x + base / 2 - sw, y=y,
                             w=sw, l=p["slot_l"]))
    return top, cuts


def add_copper(hfss, top, cuts, z, mode):
    metal = []
    for r in top:
        obj = hfss.modeler.create_rectangle("XY", [r["x"], r["y"], z],
                                            [r["w"], r["l"]], name=r["name"])
        metal.append(obj.name)
    if len(metal) > 1 and not hfss.modeler.unite(metal):
        raise RuntimeError("Copper union failed")
    copper = hfss.modeler[metal[0]]
    copper.name = "TopCopper"
    for r in cuts:
        cut = hfss.modeler.create_rectangle("XY", [r["x"], r["y"], z],
                                            [r["w"], r["l"]], name=r["name"])
        hfss.modeler.subtract(copper.name, cut.name, keep_originals=False)
    # Physical copper, with top surface at h+35um.
    assert hfss.modeler.thicken_sheet(copper.name,.035)
    copper.material_name='copper';copper.solve_inside=False
    return copper.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["single", "array", "divider"], default="single")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--length", type=float, default=12.17)
    ap.add_argument("--width", type=float, default=15.73)
    ap.add_argument("--inset", type=float, default=2.70)
    ap.add_argument("--slot-l", type=float, default=0.0)
    ap.add_argument("--slot-span", type=float, default=7.0)
    ap.add_argument("--slot-y", type=float, default=5.0)
    ap.add_argument("--slot-w", type=float, default=0.3)
    ap.add_argument("--height", type=float, default=0.2104)
    ap.add_argument("--epsr", type=float, default=4.4)
    ap.add_argument("--tand", type=float, default=0.02)
    ap.add_argument("--copper", choices=["pec", "finite", "shell", "two-sided"], default="shell")
    ap.add_argument("--w50", type=float, default=0.4)
    ap.add_argument("--w70", type=float, default=0.215)
    ap.add_argument("--gap", type=float, default=0.25)
    ap.add_argument("--wbranch", type=float, default=0.4)
    ap.add_argument("--winput", type=float, default=0.4)
    ap.add_argument("--margin", type=float, default=26.0)
    ap.add_argument("--mesh-length", type=float, default=0.0,
                    help="optional maximum surface mesh length on the top copper")
    ap.add_argument("--board-w", type=float, default=None)
    ap.add_argument("--board-l", type=float, default=None)
    ap.add_argument("--tee-dist", type=float, default=4.0,
                    help="array: T-junction distance from bottom board edge")
    ap.add_argument("--trans-dist", type=float, default=12.6,
                    help="array: transformer end distance from bottom edge")
    ap.add_argument("--passes", type=int, default=10)
    ap.add_argument("--min-passes", type=int, default=4)
    ap.add_argument("--min-converged", type=int, default=2,
                    help="consecutive passes below MaxDeltaS required to stop")
    ap.add_argument("--delta", type=float, default=0.03)
    ap.add_argument("--basis-order", type=int, default=2)
    ap.add_argument("--refine-percent", type=int, default=20)
    ap.add_argument("--audit-legacy-port", action="store_true")
    ap.add_argument("--symmetry-h", action="store_true", help="Use the x=0 magnetic symmetry plane; impedance multiplier 0.5")
    ap.add_argument("--fstart", type=float, default=5.4)
    ap.add_argument("--fstep", type=float, default=0.01)
    ap.add_argument("--fstop", type=float, default=6.2)
    ap.add_argument("--no-sweep", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="add a discrete 25 MHz sweep for interpolating-sweep verification")
    ap.add_argument("--band-fields", action="store_true",help="Save discrete fields and check patterns at both target-band edges")
    ap.add_argument("--farfield", action="store_true")
    ap.add_argument("--project", default=None)
    ap.add_argument('--launch-extension',type=float,default=6.0)
    ap.add_argument('--launch-match-width',type=float)
    ap.add_argument('--launch-match-length',type=float)
    ap.add_argument('--via-sides',type=int,default=0)
    args = ap.parse_args()
    args.verify=args.verify or args.band_fields
    assert not args.symmetry_h, 'Encrypted component is retained whole; use full geometry'
    if args.symmetry_h and args.kind=='divider':
        ap.error('The three-port divider requires the full geometry.')

    run = ROOT / "tmp" / (datetime.now().strftime("%Y-%m-%d") + "-r3-hfss") / datetime.now().strftime("%H%M%S_%f")
    run.mkdir(parents=True)
    settings.aedt_log_file = str(run / "aedt.log")
    os.chdir(run)
    source=Path(__file__).read_bytes()
    (run/'source_snapshot.py').write_bytes(source)
    (run/'invocation.json').write_text(json.dumps(dict(argv=sys.argv,source_sha256=hashlib.sha256(source).hexdigest()),indent=2))
    h = args.height
    board_w = args.board_w or (40.0 if args.kind == "single" else 56.0)
    board_l = args.board_l or (40.0 if args.kind == "single" else 52.17)
    y_bottom = -26.085 - args.launch_extension
    board_l = 52.17 + args.launch_extension
    p = dict(kind=args.kind, h=h, epsr=args.epsr, tand=args.tand,
             f0_ghz=5.8, spacing=C0 / 5.8 / 2,
             patch_w=args.width, patch_l=args.length, inset=args.inset,
             w50=args.w50, w70=args.w70, gap=args.gap, wbranch=args.wbranch, winput=args.winput,
             board_w=board_w, board_l=board_l, y_bottom=y_bottom,
             tee=y_bottom + args.tee_dist, trans=y_bottom + args.trans_dist,
             slot_l=args.slot_l, slot_span=args.slot_span,
             slot_y=args.slot_y, slot_w=args.slot_w,
             margin=args.margin, copper=args.copper,
             basis_order=args.basis_order, symmetry_h=args.symmetry_h)
    result = dict(parameters=p, run_directory=str(run), success=False, stages=[])

    def event(stage, **kwargs):
        result["stages"].append(dict(stage=stage, time=datetime.now().astimezone().isoformat(), **kwargs))
        (run / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(dict(stage=stage, **kwargs), ensure_ascii=False), flush=True)

    desktop = None
    try:
        event("starting")
        desktop = Desktop(version="2025.2", student_version=True, new_desktop=True,
                          non_graphical=False, close_on_exit=True)
        event("connected", pid=desktop.aedt_process_id)
        project = Path(args.project) if args.project else run / "Patch.aedt"
        hfss = Hfss(project=str(project),
                    design={'array':'PatchArray','single':'PatchElement','divider':'CorporateDivider'}[args.kind],
                    solution_type="Terminal", version="2025.2",
                    student_version=True, new_desktop=False,
                    aedt_process_id=desktop.aedt_process_id)
        hfss.modeler.model_units = "mm"
        material = hfss.materials.add_material("Course_FR4")
        material.permittivity = args.epsr
        material.dielectric_loss_tangent = args.tand

        xmin=0 if args.symmetry_h else -board_w/2
        substrate = hfss.modeler.create_box(
            [xmin, y_bottom, 0], [board_w/2-xmin, board_l, h],
            name="FR4", material="Course_FR4")

        original_p=dict(p, board_l=52.17, y_bottom=-26.085)
        top, cuts = build_array(original_p)
        top += [dict(name='J1SignalLand',x=-.45,y=y_bottom,w=.9,l=5.6),
                dict(name='LaunchTransition',x=-p['winput']/2,y=y_bottom+5.59,w=p['winput'],l=args.launch_extension-5.59+.01)]
        p['screening_scope']='Official encrypted SMA, physical 4-layer copper/FR4, hollow plated through vias, approximate rectangular solder joints'
        p['solder_top_gap_mm']=.05
        p['solder_signal_gap_mm']=.43
        p['solder_material']='tin'
        p['manufacturer_component']='Wurth 60312202114509 rev25a / terminal'
        p['connector_native_xform']='rotate X +90deg, translate [0,y_bottom,h+.035+.43]'
        p['input_reference_from_board_edge_mm']=-8.89

        if args.launch_match_width is not None:
            assert 0<args.launch_match_length<args.launch_extension-3.6
            interface=y_bottom+5.6+args.launch_match_length
            top=[q for q in top if q['name'] not in ['Input50','LaunchTransition']]
            top += [dict(name='LaunchMatchFront',x=-args.launch_match_width/2,y=y_bottom+5.59,
                        w=args.launch_match_width,l=args.launch_match_length+.01),
                    dict(name='LaunchMatchRear',x=-p['winput']/2,y=interface,
                        w=p['winput'],l=p['tee']+.25-interface)]
            p['input_matching_sections_mm']=[dict(position='connector_side',width=args.launch_match_width,length=args.launch_match_length),
                dict(position='antenna_side',width=p['winput'],length=args.launch_extension-3.6-args.launch_match_length)]

        def half_rectangles(items):
            return [dict(q,x=max(0,q['x']),w=q['x']+q['w']-max(0,q['x'])) for q in items if q['x']+q['w']>1e-8]
        copper_name = add_copper(hfss, half_rectangles(top) if args.symmetry_h else top,
            half_rectangles(cuts) if args.symmetry_h else cuts, h, args.copper)
        p['via_polygon_sides']=args.via_sides
        # Actual course stack: L2 top z=0; lower copper/FR4 down to -1.3408.
        lower=hfss.modeler.create_box([-board_w/2,y_bottom,-1.3058],
            [board_w,board_l,1.3058],name='LowerFR4',material='Course_FR4')
        ground=hfss.modeler.create_box([-board_w/2+.5,y_bottom+.5,-.0152],
            [board_w-1,board_l-1,.0152],name='GroundL2',material='copper')
        ground.solve_inside=False
        metal=[ground.name,copper_name]
        vias=[];holes=[];lands=[]
        for x in [-4.125,4.125]:
            for z in [h,-1.3408]:
                land=hfss.modeler.create_box([x-.825,y_bottom,z],[1.65,5.6,.035],name='J1Ground',material='copper')
                land.solve_inside=False;lands.append(land.name)
            for dy in [.9,1.9,2.9,3.9,4.9]:
                via=hfss.modeler.create_cylinder('Z',[x,y_bottom+dy,-1.3408],.175,h+.035+1.3408,name='ViaBarrel',material='copper',num_sides=args.via_sides)
                hole=hfss.modeler.create_cylinder('Z',[x,y_bottom+dy,-1.35],.15,h+.035+1.36,name='FinishedDrill',material='air',num_sides=args.via_sides)
                for z,t in [(h,.035),(-1.3408,.035),(-1.0954,.0152)]:
                    ring=hfss.modeler.create_cylinder('Z',[x,y_bottom+dy,z],.3,t,name='ViaAnnulus',material='copper',num_sides=args.via_sides)
                    hfss.modeler.subtract(ring.name,hole.name,keep_originals=True)
                    ring.solve_inside=False;metal.append(ring.name)
                hfss.modeler.subtract(via.name,hole.name,keep_originals=True)
                hfss.modeler.subtract([substrate.name,lower.name],via.name,keep_originals=True)
                hfss.modeler.subtract([substrate.name,lower.name,ground.name]+lands,hole.name,keep_originals=True)
                via.solve_inside=False;vias.append(via.name);holes.append(hole.name)
        ground_metal=[n for n in metal if n!=copper_name]+lands+vias
        assert hfss.modeler.unite(ground_metal)
        metal=[ground_metal[0],copper_name]
        hfss.modeler.subtract(lower.name,ground_metal[0],keep_originals=True)
        # Drill voids are filled by the enclosing air region. Do not retain
        # overlong temporary drill tools across solder contact surfaces.
        hfss.modeler.delete(holes);holes=[]
        # Component native axes: x across board; y vertical; z outward coax.
        vendor=Path(__file__).resolve().parent/'assets/vendor/60312202114509.a3dcomp'
        comp=hfss.modeler.insert_3d_component(str(vendor),name='SMA')
        if not comp:raise RuntimeError('Official Terminal component insertion failed')
        assert comp.rotate('X',90)
        pin_z=h+.035+.43
        assert comp.move([0,y_bottom,pin_z])
        component_parts=[o.name for o in comp.parts.values() if o.object_type=='Solid']
        # Upper shield feet are 0.38 mm below the flat signal pin; lower shield
        # contact is 2.11 mm below it. Nominal gaps: top .05, bottom .0938 mm.
        solder=[]
        for x in [-4.125,4.125]:
            upper=hfss.modeler.create_box([x-.635,y_bottom,h+.035],
                [1.27,4.8,.05],name='GroundSolderTop',material='tin')
            bottom_top=pin_z-2.11
            bottom=hfss.modeler.create_box([x-.635,y_bottom,bottom_top],
                [1.27,4.8,-1.3408-bottom_top],name='GroundSolderBottom',material='tin')
            solder.extend([upper.name,bottom.name])
        # Hand-soldered toe fillet at the centre-pin end: the land extends
        # 0.22 mm past the 5.38 mm pin. Avoid filling the entire pin underside.
        signal=hfss.modeler.create_box([-.37,y_bottom+5.38,h+.035],
            [.74,.22,.62],name='SignalSolder',material='tin')
        solder.append(signal.name)
        for name in solder:hfss.modeler[name].solve_inside=False
        event('official_sma_placed',component=comp.name,parts=component_parts,
            bbox=hfss.modeler.get_model_bounding_box(),excitations=hfss.excitation_names,
            top_ground_solder_gap_mm=.05,signal_solder_gap_mm=.43,bottom_ground_solder_gap_mm=.0938)

        port_name=hfss.excitation_names[0]
        assert len(hfss.excitation_names)==1,hfss.excitation_names
        hfss.edit_sources({port_name: ('1W','0deg')})

        m = args.margin
        air_xmin=0 if args.symmetry_h else -board_w/2-m
        air = hfss.modeler.create_box(
            [air_xmin, y_bottom - 8.89, -m],
            [board_w/2+m-air_xmin, board_l + m + 8.89, h + 2 * m],
            name="Air", material="air")
        # HFSS enclosing background volume: embedded materials take precedence.
        # Encrypted component parts cannot be Boolean tools and remain intact.

        bounds = [[air_xmin, board_w / 2 + m],
                  [y_bottom - 8.89, 26.085 + m],
                  [-m, h + m]]
        outer_faces = [f.id for f in air.faces if any(
            abs(f.center[axis] - edge) < 1e-6
            for axis in range(3) for edge in bounds[axis])]
        if args.symmetry_h:
            symfaces=[f.id for obj in [air,substrate] for f in obj.faces if abs(f.center[0])<1e-7]
            outer_faces=[i for i in outer_faces if i not in symfaces]
            assert hfss.assign_symmetry(symfaces,name='SymmetryH',is_perfect_e=False)
            assert hfss.set_impedance_multiplier(0.5)
        if len(outer_faces) < 6:
            raise RuntimeError(f"Unexpected radiation face count: {len(outer_faces)}")
        if not hfss.assign_radiation_boundary_to_faces(outer_faces, name="Radiation"):
            raise RuntimeError("Radiation assignment failed")
        if args.farfield:
            hfss.insert_infinite_sphere(phi_start=0, phi_stop=360, phi_step=5,
                                        theta_start=-180, theta_stop=180, theta_step=2,
                                        name="FullSphere")
        if args.mesh_length:
            hfss.mesh.assign_length_mesh(
                [copper_name], inside_selection=False,
                maximum_length=args.mesh_length, maximum_elements=None,
                name="ResolvePatch")

        setup = hfss.create_setup("Setup58")
        setup.props["Frequency"] = "5.8GHz"
        # Set the maximum first: a fresh PyAEDT setup starts with a small
        # maximum, so raising MinimumPasses first can violate AEDT's rule.
        setup.props["MaximumPasses"] = args.passes
        setup.props["MinimumPasses"] = min(args.min_passes, args.passes)
        setup.props["MinimumConvergedPasses"] = min(args.min_converged, args.passes)
        setup.props["MaxDeltaS"] = args.delta
        setup.props["PercentRefinement"] = args.refine_percent
        setup.props["BasisOrder"] = args.basis_order
        setup.props["SaveRadFieldsOnly"] = False
        setup.update()
        if not args.no_sweep:
            hfss.create_linear_step_sweep("Setup58", "GHz", args.fstart, args.fstop, args.fstep,
                                          name="Sweep", save_fields=False,
                                          save_rad_fields=False, sweep_type="Interpolating")
        if args.verify:
            hfss.create_linear_step_sweep("Setup58", "GHz", 5.65, 5.95, 0.025,
                                          name="DiscreteCheck", save_fields=args.band_fields,
                                          save_rad_fields=args.band_fields, sweep_type="Discrete")
        hfss.save_project()
        valid = hfss.validate_full_design(output_dir=str(run))
        event("model_saved", validation=str(valid[0])[:2000], top=top, cuts=cuts)
        if not valid[1]:
            raise RuntimeError("HFSS design validation failed")

        event("solve_started")
        solved = hfss.analyze_setup("Setup58", cores=4, tasks=1,
                                    use_auto_settings=False, blocking=True)
        hfss.save_project()
        event("solver_returned", solved=solved)
        hfss.export_convergence("Setup58", output_file=str(run / "convergence.txt"))
        hfss.export_mesh_stats("Setup58", output_file=str(run / "mesh_stats.txt"))
        hfss.export_profile("Setup58", output_file=str(run / "profile.txt"))
        (run / "desktop_messages.txt").write_text("\n".join(list(desktop.odesktop.GetMessages("", "", 0))), encoding="utf-8")
        if not solved:
            try:
                ref=hfss.post.get_solution_data(expressions=[f'dB(St({port_name},{port_name}))'],setup_sweep_name='Setup58 : LastAdaptive')
                if ref:ref.export_data_to_csv(str(run/'sparameters_last_adaptive_unverified.csv'))
            except Exception as reference_error:
                event('reference_export_failed',error=str(reference_error))
            raise RuntimeError('HFSS solve failed; see desktop_messages and mesh limit')

        sweep_name = "Setup58 : Sweep" if not args.no_sweep else "Setup58 : LastAdaptive"
        expressions = [f"dB(St({port_name},{port_name}))", f"re(St({port_name},{port_name}))", f"im(St({port_name},{port_name}))"]
        if args.kind=='divider':
            expressions += ["dB(S(P2,P1))","dB(S(P3,P1))","ang_deg(S(P2,P1))","ang_deg(S(P3,P1))","dB(S(P2,P3))"]
        data = hfss.post.get_solution_data(expressions=expressions,
                                           setup_sweep_name=sweep_name)
        if not data:
            raise RuntimeError("S parameter extraction failed")
        data.export_data_to_csv(str(run / "sparameters.csv"))
        if not args.no_sweep:
            hfss.export_touchstone(setup="Setup58", sweep="Sweep", output_file=str(run / ('divider.s3p' if args.kind=='divider' else "antenna.s1p")))
        if args.verify:
            discrete = hfss.post.get_solution_data(
                expressions=expressions, setup_sweep_name="Setup58 : DiscreteCheck")
            if discrete:
                discrete.export_data_to_csv(str(run / "sparameters_discrete.csv"))

        if args.farfield:
            full = hfss.post.get_solution_data(
                expressions=["dB(RealizedGainTotal)", "dB(RealizedGainTheta)", "dB(RealizedGainPhi)"],
                setup_sweep_name="Setup58 : LastAdaptive", report_category="Far Fields",
                context="FullSphere", primary_sweep_variable="Theta",
                variations={"Freq": ["5.8GHz"], "Phi": ["All"], "Theta": ["All"]})
            if full:
                full.export_data_to_csv(str(run / "farfield_full.csv"))
            if args.band_fields:
                for freq in [5.725,5.8,5.875]:
                    ff=hfss.post.get_solution_data(
                        expressions=['dB(RealizedGainTotal)','dB(RealizedGainTheta)','dB(RealizedGainPhi)'],
                        setup_sweep_name='Setup58 : DiscreteCheck',report_category='Far Fields',
                        context='FullSphere',primary_sweep_variable='Theta',
                        variations={'Freq':[str(freq)+'GHz'],'Phi':['All'],'Theta':['All']})
                    if not ff:raise RuntimeError(f'Missing fields at {freq} GHz')
                    ff.export_data_to_csv(str(run/f'farfield_full_{freq:.3f}.csv'))
            for phi in [0, 90]:
                ff = hfss.post.get_solution_data(
                    expressions=["dB(RealizedGainTotal)", "dB(GainTotal)", "dB(DirTotal)",
                                 "dB(RealizedGainTheta)", "dB(RealizedGainPhi)"],
                    setup_sweep_name="Setup58 : LastAdaptive", report_category="Far Fields",
                    context="FullSphere", primary_sweep_variable="Theta",
                    variations={"Freq": ["5.8GHz"], "Phi": [str(phi) + "deg"], "Theta": ["All"]})
                if not ff:
                    raise RuntimeError(f"Far field extraction failed: phi={phi}")
                ff.export_data_to_csv(str(run / f"farfield_phi{phi}.csv"))
            ap_report = hfss.post.reports_by_category.antenna_parameters(
                expressions=["PeakDirectivity", "PeakGain", "PeakRealizedGain",
                             "RadiatedPower", "AcceptedPower", "IncidentPower",
                             "RadiationEfficiency", "TotalEfficiency"],
                setup="Setup58 : LastAdaptive", infinite_sphere="FullSphere")
            ap_report.variations = {"Freq": ["5.8GHz"]}
            ap = ap_report.get_solution_data()
            if ap:
                ap.export_data_to_csv(str(run / "antenna_parameters.csv"))

        result["success"] = True
        event("passed")
    except Exception as exc:
        if desktop:
            (run/"desktop_messages.txt").write_text("\n".join(desktop.odesktop.GetMessages("","",0)),encoding="utf8")
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        event("failed", error=str(exc))
        traceback.print_exc()
    finally:
        if desktop is not None:
            try:
                desktop.release_desktop(close_projects=True, close_on_exit=True)
                event("closed")
            except Exception as exc:
                result["cleanup_error"] = str(exc)
        (run / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("RUN=" + str(run), flush=True)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
