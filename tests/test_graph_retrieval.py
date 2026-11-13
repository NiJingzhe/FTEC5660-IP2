"""Unit tests for the training-free construction-graph retrieval module.

Run:  python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from graph_retrieval import (  # noqa: E402
    backward_subgraph,
    build_library_entry,
    lexical_overlap,
    retrieve,
    serialize_graph,
)


def _bracket_graph():
    """L-bracket: box base, fillet on a vertical edge, top hole, chamfer.

    Dependency chain: box <- fillet <- hole(pattern of 1) <- chamfer? no --
    kept small: box -> fillet -> hole -> result; hole consumes fillet's solid.
    """
    return {
        "nodes": [
            {"id": "n1", "op": "make_box_rsolid", "role": "base",
             "params": {"L": 40.0, "W": 20.0, "H": 8.0}, "tags": ["base"]},
            {"id": "n2", "op": "fillet_rsolid", "role": "edge treatment",
             "params": {"r": 3.0}, "tags": ["fillet"]},
            {"id": "n3", "op": "extrude_rsolid", "role": "hole",
             "params": {"d": 5.0}, "tags": ["hole", "mounting"]},
            {"id": "n4", "op": "chamfer_rsolid", "role": "edge treatment",
             "params": {"c": 1.0}, "tags": ["chamfer"]},
        ],
        "edges": [["n2", "n1"], ["n3", "n2"], ["n4", "n3"]],
        "results": ["n4"],
    }


class TestSerialization(unittest.TestCase):
    def test_dependency_order(self):
        text = serialize_graph(_bracket_graph())
        lines = text.splitlines()
        self.assertEqual(lines[0].split("(")[0], "make_box_rsolid")
        self.assertTrue(lines[1].endswith("<- n1"))
        self.assertTrue(lines[2].endswith("<- n2"))

    def test_cycle_rejected(self):
        g = {"nodes": [{"id": "a", "op": "x"}, {"id": "b", "op": "y"}],
             "edges": [["a", "b"], ["b", "a"]], "results": ["a"]}
        with self.assertRaises(ValueError):
            serialize_graph(g)

    def test_structure_in_text(self):
        # the serialized text must carry parameters and dependencies
        text = serialize_graph(_bracket_graph())
        self.assertIn("r=3", text)
        self.assertIn("<- n1", text)


class TestSubgraph(unittest.TestCase):
    def test_backward_traversal(self):
        sub = backward_subgraph(_bracket_graph(), seed="n3", max_nodes=8)
        ids = {n["id"] for n in sub["nodes"]}
        self.assertEqual(ids, {"n1", "n2", "n3"})   # seed + its dependencies
        self.assertEqual(sub["results"], ["n3"])

    def test_bounded(self):
        # a long chain must be cut at max_nodes, keeping the closest ancestors
        chain = {"nodes": [{"id": f"n{i}", "op": f"op{i}"} for i in range(10)],
                 "edges": [[f"n{i+1}", f"n{i}"] for i in range(9)],
                 "results": ["n9"]}
        sub = backward_subgraph(chain, seed="n9", max_nodes=4)
        self.assertEqual(len(sub["nodes"]), 4)


class TestScoring(unittest.TestCase):
    def test_structural_match_outranks_textual_match(self):
        # query wants a fillet-then-hole structure; case A has it, case B is
        # textually close (same words) but structurally different (no fillet).
        case_a = _bracket_graph()
        case_b = {"nodes": [
            {"id": "m1", "op": "make_box_rsolid", "role": "base",
             "params": {"L": 60.0, "W": 30.0, "H": 10.0}, "tags": ["base"]},
            {"id": "m2", "op": "chamfer_rsolid", "role": "edge treatment",
             "params": {"c": 2.0}, "tags": ["fillet", "hole"]},   # misleading tags
        ], "edges": [["m2", "m1"]], "results": ["m2"]}
        library = []
        library += build_library_entry("A_bracket", case_a, "bracket with fillet and hole")
        library += build_library_entry("B_slab", case_b, "bracket with fillet and hole")
        query = "mounting hole with fillet on a base plate"
        top = retrieve(query, None, library, k=3, kinds=["full_graph"])
        self.assertEqual(top[0][1], "A_bracket")

    def test_lexical_fallback(self):
        self.assertGreater(lexical_overlap("fillet radius", "fillet radius on edge"), 0.0)
        self.assertEqual(lexical_overlap("fillet", "chamfer"), 0.0)

    def test_subgraph_entries_enable_feature_reuse(self):
        # a feature-level query should hit case A's subgraph entry
        library = build_library_entry("A_bracket", _bracket_graph(), "bracket")
        query = "chamfer treatment on a hole edge"
        top = retrieve(query, None, library, k=2)
        self.assertTrue(any(kind.startswith("subgraph:") for _, _, kind in top))


if __name__ == "__main__":
    unittest.main()
