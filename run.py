"""Run paired STEP-to-code episodes on Hardest23; see README.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from repro import HARNESS_VERSION
from repro.cases import digest, discover, write_json
from repro.episode import run_episode
from repro.provider import ChatProvider
from repro.scoring import score

ROOT = Path(__file__).resolve().parent
PENDING = {"provider_error", "sandbox_error", "scorer_error"}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=ROOT / "data/hardest23")
    ap.add_argument("--model", required=True, help="Actual API model ID, or mock/no-submit")
    ap.add_argument("--arms", nargs="+", choices=("simplecadapi", "cadquery"), default=["simplecadapi", "cadquery"])
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"))
    ap.add_argument("--api-key-env", default="OPENAI_API_KEY")
    ap.add_argument("--out", type=Path, default=ROOT / "results/runs/run.json")
    ap.add_argument("--rounds", type=int)
    ap.add_argument("--token-budget", type=int)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--vision", action="store_true", help="Attach PNGs; use the same setting for both arms")
    ap.add_argument("--guidance", type=Path, help="Optional JSON map of arm -> documentation file")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Validate cases/settings; no API calls or code execution")
    ap.add_argument("--local-python", type=Path, help="Explicit local smoke execution; never a sandboxed result")
    return ap


def main() -> int:
    args = parser().parse_args()
    config = json.loads((ROOT / "configs/paired.json").read_text())
    for key, value in (("rounds", args.rounds), ("output_token_budget", args.token_budget),
                       ("max_tokens", args.max_tokens), ("temperature", args.temperature)):
        if value is not None:
            config[key] = value
    if min(config["rounds"], config["output_token_budget"], config["max_tokens"]) < 1:
        raise ValueError("Round and token limits must be positive")
    if args.rep < 0 or (args.limit is not None and args.limit < 1):
        raise ValueError("rep must be nonnegative; limit must be positive")
    if args.local_python and len(args.arms) != 1:
        raise ValueError("Local smoke execution takes one arm and its matching Python environment")
    url = urlsplit(args.base_url)
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Base URL must not contain credentials, query or fragment")
    cases = discover(args.cases.resolve())
    if args.limit:
        cases = cases[:args.limit]
    guidance, guidance_hash = {}, {}
    if args.guidance:
        mapping = json.loads(args.guidance.read_text())
        for arm in args.arms:
            path = (args.guidance.parent / mapping[arm]).resolve()
            guidance[arm], guidance_hash[arm] = path.read_text(), digest(path)
    image_ids = {}
    if not args.dry_run and not args.local_python:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        for arm in args.arms:
            image_ids[arm] = subprocess.check_output([
                "docker", "image", "inspect", "--format", "{{.Id}}",
                config["arms"][arm]["image"]], text=True).strip()
            config["arms"][arm]["image"] = image_ids[arm]
    protocol = {
        "harness_version": HARNESS_VERSION, "config": config, "model": args.model,
        "base_url": args.base_url.rstrip("/"), "arms": args.arms,
        "vision": args.vision, "rep": args.rep,
        "execution": "local-smoke" if args.local_python else "docker",
        "local_python": str(args.local_python.absolute()) if args.local_python else None,
        "guidance_sha256": guidance_hash,
        "docker_image_ids": image_ids,
        "case_manifests": {p.name: digest(p / "case.json") for p in cases},
        "harness_sha256": {str(p.relative_to(ROOT)): digest(p)
                            for p in [Path(__file__).resolve(), ROOT / "envs/step2code/TASK.md",
                                      *sorted((ROOT / "repro").glob("*.py"))]},
        "environment_lock_sha256": digest(ROOT / "uv.lock"),
    }
    fingerprint = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    if args.dry_run:
        print(json.dumps({"cases": len(cases), "episodes": len(cases) * len(args.arms),
                          "protocol_sha256": fingerprint, **protocol}, indent=2))
        return 0
    if args.out.exists() and not args.resume:
        raise FileExistsError(f"Use --resume or a new --out: {args.out}")
    if args.model == "mock/no-submit":
        def call(messages):
            return {"message": {"role": "assistant", "content": "```python\nprint('mock: no answer')\n```"},
                    "usage": {"prompt_tokens": 0, "completion_tokens": 1}, "model": args.model}
    elif args.model.startswith("mock/"):
        raise ValueError("Only mock/no-submit is supported; oracle checks use tools/check_pipeline.py")
    else:
        call = ChatProvider(model=args.model, base_url=args.base_url, api_key_env=args.api_key_env,
                            timeout=config["api_timeout"], max_tokens=config["max_tokens"],
                            temperature=config["temperature"])
    payload = {"format": "ip2-run/1", "protocol_sha256": fingerprint,
               "protocol": protocol, "records": []}
    if args.out.exists():
        payload = json.loads(args.out.read_text())
        if payload["protocol_sha256"] != fingerprint:
            raise ValueError("Resume refused: model, cases, code or settings changed")
    completed = {(r["case_id"], r["arm"]) for r in payload["records"] if r["status"] not in PENDING}
    run_id = args.out.resolve().stem + "-" + fingerprint[:12]
    for case in cases:
        manifest = json.loads((case / "case.json").read_text())
        for arm in args.arms:
            if (case.name, arm) in completed:
                continue
            directory = ROOT / "work" / run_id / f"r{args.rep}" / case.name / arm / str(time.time_ns())
            result = run_episode(case=case, arm=arm, config=config, root=directory,
                                 call=call, vision=args.vision,
                                 local_python=str(args.local_python) if args.local_python else None,
                                 guidance=guidance.get(arm, ""))
            measurement = None
            if result["artifact"]:
                measurement = score(case / "gt/gt.step", Path(result["artifact"]), config=config["scorer"],
                                    output=directory / "score.json", timeout=config["scoring_timeout"])
                if measurement["status"] == "scorer_error":
                    result["status"] = "scorer_error"
            record = {"case_id": case.name, "arm": arm, "rep": args.rep,
                      "gt_sha256": manifest["gt"]["gt/gt.step"],
                      "work": str(directory.relative_to(ROOT)), **result,
                      "resolved": result["status"] not in PENDING,
                      "valid_delivery": bool(measurement and measurement.get("valid_delivery")),
                      "measurement": measurement}
            payload["records"] = [r for r in payload["records"]
                                  if (r["case_id"], r["arm"]) != (case.name, arm)]
            payload["records"].append(record)
            write_json(args.out, payload)
            print(f"{case.name} {arm}: {record['status']}, valid_delivery={record['valid_delivery']}", flush=True)
    return 1 if any(r["status"] in PENDING for r in payload["records"]) else 0


if __name__ == "__main__":
    sys.exit(main())
