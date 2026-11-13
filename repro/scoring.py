"""Independent geometry evaluation using the original report's metric definitions.

This is a documented implementation of those definitions, not the original
frozen evaluator.py. No registration, scale normalization, or composite score.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from .cases import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def score(reference: Path, candidate: Path, *, config: dict, output: Path, timeout: int) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = output.with_suffix(".config.json")
    write_json(settings, config)
    command = [sys.executable, "-m", "repro.scoring", "--reference", str(reference.resolve()),
               "--candidate", str(candidate.resolve()), "--out", str(output.resolve()),
               "--config", str(settings.resolve())]
    with output.with_suffix(".log").open("w") as log:
        proc = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return {"status": "scorer_error", "error": "Scorer timed out"}
        if proc.returncode:
            return {"status": "scorer_error", "error": f"Scorer exit {proc.returncode}"}
    return json.loads(output.read_text())


def shape_kind(shape):
    if not shape.isValid():
        raise ValueError("Invalid BREP")
    if shape.Solids():
        if shape.Volume() <= 0:
            raise ValueError("Solid has no positive volume")
        return "solid"
    if shape.Shells():
        return "shell"
    raise ValueError("Neither a solid nor a shell")


def evaluate(reference: Path, candidate: Path, config: dict) -> dict:
    import cadquery as cq
    import numpy as np
    import trimesh
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

    ref = cq.importers.importStep(str(reference)).val()
    ref_kind = shape_kind(ref)  # A broken reference is an evaluator error.
    result = {"metric": config["metric"], "settings": config,
              "gt_sha256": digest(reference), "candidate_sha256": digest(candidate),
              "scorer_sha256": digest(Path(__file__)), "status": "scored"}
    try:
        sub = cq.importers.importStep(str(candidate)).val()
        sub_kind = shape_kind(sub)
        if ref_kind != sub_kind:
            raise ValueError(f"Geometry kind mismatch: {sub_kind} vs {ref_kind}")
    except Exception as exc:
        return {**result, "valid_delivery": False, "error": str(exc),
                "material_iou": None, "surface_f1_at_1mm": None,
                "chamfer_l1_mm": None, "hausdorff_mm": None, "badly_wrong": None}

    def mesh(shape):
        # CadQuery's relative tessellation tolerance is disabled explicitly.
        # Clean triangulations before meshing at the requested absolute sag.
        from OCP.BRepTools import BRepTools
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        BRepTools.Clean_s(shape.wrapped)
        mesher = BRepMesh_IncrementalMesh(shape.wrapped, config["mesh_deflection_mm"], False, 0.1, False)
        if not mesher.IsDone():
            raise RuntimeError("Tessellation did not complete")
        vertices, triangles = shape.tessellate(config["mesh_deflection_mm"], 0.1)
        return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=triangles, process=False)

    meshes = [mesh(ref), mesh(sub)]
    if any(len(m.faces) == 0 or m.area <= 0 for m in meshes):
        raise RuntimeError("Cannot sample an empty surface")
    distances = []
    for i in range(2):
        points, _ = trimesh.sample.sample_surface(meshes[i], config["surface_samples_per_direction"],
                                                seed=config["sampling_seed"] + i)
        _, distance, _ = trimesh.proximity.closest_point(meshes[1-i], points)
        distances.append(distance)
    recall, precision = [float(np.mean(d <= config["surface_tolerance_mm"])) for d in distances]
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = None
    if ref_kind == "solid":
        common = BRepAlgoAPI_Common()
        from OCP.TopTools import TopTools_ListOfShape
        left, right = TopTools_ListOfShape(), TopTools_ListOfShape()
        left.Append(ref.wrapped)
        right.Append(sub.wrapped)
        common.SetArguments(left)
        common.SetTools(right)
        common.SetFuzzyValue(config["boolean_fuzzy_mm"])
        common.Build()
        if not common.IsDone():
            raise RuntimeError("Material intersection failed")
        intersection = max(0.0, cq.Shape.cast(common.Shape()).Volume())
        union = ref.Volume() + sub.Volume() - intersection
        if union <= 0:
            raise RuntimeError("Material union has no positive volume")
        iou = min(1.0, max(0.0, intersection / union))
    result.update(valid_delivery=True, geometry_kind=sub_kind, material_iou=iou,
                  surface_precision_at_1mm=precision, surface_recall_at_1mm=recall,
                  surface_f1_at_1mm=f1, badly_wrong=f1 < config["badly_wrong_f1_threshold"],
                  chamfer_l1_mm=float((distances[0].mean() + distances[1].mean()) / 2),
                  hausdorff_mm=float(max(d.max() for d in distances)))
    return result


def worker():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    result = evaluate(args.reference, args.candidate, json.loads(args.config.read_text()))
    write_json(args.out, result)


if __name__ == "__main__":
    worker()
