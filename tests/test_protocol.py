import copy
import importlib.util
import unittest
from pathlib import Path

from repro.cases import discover
from repro.episode import parse_reply
from repro.sandbox import bounded

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("summary", ROOT / "tools/summarize.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class TestProtocol(unittest.TestCase):
    def test_all_23_cases_are_hash_valid(self):
        self.assertEqual(len(discover(ROOT / "data/hardest23")), 23)

    def test_only_explicit_submit_is_final(self):
        self.assertEqual(parse_reply("```submit\nresult = build()\n```")[0], "submit")
        self.assertEqual(parse_reply("```python\nresult = build()\n```")[0], "python")
        self.assertIsNone(parse_reply("result = build()"))
        self.assertIsNone(parse_reply("```submit\nresult = build()"))
        self.assertIsNone(parse_reply("```python\na=1\n```\n```submit\nb=2\n```"))

    def test_observation_retains_head_and_tail(self):
        output = bounded("start" + "x" * 20000 + "finish")
        self.assertTrue(output.startswith("start"))
        self.assertTrue(output.endswith("finish"))

    def test_pending_case_blocks_headline(self):
        payload = {"protocol_sha256": "test", "protocol": {
            "arms": ["simplecadapi", "cadquery"], "case_manifests": {"a": "x", "b": "y"}},
            "records": []}
        for arm in payload["protocol"]["arms"]:
            for case in ("a", "b"):
                payload["records"].append({"case_id": case, "arm": arm, "resolved": True, "valid_delivery": True,
                    "measurement": {"material_iou": 1.0, "surface_f1_at_1mm": 1.0,
                                    "chamfer_l1_mm": 0.0, "hausdorff_mm": 0.0, "badly_wrong": False},
                    "tokens": {"prompt_tokens": 2, "completion_tokens": 1}})
        complete = summary.summarize(payload)
        self.assertEqual(complete["arms"]["cadquery"]["mean_chamfer_l1_mm"], 0)
        pending = copy.deepcopy(payload)
        pending["records"][-1]["resolved"] = False
        partial = summary.summarize(pending)
        self.assertIsNone(partial["arms"]["cadquery"]["mean_chamfer_l1_mm"])
        self.assertEqual(partial["arms"]["cadquery"]["pending"], ["b"])


if __name__ == "__main__":
    unittest.main()
