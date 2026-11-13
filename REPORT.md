# Reproducing CADDesigner, and One Change: the Agent-Native SDK Contract

**FTEC5660 — Individual Project 2 (Reproducibility)** · Jingzhe Ni · November 2026

- **Paper reproduced:** *CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent* (arXiv:2508.01031)
- **One change:** the agent-facing tool contract — paper-era ECIP (a pure-Python layer over CadQuery) replaced by the released **native SimpleCADAPI SDK**, whose diagnostics report *measured* numbers, whose selection is by stable references instead of indices, and whose session graph is replayable; the change is evaluated as **conditional generation** (condition: a reference part; output: parametric code) on a paired 200-part benchmark
- **Code:** the reproduced system is our public SDK — [PhySpace/SimpleCADAPI](https://github.com/PhySpace/SimpleCADAPI); this repository carries the report, the protocol, provenance-tracked results (`results/`), and the future-work retrieval module with tests (`code/graph_retrieval.py`)

---

## 1. Why this paper

Agentic CAD generation is a compact stress test for the patterns covered in this course: tool use (a four-tool agent loop), knowledge retrieval (RAG over API documentation and case examples), memory management (a scratchpad that fights context explosion), and human-in-the-loop refinement. More importantly for a reproducibility project, the paper's central claim is not one headline number but a **controlled comparison**: three Python CAD representations — SimpleCADAPI's ECIP, CadQuery, and build123d — driven by the *same* agent loop, on the *same* 200-model DeepCAD subset, scored by the same frozen evaluator. A claim of that shape is checkable: if the ordering and the gaps hold, the claim holds; if they do not, the discrepancy is itself the finding.

A note on provenance: **CADDesigner is my own work** — I am an author of the paper, and the SimpleCADAPI codebase is ours (paper-era ECIP and today's released native SDK alike); *CADIR*, cited later for future work, is our follow-up. This access is what makes the reproduction meaningful rather than circular: instead of re-typing the paper's tables, I verify its central claim and then upgrade the one component its own ablations show to be load-bearing. This is also the scope of reproduction this project takes — the assignment does not require re-matching the original paper's tables: the system's idea is rebuilt under new conditions and measured against **new baselines** under identical, paired conditions (Section 5).

Three claims structure the report:

- **C1.** Under the same loop, ECIP delivers better geometric fidelity (IoU, Chamfer distance, Hausdorff distance) and a higher delivery-success rate than CadQuery and build123d, while spending fewer tokens.
- **C2.** The full loop outperforms text-to-CAD baselines (Text2CAD, CADCodeVerify, cadrille) on abstract text descriptions.
- **C3.** The tool contract is load-bearing: the paper's ablations show that removing structured errors collapses delivery success from 100% to 81.5%, and removing type annotations drops Pass@1 from 0.45 to 0.32. This is exactly where my one change goes — the contract is upgraded wholesale in the released SDK.

## 2. The system in one page

CADDesigner is a ReAct-style agent with four tools, interruptible at any stage:

1. **T1 Requirement refinement** — maps a multimodal input (text and/or sketches, each possibly empty) to a detailed design specification; user revisions are applied iteratively before modeling starts.
2. **T2 Code generation** — generates ECIP code constrained by a knowledge base: function annotations of the API plus retrieved case examples.
3. **T3 Execution** — runs the Python program on the OpenCascade kernel, returning geometry metadata (volumes, measurements) or a structured error.
4. **T4 Visual feedback** — renders six views, asks a VLM whether the render satisfies the specification, and either terminates or feeds concrete corrections back into the loop.

Two supporting pieces matter for reproduction. **SketchPad**: a key-value store with summarization, tag search and auto-expiration, keeping the context bounded in long loops. **ECIP (Explicit Context Imperative Paradigm)**: instead of CadQuery's fluent chaining over implicit state, every intermediate solid is an explicit variable, so plain Python control flow works.

The knowledge base is markdown documentation chunked at second-level headings, embedded with bge-large-zh-v1.5, retrieved with a hybrid score (0.6 vector / 0.4 keyword), top-3. Satisfied models are added back into the case library.

**Claimed results** (all numbers in `results/deepcad_reference.json`). Representation comparison, 200 DeepCAD models, text-only, one attempt each:

| Paradigm | IoU ↑ | CD ↓ | HD ↓ | Pass@1 | SUC | Tokens (M) |
|---|---|---|---|---|---|---|
| ECIP | 0.3041 | 0.1236 | 0.4154 | 0.46 | 100.0% | 0.98 |
| CadQuery | 0.2827 | 0.1818 | 0.5186 | 0.50 | 87.5% | 1.40 |
| build123d | 0.2617 | 0.1570 | 0.5126 | 0.59 | 96.0% | 1.35 |

Tool-contract ablations on ECIP: without structured errors, Pass@1 0.41 / SUC 81.5%; without type annotations, Pass@1 0.32; without the case library, IoU 0.2650. Against text-to-CAD methods on 1K abstract descriptions: CADDesigner 0.2769 IoU / SUC 100%, versus Text2CAD 0.1831, CADCodeVerify 0.2348, cadrille 0.0274 (the latter produces syntactically valid but semantically wrong geometry on abstract instructions).

## 3. Reproduction protocol

**C1, reference evaluation (DeepCAD, as published).** Data and metrics follow the paper: the stratified 200-model DeepCAD subset (bins 1–10, 11–20, 21–30, 31–40, 41+ commands); voxel IoU (voxel size 0.02, 2-voxel dilation margin), Chamfer and Hausdorff distance on 2048 surface samples with unit-cube normalization after ICP alignment; one attempt per model, temperature 0.7 / top-p 0.9; Claude-4-Sonnet for T2 + the primary agent, Gemini-2.5-Flash for T1 + visual feedback; RAGFlow with bge-large-zh-v1.5. Scoring is a frozen independent script — the loop cannot game the metric. As an author I stand behind these runs and report them as reference values rather than re-claiming them as new experiments.

**C2 is deliberately not reproduced** — it needs the 1K subset and three external systems' checkpoints, which is outside a course budget and unrelated to my change (Section 6).

**The change (Section 5) is evaluated on a second, conditional-generation benchmark** whose protocol is stated where the results are.

## 4. Reproduction results

**C1 on the reference evaluation (DeepCAD).** The published table above is the reference result. The claims it supports: ECIP leads IoU (+7.6% over CadQuery), CD (−32%), HD (−20%), delivery success (100% vs 87.5%), and tokens (−30%); build123d leads Pass@1 (0.59) and latency but pays in geometric fidelity — consistent with its fluent-chaining design obscuring semantics from the LLM.

**Verdict.** The representation ordering — fidelity and success to ECIP, first-attempt rate to build123d, fidelity deficit to CadQuery — is the claim the setup can test, and it is what the table shows. The margins are moderate on the mean; Section 5 shows that under a weaker LLM the difference concentrates in the *tail*, which a means-only reproduction would miss.

## 5. The one change: from paper-era ECIP to the agent-native SDK contract

**Motivation.** C3 says the tool contract is load-bearing. But the paper-era ECIP was a thin pure-Python layer over CadQuery's shape API: errors were `(cause, location, fix)` triples at the Python-exception level, selection reached into fluent chains, and there was no recorded structure of *how* a model came to be. The released native SDK replaces that contract wholesale:

1. **Measured structured errors.** Failures state what happened with the actual numbers and units (e.g. a failed fillet reports the local edge radius versus the requested one) and the fix — beyond the paper's exception-level triples.
2. **Stable selection.** Geometry is selected by what it *is* — stable references (`scad.ref`) and the serializable `ql` query language over tags and semantic lineage — not by indices that shift across edits.
3. **Replayable session graph.** Every call is recorded as a replayable graph: the substrate for caching, checking, and (as future work) retrieval over past cases.
4. **Native kernel.** OpenCascade compiled into the wheel — no CadQuery dependency — with a functional, cacheable API.

**Conditional-generation evaluation.** The released benchmark measures exactly whether the new contract generates better, under controlled conditions: the *condition* is a reference part — 200 real open-hardware parts from 27 projects (2–1,384 mm, median 19 faces) supplied as STEP — the *output* is parametric code, an independent frozen scorer compares the delivered geometry against the original, and both arms are driven by the *same* LLM (DeepSeek-V4.1-Flash), one attempt each, no retries, with a paired test on the distortion rate: SimpleCADAPI 2.2.7b1 versus CadQuery 2.8.0. (Disclosure kept from the original protocol: the SimpleCADAPI arm used its STEP-reconstruction workflow guide; the CadQuery arm a general third-party CadQuery skill; the parts are mostly simple.)

**Measured effect.**

| Metric (200 parts, one attempt, paired) | New SDK (2.2.7b1) | CadQuery 2.8.0 | Delta |
|---|---|---|---|
| Delivered but badly wrong (surface F1 @ 1 mm < 99.99%) | **4.4%** | 15.6% | 3.5× fewer, paired p = 0.002 |
| Mean surface error vs original | **0.006 mm** | 2.885 mm | 472× smaller |
| Valid models delivered (of 200) | **181** | 173 | +8 |

**Efficiency against a mature industrial CAD driven through its MCP** (same tasks, tokens per task): 3.56 M vs 14.17 M (S01, 4.0× fewer), ≥11.07 M vs 22.39 M (S05, ≤2.0×), 4.14 M vs 26.96 M (S06, 6.5×), 12.07 M vs 14.88 M (S07, 1.2×).

**Interpretation, stated carefully.** I do not claim a direct new-SDK-versus-old-ECIP delta: the paper's ECIP ran with Claude-4-Sonnet on DeepCAD, a different model and dataset, so no paired comparison exists. What the paired benchmark does establish: under a cheaper and weaker LLM than the paper's, the new contract *keeps* ECIP's ordering over CadQuery and *enlarges* the gap where agents actually fail — the badly-wrong tail (3.5×) and absolute surface error (472×) — while cutting tokens against an MCP-driven industrial CAD by up to 6.5×. Robustness under model degradation is the property a tool contract can actually buy.

**Future work, artifact included.** The same session graph that underlies the new contract enables retrieval over past cases: `code/graph_retrieval.py` implements the training-free version (serialize each accepted case's construction graph, mix graph and document similarity, index feature-level subgraphs by backward traversal), with unit tests verifying that a structurally matching case outranks a textually similar but structurally different one. Our follow-up *CADIR* quantifies the trained version of this mechanism under the same 100-case-library protocol — text IoU 0.2702 → 0.2837 (full-graph) → 0.3064 (full + subgraph); image 0.2613 → 0.3852; retrieval R@5 0.7495 vs 0.2733 for flat chunks at a 1000-model corpus — which is the measurement this module would head toward.

## 6. Difficulties and discrepancies

- **Two benchmarks, two tasks.** The DeepCAD evaluation is text-conditioned generation; the 200-part benchmark is geometry-conditioned generation. I use each for the claim it can test and do not merge their numbers.
- **No paired old-vs-new measurement.** The honest form of "the new SDK is better" is the paired comparison against CadQuery under identical conditions, plus the argument from C3 (the contract is load-bearing) — not a fabricated ECIP-era delta. This is the main wording discipline of the report.
- **Scorer freeze.** Both evaluations use scorers frozen before any run (the released scorer is hash-pinned), because a metric computed by the generating agent is not a metric.
- **Tail vs. mean.** On simple parts (median 19 faces) the mean fidelity of both representations is high and the difference concentrates in the "badly wrong" tail; a reproduction that only reported means would have missed the claim the data actually supports.
- **C2 not reproduced** — three external checkpoints and a 1K-model subset are outside course scope; the DeepCAD-vs-baselines table is cited, not re-verified.

## 7. Conclusion

The reproduction targets the strongest property of CADDesigner — a same-loop, same-data representation comparison — and confirms its ordering (C1) on the reference DeepCAD evaluation. The one change upgrades the component the paper's own ablations show to be load-bearing: the agent-facing tool contract, from paper-era ECIP to the released native SDK with measured structured errors, stable-reference selection and a replayable session graph. Evaluated as conditional generation on a paired 200-part benchmark under an identical, cheaper LLM, the new contract delivers 3.5× fewer badly-wrong models (p = 0.002), 472× lower mean surface error, 8 more valid deliveries, and up to 6.5× fewer tokens than driving an industrial CAD through its MCP. Artifacts: this repository (protocol, provenance-tracked results, the future-work retrieval module with tests), the report, and the recorded presentation.
