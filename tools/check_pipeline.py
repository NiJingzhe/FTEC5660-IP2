"""Offline integration check: real exports, scorer identity and clean final execution."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repro.cases import discover, write_json
from repro.episode import run_episode
from repro.sandbox import finalise, run_code
from repro.scoring import ROOT, score


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk-python", type=Path)
    ap.add_argument("--docker", action="store_true", help="Check both real sandbox images")
    args = ap.parse_args()
    import tempfile
    config = json.loads((ROOT / "configs/paired.json").read_text())
    config.update(rounds=1, execution_timeout=60)
    outcomes = {"cases_validated": len(discover(ROOT / "data/hardest23"))}
    if args.docker:
        outcomes["image_ids"] = {arm: subprocess.check_output([
            "docker", "image", "inspect", "--format", "{{.Id}}", details["image"]], text=True).strip()
            for arm, details in config["arms"].items()}
    with tempfile.TemporaryDirectory(prefix="ip2-check-", dir=ROOT / "work") as tmp:
        root = Path(tmp)
        for arm, python in [("cadquery", Path(sys.executable)), ("simplecadapi", args.sdk_python)]:
            if python is None and not args.docker:
                continue
            code = ("import cadquery as cq\nresult = cq.Workplane('XY').box(10, 20, 5)\n" if arm == "cadquery" else
                    "import simplecadapi as scad\n@scad.part(id='smoke_box')\ndef build():\n"
                    "    return scad.make_box_rsolid(width=10, height=20, depth=5)\nresult=build()\n")
            directory = root / arm
            execution = run_code(code + finalise(arm), directory,
                                 image=config["arms"][arm]["image"], timeout=120,
                                 local_python=None if args.docker else str(python))
            if execution["returncode"]:
                raise RuntimeError(f"{arm} export failed: {execution['stderr']}")
            measurement = score(directory / "final.step", directory / "final.step", config=config["scorer"],
                                output=root / f"{arm}-identity.json", timeout=120)
            if (not measurement.get("valid_delivery") or measurement.get("surface_f1_at_1mm") != 1.0
                    or abs(measurement.get("material_iou", 0) - 1.0) > 1e-6
                    or measurement.get("chamfer_l1_mm", 1) > 1e-6):
                raise RuntimeError(f"{arm} identity scorer failed: {measurement}")
            outcomes[arm + "_export_and_identity"] = "passed"
        case = discover(ROOT / "data/hardest23")[0]
        # Run a successful final submission through the actual episode interface.
        def submit_box(messages):
            return {"message": {"role": "assistant", "content":
                "```submit\nimport cadquery as cq\nresult=cq.Workplane('XY').box(10,20,5)\n```"},
                "usage": {"prompt_tokens": 0, "completion_tokens": 1}}
        delivered = run_episode(case=case, arm="cadquery", config=config, root=root / "submitted-box",
                                call=submit_box, local_python=None if args.docker else sys.executable)
        if delivered["status"] != "submitted" or not delivered["artifact"]:
            raise RuntimeError("Explicit submission failed")
        outcomes["explicit_submission_export"] = "passed"
        # Exercise report-defined geometry metrics on a real reference.
        diagnostic = score(case / "gt/gt.step", Path(delivered["artifact"]), config=config["scorer"],
                           output=root / "nonidentity.json", timeout=180)
        if (diagnostic.get("status") != "scored" or not diagnostic.get("valid_delivery")
                or diagnostic.get("chamfer_l1_mm", 0) <= 0):
            raise RuntimeError(f"Nonidentity scorer failed: {diagnostic}")
        outcomes["nonidentity_geometry_scoring"] = "passed"
        # This submission tries to read an investigation file; it must fail in the clean directory.
        def call(messages):
            return {"message": {"role": "assistant", "content": "```submit\nopen('target.step').read()\n```"},
                    "usage": {"prompt_tokens": 0, "completion_tokens": 1}}
        episode = run_episode(case=case, arm="cadquery", config=config, root=root / "clean-final",
                              call=call, local_python=None if args.docker else sys.executable)
        if episode["status"] != "submission_failed" or episode["artifact"] is not None:
            raise RuntimeError("Final submission could read target geometry")
        outcomes["target_unavailable_to_submission"] = "passed"
    outcomes["scope"] = "Offline smoke only; no LLM reconstruction or benchmark claim."
    outcomes["execution"] = "docker" if args.docker else "local-smoke"
    outcomes["metric"] = config["scorer"]["metric"]
    write_json(ROOT / "results" / ("validation-docker.json" if args.docker else "validation.json"), outcomes)
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    (ROOT / "work").mkdir(exist_ok=True)
    main()
