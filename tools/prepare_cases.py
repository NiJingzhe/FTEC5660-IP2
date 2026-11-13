"""Convert the supplied Hardest23 archive/directory into hash-pinned cases."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repro.cases import digest, validate, write_json


def prepare(source: Path, out: Path) -> int:
    entries = sorted(source.rglob("CASE_INFO.json"))
    if len(entries) != 23:
        raise ValueError(f"Expected Hardest23's 23 cases, found {len(entries)}")
    for entry in entries:
        info = json.loads(entry.read_text())
        raw = entry.parent
        step = raw / "brep.step"
        if digest(step) != info["step_sha256"]:
            raise ValueError(f"Source STEP hash mismatch: {step}")
        case = out / f"case{info['test_index']:03d}"
        if case.exists():
            raise FileExistsError(f"Will not overwrite existing case: {case}")
        (case / "input").mkdir(parents=True)
        (case / "gt").mkdir()
        (case / "provenance").mkdir()
        shutil.copy2(step, case / "input/target.step")
        shutil.copy2(step, case / "gt/gt.step")
        shutil.copy2(raw / "preview.png", case / "input/preview.png")
        for name in ("CASE_INFO.json", "meta.json", "ATTRIBUTION.txt", "LICENSE.txt"):
            shutil.copy2(raw / name, case / "provenance" / name)
        manifest = {
            "format": "ip2-case/1", "id": case.name, "task": "step2code",
            "kind": "part", "units": "mm", "split": "hardest23",
            "input": {str(p.relative_to(case)): digest(p) for p in sorted((case / "input").iterdir())},
            "gt": {"gt/gt.step": digest(case / "gt/gt.step")},
            "notes": "Selected difficult subset of a 200-part bank; selection criterion not independently verified."
        }
        write_json(case / "case.json", manifest)
        validate(case)
    write_json(out / "dataset.json", {
        "format": "ip2-dataset/1", "name": "Hardest23", "count": 23,
        "case_ids": sorted(p.name for p in out.glob("case*")),
        "selection": "User-supplied difficult subset of 200; not a random sample.",
        "licenses": "Per-case provenance/LICENSE.txt and ATTRIBUTION.txt."
    })
    return len(entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="cases_Hardest23.7z or an extracted directory")
    ap.add_argument("--out", type=Path, default=Path("data/hardest23"))
    args = ap.parse_args()
    if args.source.is_dir():
        count = prepare(args.source, args.out)
    else:
        import py7zr
        with tempfile.TemporaryDirectory() as tmp:
            with py7zr.SevenZipFile(args.source) as archive:
                archive.extractall(tmp)
            count = prepare(Path(tmp), args.out)
    print(f"Prepared and validated {count} cases in {args.out}")


if __name__ == "__main__":
    main()
