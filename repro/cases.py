from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def discover(root: Path) -> list[Path]:
    paths = [root / "case.json"] if (root / "case.json").is_file() else sorted(root.rglob("case.json"))
    if not paths:
        raise ValueError(f"No case.json found in {root}")
    cases = [p.parent for p in paths]
    ids = [validate(p)["id"] for p in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case IDs")
    return cases


def validate(case: Path) -> dict:
    manifest = json.loads((case / "case.json").read_text())
    if manifest["format"] != "ip2-case/1" or manifest["task"] != "step2code" or manifest["units"] != "mm":
        raise ValueError(f"Unsupported case: {case}")
    for group in ("input", "gt"):
        expected = manifest[group]
        actual = {str(p.relative_to(case)) for p in (case / group).rglob("*") if p.is_file()}
        if actual != set(expected):
            raise ValueError(f"Unlisted or missing {group} file in {case}")
        for name, sha in expected.items():
            path = case / name
            if not name.startswith(group + "/") or ".." in Path(name).parts:
                raise ValueError(f"Invalid manifest path: {name}")
            if path.is_symlink() or digest(path) != sha:
                raise ValueError(f"Hash mismatch or symlink: {path}")
    # STEP is deliberately both the conditioning input and the reference here.
    if manifest["input"]["input/target.step"] != manifest["gt"]["gt/gt.step"]:
        raise ValueError(f"Reference differs from the conditioning STEP: {case}")
    return manifest
