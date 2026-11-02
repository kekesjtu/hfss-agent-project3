"""Verify the local agent -> PyAEDT -> HFSS -> solve -> export chain."""
import argparse
import csv
from datetime import datetime
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parent
os.environ["PYAEDT_USE_PRE_GRPC_ARGS"] = "True"
os.environ.setdefault("ANSYSEMSV_ROOT252", r"E:\Program Files\ANSYS Student\v252\AnsysEM")

from ansys.aedt.core import Desktop, Hfss, settings

settings.use_grpc_api = True
settings.grpc_secure_mode = False
settings.grpc_local = False
settings.enable_local_log_file = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-solve", action="store_true")
    parser.add_argument("--non-graphical", action="store_true")
    args = parser.parse_args()
    work = ROOT.parent / "tmp" / (datetime.now().strftime("%Y-%m-%d") + "-hfss-smoke-test")
    run = work / datetime.now().strftime("%H%M%S_%f")
    run.mkdir(parents=True, exist_ok=False)
    # AEDT writes its batch log to the process working directory unless -Logfile is given.
    # Pin it to this run directory so no batch.log lands in the repository root.
    settings.aedt_log_file = str(run / "aedt.log")
    result = {
        "started": datetime.now().astimezone().isoformat(),
        "python": sys.version,
        "executable": sys.executable,
        "pyaedt": importlib.metadata.version("pyaedt"),
        "run_directory": str(run),
        "stages": [],
        "success": False,
    }
    result_path = run / "result.json"

    def checkpoint(stage, **details):
        result["stages"].append({"stage": stage, "time": datetime.now().astimezone().isoformat(), **details})
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"stage": stage, **details}, ensure_ascii=False), flush=True)

    desktop = None
    try:
        checkpoint("environment_ready")
        desktop = Desktop(version="2025.2", student_version=True,
                          new_desktop=True, non_graphical=args.non_graphical,
                          close_on_exit=True)
        checkpoint("aedt_connected", version=desktop.aedt_version_string,
                   process_id=desktop.aedt_process_id)
        project = run / "AgentCavity.aedt"
        hfss = Hfss(project=str(project), design="CavityEigenmode",
                    solution_type="Eigenmode", version="2025.2",
                    student_version=True, new_desktop=False,
                    aedt_process_id=desktop.aedt_process_id)
        hfss.modeler.model_units = "mm"
        cavity = hfss.modeler.create_box([0, 0, 0], [100, 80, 40],
                                         name="VacuumCavity", material="vacuum")
        if not cavity:
            raise RuntimeError("Failed to create the cavity geometry")
        cavity.solve_inside = True
        boundary = hfss.assign_perfect_e([face.id for face in cavity.faces], name="PECWalls")
        if not boundary:
            raise RuntimeError("Failed to create PEC boundary")
        setup = hfss.create_setup("EigenSetup")
        setup.props["MinimumFrequency"] = "1GHz"
        setup.props["NumModes"] = 1
        setup.props["MaximumPasses"] = 4
        setup.props["MinimumPasses"] = 1
        setup.props["MinimumConvergedPasses"] = 1
        setup.props["MaxDeltaFreq"] = 1
        if not setup.update():
            raise RuntimeError("Failed to update eigenmode setup")
        if not hfss.save_project(str(project)):
            raise RuntimeError("Failed to save HFSS project")
        if not project.is_file():
            raise RuntimeError("Saved project is missing")
        checkpoint("model_saved", project=str(project), objects=hfss.modeler.object_names,
                   expected_fundamental_ghz=299792458 / 2 * math.sqrt(1 / 0.1**2 + 1 / 0.08**2) / 1e9)
        if not args.no_solve:
            checkpoint("solve_started")
            solved = hfss.analyze_setup("EigenSetup", cores=2, tasks=1,
                                        use_auto_settings=False, blocking=True)
            if not solved:
                raise RuntimeError("HFSS solver returned failure")
            checkpoint("solve_completed")
            hfss.save_project()
            quantities = hfss.post.available_report_quantities(
                report_category="Eigenmode Parameters", solution="EigenSetup : LastAdaptive")
            checkpoint("result_quantities", quantities=quantities)
            if not quantities:
                raise RuntimeError("Solver returned no report quantities")
            data = hfss.post.get_solution_data(
                expressions=quantities, setup_sweep_name="EigenSetup : LastAdaptive",
                report_category="Eigenmode Parameters")
            if not data:
                raise RuntimeError("Could not read eigenmode result data")
            csv_path = run / "eigenmode.csv"
            data.export_data_to_csv(str(csv_path))
            if not csv_path.is_file() or csv_path.stat().st_size == 0:
                raise RuntimeError("Exported results are missing or empty")
            checkpoint("results_exported", csv=str(csv_path), expressions=list(data.expressions))
            with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
                row = next(csv.DictReader(csv_file, delimiter=";"))
            frequency_hz = float(row["Mode(1) (Real)"])
            expected_hz = 299792458 / 2 * math.sqrt(1 / 0.1**2 + 1 / 0.08**2)
            relative_error = abs(frequency_hz - expected_hz) / expected_hz
            if not math.isfinite(frequency_hz) or relative_error > 0.05:
                raise RuntimeError(f"Eigenfrequency sanity check failed: {frequency_hz} Hz")
            checkpoint("physics_checked", frequency_ghz=frequency_hz / 1e9,
                       expected_ghz=expected_hz / 1e9,
                       relative_error_percent=100 * relative_error)
        result["success"] = True
        checkpoint("passed")
    except Exception as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        checkpoint("failed", error=str(exc))
        traceback.print_exc()
    finally:
        if desktop is not None:
            try:
                released = desktop.release_desktop(close_projects=True, close_on_exit=True)
                if released is False:
                    raise RuntimeError("Desktop release returned failure")
                checkpoint("desktop_closed")
            except Exception as exc:
                result["cleanup_error"] = str(exc)
                result["success"] = False
        result["finished"] = datetime.now().astimezone().isoformat()
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        (work / "latest_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print("RESULT_FILE=" + str(result_path), flush=True)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
