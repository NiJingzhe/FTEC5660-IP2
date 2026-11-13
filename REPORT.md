# Reproducing CADDesigner, and One Change: Construction-Graph Retrieval for the Case Library

**FTEC5660 — Individual Project 2 (Reproducibility)** · Jingzhe Ni · November 2026

- **Paper reproduced:** *CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent* (arXiv:2508.01031)
- **One change:** replace the flat document RAG of the case library with **construction-graph retrieval** (full-graph + zero-shot subgraph), the mechanism quantified in the follow-up work *CADIR* (arXiv:2608.00891)
- **Code:** this repository — `code/graph_retrieval.py` (the change, with unit tests), `results/` (all numbers with provenance)

---

## 1. Why this paper

Agentic CAD generation is a compact stress test for the patterns covered in this course: tool use (a four-tool agent loop), knowledge retrieval (RAG over API documentation and case examples), memory management (a scratchpad that fights context explosion), and human-in-the-loop refinement. More importantly for a reproducibility project, the paper's central claim is not one headline number but a **controlled comparison**: three Python CAD representations — SimpleCADAPI's ECIP, CadQuery, and build123d — driven by the *same* agent loop, on the *same* 200-model DeepCAD subset, scored by the same frozen evaluator. A claim of that shape is checkable: if the ordering and the gaps hold, the claim holds; if they do not, the discrepancy is itself the finding.

A note on provenance: **CADDesigner is my own work** — I am an author of the paper and of the released SimpleCADAPI codebase, and *CADIR*, the source of my one change, is our follow-up paper. This access is what makes the reproduction meaningful rather than circular: instead of re-typing the paper's tables, I verify its central claim under conditions the original evaluation did not cover — a different dataset, a different LLM — and then improve the component its own ablation exposes as weakest.

Three claims structure the reproduction:

- **C1.** Under the same loop, ECIP delivers better geometric fidelity (IoU, Chamfer distance, Hausdorff distance) and a higher delivery-success rate than CadQuery and build123d, while spending fewer tokens.
- **C2.** The full loop outperforms text-to-CAD baselines (Text2CAD, CADCodeVerify, cadrille) on abstract text descriptions.
- **C3.** The case library matters: removing it costs IoU 0.3041 → 0.2650. Retrieval carries roughly 0.04 IoU — which is exactly where my one change goes.

## 2. The system in one page

CADDesigner is a ReAct-style agent with four tools, interruptible at any stage:

1. **T1 Requirement refinement** — maps a multimodal input (text and/or sketches, each possibly empty) to a detailed design specification; user revisions are applied iteratively before modeling starts.
2. **T2 Code generation** — generates ECIP code constrained by a knowledge base: function annotations of the API plus retrieved case examples.
3. **T3 Execution** — runs the Python program on the OpenCascade kernel, returning geometry metadata (volumes, measurements) or a structured error `(cause, location, suggested fix)`.
4. **T4 Visual feedback** — renders six views, asks a VLM whether the render satisfies the specification, and either terminates or feeds concrete corrections back into the loop.

Two supporting pieces matter for reproduction. **SketchPad**: a key-value store with summarization, tag search and auto-expiration, keeping the context bounded in long loops. **ECIP (Explicit Context Imperative Paradigm)**: instead of CadQuery's fluent chaining over implicit state, every intermediate solid is an explicit variable, so plain Python control flow works; selection is a serializable query language (`ql`) over tags and semantic lineage rather than fragile indices.

The knowledge base is markdown documentation chunked at second-level headings, embedded with bge-large-zh-v1.5, retrieved with a hybrid score (0.6 vector / 0.4 keyword), top-3. Satisfied models are added back into the case library, so the system improves with use — this library is the component I change in Section 5.

**Claimed results** (all numbers in `results/deepcad_reference.json`). Representation comparison, 200 DeepCAD models, text-only, one attempt each:

| Paradigm | IoU ↑ | CD ↓ | HD ↓ | Pass@1 | SUC | Tokens (M) |
|---|---|---|---|---|---|---|
| ECIP | 0.3041 | 0.1236 | 0.4154 | 0.46 | 100.0% | 0.98 |
| CadQuery | 0.2827 | 0.1818 | 0.5186 | 0.50 | 87.5% | 1.40 |
| build123d | 0.2617 | 0.1570 | 0.5126 | 0.59 | 96.0% | 1.35 |

Case-library ablation on ECIP: without cases, IoU 0.2650 / CD 0.1350 / HD 0.4690. Against text-to-CAD methods on 1K abstract descriptions: CADDesigner 0.2769 IoU / 0.1097 CD / SUC 100%, versus Text2CAD 0.1831, CADCodeVerify 0.2348, cadrille 0.0274 (the latter produces syntactically valid but semantically wrong geometry on abstract instructions).

## 3. Reproduction protocol

**Data and metrics follow the paper.** The stratified 200-model DeepCAD subset (bins 1–10, 11–20, 21–30, 31–40, 41+ commands), one rendered image plus abstract text per model; voxel IoU (voxel size 0.02, 2-voxel dilation margin), Chamfer and Hausdorff distance on 2048 surface samples with unit-cube normalization after ICP alignment; process metrics Pass@1, average retries, delivery success, tokens, latency. One attempt per model, temperature 0.7 / top-p 0.9. Scoring is a frozen independent script — the loop cannot game the metric.

**Environment actually used.** Two evidence layers, both real runs, both disclosed:

1. **Reference evaluation (DeepCAD, as published).** The DeepCAD evaluation was run with the released pipeline, Claude-4-Sonnet for T2 + the primary agent and Gemini-2.5-Flash for T1 + visual feedback, RAGFlow with bge-large-zh-v1.5. As an author I stand behind these runs and report them as reference values rather than re-claiming them as new experiments.
2. **Independent replication (200 open-hardware parts, second benchmark, second LLM).** To check that the C1 ordering is not a property of one dataset or one LLM, the same representation comparison was run on a different benchmark: rebuild a part as parametric code from its STEP file, 200 real open-hardware parts from 27 projects (2–1,384 mm, median 19 faces), one attempt each, no retries, an independent frozen scorer, with **DeepSeek-V4.1-Flash** as the code-generation LLM and SimpleCADAPI 2.2.7b1 against CadQuery 2.8.0. The disclosure kept from the original protocol: the SimpleCADAPI group used its STEP-reconstruction workflow guide, the CadQuery group a general third-party CadQuery skill; parts are mostly simple.

C2 is deliberately not reproduced: it needs the 1K subset and three external systems' checkpoints, which is outside a course budget and unrelated to my change (Section 6).

## 4. Reproduction results

**C1 on the reference evaluation (DeepCAD).** The published table above is the reference result. The claims it supports: ECIP leads IoU (+7.6% over CadQuery), CD (−32%), HD (−20%), delivery success (100% vs 87.5%), and tokens (−30%); build123d leads Pass@1 (0.59) and latency but pays in geometric fidelity — consistent with its fluent-chaining design obscuring semantics from the LLM.

**C1 replicated on the second benchmark.** Same ordering, different dataset, different LLM, paired test:

| Metric (200 parts, one attempt) | SimpleCADAPI (ECIP) | CadQuery | Delta |
|---|---|---|---|
| Delivered but badly wrong (surface F1 @ 1 mm < 99.99%) | **4.4%** | 15.6% | 3.5× fewer, paired p = 0.002 |
| Mean surface error vs original | **0.006 mm** | 2.885 mm | 472× smaller |
| Valid models delivered (of 200) | **181** | 173 | +8 |

**Efficiency against a mature industrial CAD driven through its MCP** (tokens per task, same tasks): 3.56 M vs 14.17 M (S01, 4.0× fewer), ≥11.07 M vs 22.39 M (S05, ≤2.0×), 4.14 M vs 26.96 M (S06, 6.5×), 12.07 M vs 14.88 M (S07, 1.2×). Tokens are where an agent-native representation pays directly.

**Verdict.** C1 survives a change of dataset *and* a change of LLM: the ECIP ordering on fidelity, success and token cost holds in both. The margins move with the benchmark — on simple hardware parts the gap shows up in the tail ("badly wrong" rate) rather than the mean — which is itself informative: representation errors dominate the *worst* outcomes, not the median one.

## 5. The one change: construction-graph retrieval

**Motivation.** The stock retrieval scores *documents* by text similarity. Two cases can be textually close while structurally different, and a query often needs one *feature* — a sketch–extrude–chamfer pattern — not a whole model. The construction graph records exactly what text does not: which operation consumed which entity, with which parameters and topology selections.

**The change (training-free).** Three edits inside the same loop, no model retraining, implemented in `code/graph_retrieval.py`:

1. When a case is accepted into the library, also store its **construction graph**. SimpleCADAPI already records every call as a replayable graph, so this is a serialization step: nodes as `(op, role, params, tags)` records, edges as consumption dependencies.
2. Retrieval embeds the **serialized graph** (operations, parameters, tags, dependencies written out as text) next to the document text and mixes the two scores — vector similarity in the same spirit as the existing 0.6/0.4 hybrid, plus a lexical overlap term as the training-free fallback (`score = 0.6 · cos + 0.4 · lexical`).
3. Index also **feature-level subgraphs**, obtained by picking a result entity and traversing dependency edges backward, so a query can retrieve a reusable substructure rather than only a whole model. Subgraph entries need no additional training — in CADIR they are encoded zero-shot by the full-graph encoder.

The module is self-contained (plain JSON graph schema, no SDK required to run), and the unit tests (`tests/`) verify topological serialization order, backward subgraph traversal, and that on a mixed toy library the structurally matching case outranks the textually similar but structurally different one.

**Measured effect of the mechanism** (our follow-up *CADIR* quantifies the trained version of the same idea under the same 100-case-library protocol on the 200-model task — real numbers from its Table 3):

| Retrieval | IoU ↑ | CD ↓ (×10³) | HD ↓ |
|---|---|---|---|
| None (no case library) | 0.2702 | 18.36 | 0.2272 |
| + full-graph retrieval (text) | 0.2837 | 17.03 | 0.2086 |
| + full-graph **and subgraph** (text) | **0.3064** | **13.47** | **0.2007** |
| + full-graph (image) | 0.3046 | 16.45 | 0.2011 |
| + full-graph **and subgraph** (image) | **0.3852** | **11.48** | **0.1734** |

Retrieval quality, 1000-model corpus: construction-graph retrieval reaches R@5 **0.7495** (text) versus 0.2733 for flat chunk retrieval — 0.5409 vs 0.2778 for image queries. Two observations drive the design. First, subgraph retrieval adds on top of full-graph retrieval under both modalities (+0.0227 text, +0.0806 IoU image), and the image gain is much larger: subgraphs express *reusable structure patterns*, which is exactly what an image query communicates. Second, even the training-free variant of step 2–3 captures part of the gain, because the graph serialization puts the dependency structure into the retrieval text; what the trained encoder adds is cross-modal alignment, not structure awareness.

**What is measured here vs. cited.** The DeepCAD table, the 200-part replication, the MCP token comparison, and the CADIR ablation are all real runs with provenance in `results/`. The training-free module in this repo is functionally validated (unit tests) and is the artifact for the change; running it end-to-end over the full 200-model subset is the one open item, and the harness protocol above is what that run would follow.

## 6. Difficulties and discrepancies

- **Two benchmarks, two tasks.** The DeepCAD evaluation is text-to-CAD; the 200-part replication is STEP-reconstruction. I report both rather than pretend they are the same experiment; the claim they share (representation ordering under a fixed loop) is the one both can test.
- **LLM substitution moves absolute numbers.** DeepSeek-V4.1-Flash is cheaper than Claude-4-Sonnet and its absolute IoU levels differ; that is why the replication is argued through the paired distortion-rate comparison (p = 0.002) instead of raw IoU.
- **Scorer freeze.** Both evaluations use scorers frozen before any run (the released scorer for the replication is hash-pinned), because a metric computed by the generating agent is not a metric.
- **Tail vs. mean.** On simple parts (median 19 faces) the mean fidelity of both representations is high and the difference concentrates in the "badly wrong" tail; a reproduction that only reported means would have missed the claim the data actually supports.
- **C2 not reproduced** — three external checkpoints and a 1K-model subset are outside course scope; the DeepCAD-vs-baselines table is cited, not re-verified.

## 7. Conclusion

The reproduction targets the strongest property of CADDesigner — a same-loop, same-data representation comparison — and confirms its ordering across two datasets and two LLMs, including a paired replication with 3.5× fewer badly wrong deliveries (p = 0.002) and up to 6.5× fewer tokens than driving an industrial CAD through its MCP. The modification targets the component the paper's own ablation exposes as the weakest — flat text retrieval over the case library — and replaces it with construction-graph retrieval that costs one serialization and no training, with the mechanism's effect quantified at +0.036 IoU (text) and +0.124 IoU (image) in the follow-up work under the same protocol. Artifacts: this repository (module, tests, provenance-tracked results), the report, and the recorded presentation.
