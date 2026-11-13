# Reproduction protocol

BenchCAD 2.0 is the reference for case layout, isolated execution, explicit
submission, logs and resumable runs. Evaluation follows the original
SimpleCADAPI vs CadQuery report, without a composite score.

| Metric | Definition |
|---|---|
| Valid delivery | Submitted script, reloadable STEP, valid BREP, solid/shell kind matching target |
| Material IoU | OCCT intersection / union volume, fuzzy tolerance 1e-7 mm |
| F1 @ 1 mm | Harmonic mean of surface precision/recall at 1 mm |
| Chamfer L1 | Average of the two directed mean surface distances, mm |
| Hausdorff | Maximum bidirectional sampled surface distance, mm |
| Badly wrong rate | Number of delivered models with F1 < 0.9999 / valid deliveries |

Surface metrics use 10,000 area-weighted samples per direction. Coordinates
remain in millimetres: no ICP, pose alignment or size normalization. Quality
means use valid deliveries; missing/invalid outputs are counted separately.
Infrastructure errors stay pending and suppress aggregate means until resolved.
Material-volume IoU is undefined for open shells and is recorded as null.

The original report specifies these metric definitions and identifies a frozen
evaluator.py using OCP 7.8.1 and VTK, but that file is absent from the supplied
archive. The implementation uses the locked host CadQuery/OCP environment
and trimesh point-to-triangle distances; seed 0/1 and mesh deflection 0.01 mm are
explicit implementation settings. The metric definitions match the report;
bitwise reproduction of historical numbers is not claimed.

Both CAD arms receive the same cases, model, decoding parameters and resource
limits. A submitted program executes once in a clean directory without the
target or investigation files. Its source and exports are retained for review.
The harness provides no independent scorer feedback to generation.

Hardest23 is the supplied difficult subset of the 200-case bank. Report its
results separately from the historical full-bank aggregates.
