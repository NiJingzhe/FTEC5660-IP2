# FTEC5660 IP2 — CADDesigner reproduction

A runnable **STEP → parametric code → independently scored geometry** experiment,
comparing **SimpleCADAPI 2.2.7b1** with **CadQuery 2.8.0** on the supplied
**Hardest23** subset of a 200-part open-hardware bank.

The harness follows [BenchCAD **2.0**](https://github.com/BenchCAD-org/benchcad-2-main):
case manifests with hashed files, persistent investigation directories, multi-round
Python execution, an explicit `submit`, isolated final execution, and a separate
deterministic scorer. It is a custom STEP-conditioned task, **not a BenchCAD Core
task or leaderboard result**. No construction-graph retrieval is part of this project.

CADDesigner is my own paper; SimpleCADAPI is our SDK. See [REPORT.md](REPORT.md)
for the original claims and the provenance of the historical measurements.

## Install

Python 3.12, [uv](https://docs.astral.sh/uv/), Git, and Docker are needed.

```bash
uv sync --locked

docker build --build-arg 'CAD_PACKAGE=cadquery==2.8.0' \
  -t ip2-cadquery:2.8.0 sandbox/
docker build --build-arg 'CAD_PACKAGE=simplecadapi==2.2.7b1' \
  -t ip2-simplecadapi:2.2.7b1 sandbox/
```

The host/scorer environment is pinned in `uv.lock`; the sandbox fixes the CAD
package versions. Transitive sandbox packages currently resolve at image build
time. Runs record and execute the resolved image IDs; rebuilds are not byte-identical.
The independent scorer uses the original report's metric definitions.
BenchCAD 2.0 is a reference for harness organization only.

## Data

All **23 prepared cases** are included in `data/hardest23/`, with their original
attribution and licenses. No download or access to a WeChat path is needed to run.
The source archive is not required. To recreate the cases into a *new* directory:

```bash
uv sync --locked --group data
uv run python tools/prepare_cases.py /path/to/cases_Hardest23.7z --out data/recreated
```

Each case contains:

```text
case010/
  case.json                  hashes, units, task, split
  input/target.step          reference the agent may inspect
  input/preview.png          supplied overview
  gt/gt.step                 scorer reference
  provenance/                original metadata, ATTRIBUTION.txt, LICENSE.txt
```

Here `input/target.step` intentionally equals `gt/gt.step`: the task is
reconstruction from geometry. This differs from BenchCAD 2.0 T3, whose input is
views alone. Only `input/` is staged for investigation; only the submitted Python
program is staged for final execution. The final program must build from parameters
without reading the target or earlier investigation files.

Hardest23 is a **selected difficult subset**, not a random sample. The original
selection/ranking rule is not independently verified. Its scores must not be
presented as measurements on the full 200 cases.

## Run

Validate every manifest and inspect the resolved protocol without API calls:

```bash
uv run python run.py --model YOUR_MODEL_ID --dry-run
```

Supply an accessible OpenAI-compatible Chat Completions endpoint. `.env.example`
lists the environment variables; the harness does not read `.env` automatically.

```bash
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_API_KEY=...  # keep this in your environment, never a committed file

# One case, both arms; budget-limited smoke, not the default protocol
uv run python run.py --model YOUR_MODEL_ID --limit 1 --rounds 3 \
  --out results/runs/smoke.json

# All 23 cases, paired; repeat with --rep 1 / 2 and separate output files
uv run python run.py --model YOUR_MODEL_ID --rep 0 \
  --out results/runs/paired-r0.json
uv run python run.py --model YOUR_MODEL_ID --rep 0 \
  --out results/runs/paired-r0.json --resume

uv run python tools/summarize.py results/runs/paired-r0.json
```

Default limits in `configs/paired.json`: **60 replies**, **500,000 output tokens**
including reasoning, checked between calls, **600 seconds** per execution,
**2 GB / 1 CPU**, no network inside Docker. Every API reply counts as one round,
including an invalid-format reply. This is our explicit simplified protocol;
BenchCAD's discarded-call and provider-specific reasoning policies are not reproduced.

By default the API receives **text only**. The agent can inspect STEP and image
files in Python. `--vision` attaches the supplied preview and generated PNGs for
a vision-capable model; use the same setting for both arms. No endpoint fallback,
model substitution, or decoding-parameter fallback is applied. A provider error
stays pending. Provider-reported completion tokens are required for budget accounting.

For optional library guides, `--guidance guides.json` takes a JSON object mapping
each arm to a UTF-8 file path relative to that JSON. Both texts are retained in
`system.txt` and their hashes enter the protocol. Omit it to use the same task
brief with only the library/output interface changed. The historical 200-part
experiment used different guides; a new run without them is a different setting.

Each reply contains exactly one `python` or `submit` fenced block. Investigation
files persist, process memory does not. A submitted program runs once in a clean
directory. No submission or a broken submission is a failed delivery; no earlier STEP is
substituted. Provider, Docker, and scorer infrastructure errors remain pending.
`--resume` reruns pending episodes and rejects changed settings, cases, or harness
code. It does not continue a partially completed conversation.

## Scores and artifacts

The geometry metrics follow the original evaluation report:

```text
Material IoU: OCCT intersection / union volume, fuzzy tolerance 1e-7 mm
F1 @ 1 mm: harmonic mean of bidirectional precision and recall
Chamfer L1 (mm): mean of the two directed mean surface distances
Hausdorff (mm): maximum of the two directed sampled surface distances
Badly wrong: F1 @ 1 mm < 99.99%, among valid deliveries
```

Distances use 10,000 area-weighted samples in each direction, in millimetres,
without registration or scale normalization. Valid delivery requires a submitted
program, a reloadable valid BREP and geometry kind matching the reference.
Missing models count as failed deliveries, never zero surface error.

The original frozen `evaluator.py` was not included in the supplied archive.
This implementation follows the report's definitions; its seed, meshing and
distance implementation are explicit in `configs/paired.json` and
`repro/scoring.py`. Byte-for-byte equivalence to the historical evaluator has
not been established. See [docs/PROTOCOL.md](docs/PROTOCOL.md).

Each output JSON binds the cases, model, endpoint, budgets, prompt/harness code,
guidance, scorer source, and lockfile. `work/<run>/...` retains every reply,
code block, bounded execution record, full stdout/stderr, transcript, submitted
program, final STEP, and scorer diagnostics. Summaries suppress a headline mean
when any expected case is pending. A source review of submitted programs remains
necessary: geometric similarity alone does not prove useful parametric design.

Historical numbers live in `results/deepcad_reference.json` and
`results/released_benchmark.json`; they are references, not outputs of this harness.
`results/validation*.json` record only offline pipeline checks. No paid LLM run
has been made as part of the repository restructuring.

## Verify without an API key

```bash
uv run python -m unittest discover -s tests -v
uv run python tools/check_pipeline.py
uv run python tools/check_pipeline.py --docker

# Optional: also verify native SDK export in its separate environment
uv venv --python 3.12 .venv-sdk
uv pip install --python .venv-sdk/bin/python simplecadapi==2.2.7b1
uv run python tools/check_pipeline.py --sdk-python .venv-sdk/bin/python

# Exercise an episode that deliberately never submits; expected failed delivery
uv run python run.py --model mock/no-submit --arms cadquery --rounds 1 --limit 1 \
  --out results/runs/mock.json
```

`--local-python PATH` explicitly enables local subprocess execution for smoke
checks only. Docker is the default, and there is no silent local fallback.

## Layout

```text
run.py                      paired experiment entry point
configs/paired.json         versioned protocol and metric definitions
envs/step2code/TASK.md       shared task brief
repro/                      cases, episode, provider, sandbox, scoring
sandbox/Dockerfile          one CAD library per arm
data/hardest23/             23 runnable cases, references and source licenses
tools/                      preparation, scorer setup, summary, offline checks
tests/                      protocol and result-accounting tests
results/                    historical references and offline validation
REPORT.md / REPORT.typ      report sources
presentation/               existing presentation sources and media
```
