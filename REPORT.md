# Reproducing CADDesigner, and One Change: the Agent-Native SDK Contract

**FTEC5660 — Individual Project 2 (Reproducibility)** · Jingzhe Ni · November 2026

- **Paper reproduced:** *CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent* (arXiv:2508.01031)
- **One change:** the agent-facing tool contract — paper-era ECIP (a pure-Python layer over CadQuery) replaced by the released **native SimpleCADAPI SDK**, whose diagnostics report *measured* numbers, whose selection is by stable references instead of indices, and whose session graph is replayable; the change is evaluated as **conditional generation** (condition: a reference part; output: parametric code) on a paired 200-part benchmark
- **Code:** the reproduced system is our public SDK — [PhySpace/SimpleCADAPI](https://github.com/PhySpace/SimpleCADAPI). This repository includes a runnable paired STEP-to-code harness (`run.py`), the 23-case Hardest23 subset, versioned protocol, independent scorer, and provenance-tracked historical results (`results/`).

---

## 1. Why this paper

Agentic CAD generation is a compact stress test for the patterns covered in this course: tool use (a four-tool agent loop), knowledge retrieval (RAG over API documentation and case examples), memory management (a scratchpad that fights context explosion), and human-in-the-loop refinement. More importantly for a reproducibility project, the paper's central claim is not one headline number but a **controlled comparison**: three Python CAD representations — SimpleCADAPI's ECIP, CadQuery, and build123d — driven by the *same* agent loop, on the *same* 200-model DeepCAD subset, scored by the same frozen evaluator. A claim of that shape is checkable: if the ordering and the gaps hold, the claim holds; if they do not, the discrepancy is itself the finding.

A note on provenance: **CADDesigner is my own work** — I am an author of the paper, and the SimpleCADAPI codebase is ours (paper-era ECIP and today's released native SDK alike). Because the reproduced system is our own, this is not an outside replication, and I say so up front. Instead of re-typing the paper's tables, I (a) check that the published DeepCAD runs are consistent with the paper's central claim, and (b) upgrade the one component its own ablations show to be load-bearing and measure the upgrade against **new baselines** under identical, paired conditions (Section 5). As discussed with the instructor, this report therefore does not re-run and re-match the original paper's tables; the assignment text asks for "your own measured outputs", and the paired benchmark in Section 5 is where those come from. Section 6 states which numbers were re-run and which are only cited.

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

**C1 on the reference evaluation (DeepCAD).** These are **our own first-party runs** (my co-authors and I), produced for the paper and not repeated during this assignment; the table in Section 2 is the published result (the paper's Table 5), which I re-checked here against the paper text and for internal consistency. What it supports: ECIP leads IoU (+7.6% over CadQuery), CD (−32%), HD (−20%), delivery success (100% vs 87.5%), and tokens (−30%); build123d leads Pass@1 (0.59) and latency but trails ECIP in geometric fidelity. The paper's explanation — build123d's symbolic, fluent style hides semantics from the LLM — is a hypothesis it does not test in isolation.

**Verdict.** Our own measured outputs show C1's ordering (fidelity and success to ECIP, first-attempt rate to build123d, a fidelity deficit for CadQuery). They are first-party results rather than an outside replication, which is the usual caveat for authors reproducing their own paper, and the margins on the mean are moderate. One small discrepancy turned up while cross-checking: the paper reports the same ECIP configuration with Pass@1 = 0.45 in its ablation table (Table 2) and 0.46 in the representation table (Table 5); I cite both as printed and do not resolve it. As an author, I can settle this from our run logs; the report keeps both values until that is done. The evidence for the change itself is the paired benchmark in Section 5.

## 5. The one change: from paper-era ECIP to the agent-native SDK contract

**Motivation.** C3 says the tool contract is load-bearing. But the paper-era ECIP was a thin pure-Python layer over CadQuery's shape API: errors were `(cause, location, fix)` triples at the Python-exception level, selection reached into fluent chains, and there was no recorded structure of *how* a model came to be. The released native SDK replaces that contract wholesale:

1. **Measured structured errors.** Failures state what happened with the actual numbers and units (e.g. a failed fillet reports the local edge radius versus the requested one) and the fix — beyond the paper's exception-level triples.
2. **Stable selection.** Geometry is selected by what it *is* — stable references (`scad.ref`) and the serializable `ql` query language over tags and semantic lineage — not by indices that shift across edits.
3. **Replayable session graph.** Every call is recorded as a replayable graph for caching, checking, and durable model delivery.
4. **Native kernel.** OpenCascade compiled into the wheel — no CadQuery dependency — with a functional, cacheable API.

**Conditional-generation evaluation.** The released benchmark compares the two libraries under controlled conditions: the *condition* is a reference part — 200 real open-hardware parts from 27 projects (2–1,384 mm, median 19 faces) supplied as STEP — the *output* is parametric code, an independent frozen scorer compares the delivered geometry against the original, and both arms are driven by the *same* LLM (DeepSeek-V4.1-Flash), one attempt each, no retries, with a paired test on the distortion rate: SimpleCADAPI 2.2.7b1 versus CadQuery 2.8.0. (Disclosure kept from the original protocol: the SimpleCADAPI arm used its STEP-reconstruction workflow guide; the CadQuery arm a general third-party CadQuery skill; the parts are mostly simple.)

**Measured effect.**

| Metric (200 parts, one attempt per arm, single run, paired) | New SDK (2.2.7b1) | CadQuery 2.8.0 | Delta |
|---|---|---|---|
| Delivered but badly wrong (surface F1 @ 1 mm < 99.99%) | **4.4%** | 15.6% | 3.5× fewer, paired p = 0.002 |
| Mean surface error vs original | **0.006 mm** | 2.885 mm | 472× smaller |
| Valid models delivered (of 200) | **181** | 173 | +8 |

**Efficiency against a mature industrial CAD driven through its MCP** (same tasks, tokens per task): 3.56 M vs 14.17 M (S01, 4.0× fewer), ≥11.07 M vs 22.39 M (S05, ≤2.0×), 4.14 M vs 26.96 M (S06, 6.5×), 12.07 M vs 14.88 M (S07, 1.2×).

**Interpretation, stated carefully.** Results are not directly comparable to the paper because the underlying LLM, task and dataset differ. I make no claim about a new-SDK-versus-old-ECIP delta: the paper's ECIP ran with Claude-4-Sonnet on DeepCAD, so no paired comparison exists. What the paired benchmark does show is narrower: with the same cheaper LLM on both arms, the new SDK delivered fewer badly-wrong models (3.5×), a much lower mean surface error (472×) and more valid models than CadQuery, and used up to 6.5× fewer tokens than an MCP-driven industrial CAD on four tasks.

Two limits on how far this can be read. First, **the change is not isolated**: the SDK replaces four things at once (measured errors, stable selection, session graph, native kernel), and I ran no ablation among them, so the gain belongs to the SDK as a whole, not to any single item — the link from the paper's ablation (C3) to the gain is an argument for where to look, not a measured attribution. Second, whether the gap would be larger or smaller under a stronger LLM is untested here.

**Runnable reproduction artifact.** The repository follows the execution and record organization of **BenchCAD 2.0**, while retaining the original report's evaluation metrics: Material IoU (OCCT boolean, fuzzy 1e-7 mm), surface F1 at 1 mm (10,000 area-weighted samples per direction), Chamfer L1 in mm, and sampled Hausdorff in mm. Severe distortion means F1 below 99.99%, with valid deliveries as the denominator. The supplied **Hardest23** cases can run through SimpleCADAPI 2.2.7b1 and CadQuery 2.8.0 with the same model, retained transcripts and independent evaluation. The original frozen evaluator.py was not supplied; the implementation follows the reported definitions but is not verified byte-for-byte against that evaluator. Hardest23 is a selected subset, so its measurements are reported separately from the full 200-part results. Offline pipeline checks pass; new LLM reconstruction measurements remain to be collected. Commands are in `README.md`.

## 6. Debug diary: blockers, discrepancies, and how each was handled

- **Making the artifact runnable.** The repository previously carried result summaries without an execution pipeline. It now includes the Hardest23 cases, a shared experiment entry point, isolated final execution, independent scoring, and logs. The new pipeline is validated offline; actual LLM reconstruction results remain to be collected.
- **No paired old-vs-new measurement.** The paper's ECIP ran with Claude-4-Sonnet on DeepCAD; the paired benchmark uses DeepSeek-V4.1-Flash on 200 open-hardware parts. Nothing in the two datasets is shared, so I do not compute a new-versus-old delta. The comparison I report is new SDK versus CadQuery under identical conditions.
- **Two benchmarks, two tasks.** DeepCAD is text-conditioned generation; the 200-part benchmark is reference-geometry-conditioned. Each is used only for the claim it can test and their numbers are never merged.
- **Paper-internal inconsistency.** ECIP Pass@1 is 0.45 in the paper's Table 2 and 0.46 in its Table 5 (Section 4); cited as printed.
- **Scorer freeze.** Both evaluations use scorers fixed before any run (the released scorer is hash-pinned), so the agent cannot influence its own metric.
- **Tail versus mean.** On simple parts (median 19 faces) mean fidelity is high for both libraries and the difference sits in the "badly wrong" tail; reporting only means would have hidden it, which is why the badly-wrong rate is the headline metric.
- **What was and was not re-run.** All historical measured outputs here are first-party: the DeepCAD runs were done for the paper, and the 200-part benchmark and token comparison are the released runs of the SDK repository. None were repeated during this assignment, and each has one run per arm, so I report no run-to-run mean or variance. C2 (needs the 1K subset and three external checkpoints) was not run at all. The new Hardest23 harness has offline integration checks only; these are not LLM reconstruction measurements.

## 7. Conclusions and recommendations

**What is reproducible.** My DeepCAD runs show C1's ordering, apart from the 0.45/0.46 Pass@1 discrepancy. The SDK's advantage over CadQuery appears, under one LLM and one run per arm, in the released 200-part benchmark: 4.4% vs 15.6% badly-wrong models (paired p = 0.002), 0.006 mm vs 2.885 mm mean surface error, 181 vs 173 valid deliveries, and up to 6.5× fewer tokens than an industrial CAD driven through its MCP.

**What is not established.** That the gain comes from the structured-error part of the contract (no ablation among the four sub-changes); that it holds under a stronger LLM, other parts, or repeated runs; and any direct comparison with the paper-era ECIP.

**Recommendations for future users.** (1) Re-run each arm 3–5 times and report mean and variance; (2) ablate the SDK's four sub-changes one at a time, with at least "measured errors off" as the first; (3) run a stronger LLM on the same 200 parts to test whether the gap shrinks; (4) report the badly-wrong rate next to means, since means hide the tail. Artifacts: this repository (runnable paired harness, Hardest23 cases, protocol, provenance-tracked reference results, and pipeline tests), this report, and the recorded presentation.
