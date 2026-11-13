# FTEC5660 IP2 — Reproducing CADDesigner + Construction-Graph Retrieval

Individual Project 2 (Reproducibility), FTEC5660 Agentic AI for Business and FinTech.

**Reproduced paper:** [CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent](https://arxiv.org/abs/2508.01031) — **my own work** (I am an author; the released SimpleCADAPI codebase is ours). The reproduction therefore verifies its central claim under conditions the original evaluation did not cover — a different dataset and a different LLM — rather than re-typing its tables.
**The one change:** construction-graph retrieval (full-graph + zero-shot subgraph) for the case library — the mechanism quantified in our follow-up paper [CADIR](https://arxiv.org/abs/2608.00891).

## What is here

```
├── REPORT.md                        # the report (all numbers have provenance)
├── code/graph_retrieval.py          # the change: training-free, self-contained module
├── tests/test_graph_retrieval.py    # correctness of serialization, traversal, ranking
├── results/
│   ├── deepcad_reference.json       # CADDesigner DeepCAD evaluation (reference runs)
│   └── released_benchmark.json      # 200-part replication vs CadQuery + industrial-MCP tokens
└── presentation/script.md           # script for the recorded presentation
```

## Reproduction verdict (one paragraph)

CADDesigner's core claim — under the same agent loop, the ECIP representation beats CadQuery and build123d on geometric fidelity, delivery success and token cost — holds on its 200-model DeepCAD evaluation and replicates on a second benchmark (200 open-hardware parts, STEP-reconstruction, DeepSeek-V4.1-Flash, frozen scorer): 4.4% vs 15.6% badly-wrong deliveries (3.5× fewer, paired p = 0.002), 0.006 mm vs 2.885 mm mean surface error, 181 vs 173 valid deliveries. The paper's own ablation shows the case library carries ~0.04 IoU, so the modification replaces its flat text retrieval with construction-graph retrieval: store each accepted case's construction graph (one serialization — the API already records every call as a replayable graph), mix graph-serialized and document similarity, and index feature-level subgraphs obtained by backward traversal. The mechanism's effect is quantified in CADIR under the same 100-case protocol: text IoU 0.2702 → 0.2837 (full-graph) → 0.3064 (full + subgraph); image 0.2613 → 0.3046 → 0.3852; retrieval R@5 0.7495 vs 0.2733 for flat chunks at a 1000-model corpus.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

No dependencies beyond the standard library.
