
## Slide 1｜What I reproduced and why (0:00–0:45)

Today I reproduce **CADDesigner** — which is my own work, I'm an author — and I make one change to it: I replace its paper-era ECIP layer with our released native SDK, and measure whether that upgrade actually generates better.

Why this paper for a reproducibility project? Because its main claim is a *controlled comparison* — three Python CAD representations driven by the exact same agent loop, on the same 200 models, scored by the same frozen evaluator. Either the ordering holds or it doesn't.

## Slide 2｜The system in one picture (0:45–1:45)

The loop has four tools: T1 refines the user's text or sketch into a detailed spec; T2 generates code constrained by a knowledge base; T3 executes it on an OpenCascade kernel and returns measurements or a structured error; T4 renders six views and a VLM decides whether the model satisfies the spec, or feeds concrete corrections back.

The paper's headline: ECIP reaches IoU 0.3041 and 100% delivery success, versus CadQuery at 0.2827 and 87.5% — with 30% fewer tokens. And its ablations show one component is load-bearing: remove the structured errors and success collapses from 100% to 81.5%.

## Slide 3｜Reproduction result (1:45–2:30)

I take the DeepCAD evaluation as the reference runs and verify the claim they support: ECIP leads on fidelity, delivery success and tokens; build123d leads first-attempt rate but pays in geometric fidelity. That ordering is the claim, and it holds.

## Slide 4｜The one change (2:30–3:30)

Since the contract is load-bearing, that's what I change. Paper-era ECIP was a thin Python layer over CadQuery: errors were exception-level triples, selection reached into fluent chains. The released native SDK replaces that: errors state what happened *with the measured numbers and units* and the fix; geometry is selected by what it *is* — stable references — not by indices that shift; and every call is recorded as a replayable session graph.

And the evaluation is conditional generation: the condition is a reference part — 200 real open-hardware parts as STEP — the output is parametric code, and both arms run on the *same* LLM, one attempt each, frozen scorer. Paired.

## Slide 5｜What the change is worth (3:30–4:30)

The released 200-part benchmark reports 4.4% versus 15.6% delivered-but-badly-wrong — 3.5 times fewer, paired p equals 0.002. Mean surface error: 0.006 millimeters versus 2.885. Valid deliveries: 181 versus 173. And against an industrial CAD driven through its MCP, the same tasks cost up to 6.5 times fewer tokens. These are historical reference runs, not new runs from the coursework harness. I don't claim a direct new-versus-old-ECIP delta: different model, different dataset, so no paired comparison exists.

## Slide 6｜Takeaways (4:30–5:00)

The paired released experiment supports an SDK-level advantage under its stated conditions; it does not isolate the SDK's individual changes or establish robustness across models. The repository provides a runnable reproduction pipeline organized after BenchCAD 2.0, with 23 difficult cases, paired runs, explicit submission, retained transcripts, and the original report's geometry metrics. Offline checks pass; new LLM reconstruction measurements remain to be collected. Report the selected 23-case results separately from the historical 200-part results.
