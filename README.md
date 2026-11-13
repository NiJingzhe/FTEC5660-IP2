# FTEC5660 IP2 — Reproducing CADDesigner + the Agent-Native SDK Contract

Individual Project 2 (Reproducibility), FTEC5660 Agentic AI for Business and FinTech.

**Reproduced paper:** [CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent](https://arxiv.org/abs/2508.01031) — **my own work** (I am an author; the SimpleCADAPI codebase, paper-era ECIP and the released native SDK alike, is ours).
**The one change:** the agent-facing tool contract — paper-era ECIP replaced by the released native SDK (measured structured errors, stable-reference selection, replayable session graph), evaluated as **conditional generation** (condition: reference part; output: parametric code) on a paired 200-part benchmark.

## What is here

```
├── REPORT.md                        # the report (all numbers have provenance)
├── code/graph_retrieval.py          # future-work artifact: training-free graph retrieval
├── tests/test_graph_retrieval.py    # correctness of serialization, traversal, ranking
├── results/
│   ├── deepcad_reference.json       # CADDesigner DeepCAD evaluation (reference runs)
│   └── released_benchmark.json      # paired 200-part conditional-generation benchmark + MCP token cost
└── presentation/script.md           # script for the recorded presentation
```

## Reproduction verdict (one paragraph)

CADDesigner's core claim — under the same agent loop, the ECIP representation beats CadQuery and build123d on geometric fidelity, delivery success and token cost — holds on its 200-model DeepCAD reference evaluation. The paper's own ablations show the tool contract is load-bearing (removing structured errors collapses delivery success 100% → 81.5%), so the one change upgrades that contract wholesale: the released native SDK reports failures with measured numbers and units, selects geometry by stable references instead of shifting indices, and records every call as a replayable session graph. Evaluated as conditional generation on a paired benchmark — 200 real open-hardware parts, same LLM on both arms, one attempt each, frozen scorer — the new contract delivers 4.4% vs 15.6% badly-wrong models (3.5× fewer, paired p = 0.002), 0.006 mm vs 2.885 mm mean surface error, 181 vs 173 valid deliveries, and up to 6.5× fewer tokens than an industrial CAD driven through its MCP.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

No dependencies beyond the standard library.
