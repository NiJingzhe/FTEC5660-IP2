"""Summarize the original report's metrics, using valid deliveries as denominator."""
import argparse
import json
import statistics
from pathlib import Path


def summarize(payload: dict) -> dict:
    protocol, records = payload["protocol"], payload["records"]
    expected = set(protocol["case_manifests"])
    arms = {}
    for arm in protocol["arms"]:
        rows = [r for r in records if r["arm"] == arm]
        resolved = {r["case_id"] for r in rows if r["resolved"]}
        complete = resolved == expected
        valid = [r["measurement"] for r in rows if r["resolved"] and r["valid_delivery"]]
        bad = sum(m["badly_wrong"] for m in valid)
        means = {}
        for key in ("material_iou", "surface_f1_at_1mm", "chamfer_l1_mm", "hausdorff_mm"):
            values = [m[key] for m in valid if m[key] is not None]
            means["mean_" + key] = statistics.mean(values) if complete and values else None
        arms[arm] = {"expected": len(expected), "resolved": len(resolved), "complete": complete,
            "pending": sorted(expected - resolved), "valid_deliveries": len(valid),
            "valid_delivery_rate": len(valid) / len(expected) if complete else None,
            "badly_wrong_count": bad,
            "badly_wrong_rate_among_delivered": bad / len(valid) if complete and valid else None,
            **means, "tokens": {key: sum(r["tokens"][key] for r in rows)
                                  for key in ("prompt_tokens", "completion_tokens")}}
    return {"protocol_sha256": payload["protocol_sha256"], "arms": arms,
        "model": protocol.get("model"), "execution": protocol.get("execution"),
        "note": "Metrics use valid deliveries; missing deliveries are counted separately, not assigned zero distance. Hardest23 is a selected subset."}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path)
    args = ap.parse_args()
    print(json.dumps(summarize(json.loads(args.run.read_text())), indent=2))
