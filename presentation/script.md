
## Slide 1｜What I reproduced and why (0:00–0:45)

Today I reproduce **CADDesigner**, an agentic system for conceptual CAD model generation, and I make one change to it: construction-graph retrieval for its case library.

Why this paper? Because its main claim is a *controlled comparison* — three Python CAD representations driven by the exact same agent loop, on the same 200 models, scored by the same frozen evaluator. That's a claim you can actually reproduce: either the ordering holds or it doesn't.

## Slide 2｜The system in one picture (0:45–1:45)

The loop has four tools: T1 refines the user's text or sketch into a detailed spec; T2 generates code constrained by a knowledge base; T3 executes it on an OpenCascade kernel and returns measurements or a structured error; T4 renders six views and a VLM decides whether the model satisfies the spec, or feeds concrete corrections back.

Two supporting pieces matter. A SketchPad memory keeps the context bounded. And the representation itself — ECIP — makes every intermediate solid an explicit variable, with errors that say the cause, the location, and the fix. The paper's headline: ECIP reaches IoU 0.3041 and 100% delivery success, versus CadQuery at 0.2827 and 87.5% — with 30% fewer tokens.

## Slide 3｜Reproduction and replication (1:45–2:45)

To check that this ordering isn't a property of one dataset or one LLM, I report two layers. The DeepCAD evaluation as the reference runs, and an independent replication on a different benchmark: 200 real open-hardware parts, rebuild from STEP, one attempt each, frozen scorer, with DeepSeek-V4.1-Flash instead of Claude.

The ordering survives both changes: 4.4% versus 15.6% badly-wrong deliveries — 3.5 times fewer, paired p equals 0.002. Mean surface error: 0.006 millimeters versus 2.885. And against an industrial CAD driven through its MCP, the same tasks cost up to 6.5 times fewer tokens. The lesson: representation errors dominate the *worst* outcomes, not the median one.

## Slide 4｜The one change (2:45–3:45)

The paper's own ablation says removing the case library costs about 0.04 IoU — retrieval is the component worth improving. The stock retrieval scores documents by text similarity, but two cases can be textually close and structurally different.

My change: when a model is accepted into the library, also store its **construction graph** — operations, parameters, and dependencies. The API already records every call as a replayable graph, so this costs one serialization, no retraining. Retrieval then embeds that serialized graph next to the document text, plus feature-level subgraph entries obtained by walking dependency edges backward — so a query can hit a reusable pattern like sketch–extrude–chamfer, not just a whole model. The module in the repo runs with no dependencies, and its unit tests verify exactly that: the structurally matching case outranks the textually similar one.

## Slide 5｜What the change is worth (3:45–4:30)

The trained version of this mechanism was measured under the same 100-case-library protocol: text queries go from 0.2702 IoU with no retrieval, to 0.2837 with full-graph retrieval, to 0.3064 adding subgraphs; image queries go much further, from 0.2613 to 0.3852. Retrieval quality at a 1000-model corpus: R@5 0.7495 versus 0.2733 for flat chunks. Two takeaways from those numbers: subgraphs add on top of full graphs — +0.08 IoU on image queries — because a subgraph expresses a *reusable structure pattern*, which is what an image query is really asking for. And even the training-free variant captures part of the gain, because serialization puts the structure into the retrieval text; the trained encoder adds cross-modal alignment on top.

## Slide 6｜Takeaways (4:30–5:00)

Three things I take away. First, representation comparisons under a shared loop reproduce more reliably than absolute numbers — this ordering survived a change of dataset *and* a change of LLM. Second, the case library is where the leverage is: retrieval carried 0.04 IoU in the original paper. Third, structure beats text: dependency edges in the retrieval text change what comes back, before any training enters. Code, tests, and every number with its provenance are in the linked repository.
