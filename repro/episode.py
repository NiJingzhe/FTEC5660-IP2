from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from .cases import write_json
from .provider import content
from .sandbox import finalise, regular, run_code

FENCE = re.compile(r"\A\s*```(python|py|submit)\s*\n(.*?)\n```\s*\Z", re.S | re.I)


def parse_reply(text: str) -> tuple[str, str] | None:
    match = FENCE.fullmatch(text)
    if not match or not match[2].strip() or "```" in match[2]:
        return None
    return match[1].lower(), match[2]


def run_episode(*, case: Path, arm: str, config: dict, root: Path, call,
                vision: bool = False, local_python: str | None = None,
                guidance: str = "") -> dict:
    work = root / "investigation"
    work.mkdir(parents=True, exist_ok=False)
    for source in (case / "input").iterdir():
        shutil.copy2(source, work / source.name)
    package = config["arms"][arm]
    brief = (Path(__file__).resolve().parents[1] / "envs/step2code/TASK.md").read_text()
    system = f"""{brief}
Library: {arm} {package['version']}. Python 3.12, Pillow. No network.
Limits: {config['rounds']} replies, {config['output_token_budget']} output tokens
(reasoning included, checked between calls), {config['execution_timeout']} s per execution.
Reply with exactly one fenced block, with no text outside:
```python
# Investigation code. Fresh process, persistent files; stdout/stderr and changed PNGs return.
```
or
```submit
# Complete standalone modeling program. Leaves result. Ends the episode.
```
The submitted program is run once in an empty directory with no investigation files.
The harness exports result to final.step. For SimpleCADAPI use a @scad.part
builder and assign its returned PartBuildResult to result (capture exports it).
For CadQuery leave a Workplane or Shape in result.
No submit or a crashed submission counts as a failed delivery.
Scoring is outside this work directory. No reference score is fed back.
Text feedback is limited to 10,000 bytes per stream, keeping head and tail.
{'PNG observations are attached.' if vision else 'Text-only run: images remain files; you may inspect them in Python.'}
{guidance}
"""
    images = sorted(work.glob("*.png"))
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": content("Reconstruct target.step. Files: target.step, preview.png.", images, vision=vision)}]
    (root / "system.txt").write_text(system)
    records, tokens, spent = [], {"prompt_tokens": 0, "completion_tokens": 0}, 0
    status, artifact = "no_submission", None
    start = time.monotonic()
    for rnd in range(1, config["rounds"] + 1):
        if spent >= config["output_token_budget"]:
            break
        try:
            response = call(messages)
        except Exception as exc:
            # Infrastructure failures remain pending; resume starts a fresh episode.
            status = "provider_error"
            records.append({"round": rnd, "error": str(exc)})
            break
        write_json(root / f"round_{rnd:03d}/response.json", response)
        usage = response["usage"]
        for key in tokens:
            tokens[key] += int(usage.get(key, 0))
        spent = tokens["completion_tokens"]
        message = response["message"]
        messages.append(message)
        parsed = parse_reply(message["content"])
        item = {"round": rnd, "usage": usage, "finish_reason": response.get("finish_reason"),
                "model_returned": response.get("model")}
        if parsed is None:
            item["action"] = "invalid_format"
            observation = "No executable block. Reply with exactly one complete python or submit fenced block."
            new_images = []
        else:
            kind, code = parsed
            item["action"] = kind
            (root / f"round_{rnd:03d}/code.py").write_text(code)
            final = kind == "submit"
            directory = root / "submission" if final else work
            if final:
                (root / "submitted.py").write_text(code)
            try:
                execution = run_code(code + (finalise(arm) if final else ""), directory,
                                     image=package["image"], timeout=config["execution_timeout"],
                                     local_python=local_python)
            except OSError as exc:
                status = "sandbox_error"
                item["error"] = type(exc).__name__
                records.append(item)
                break
            new_images = execution.pop("images")
            write_json(root / f"round_{rnd:03d}/execution.json", execution)
            for name in ("stdout.log", "stderr.log"):
                shutil.copy2(directory / name, root / f"round_{rnd:03d}" / name)
            item.update(returncode=execution["returncode"], timed_out=execution["timed_out"])
            if execution["returncode"] in (125, 126, 127) and not local_python:
                status = "sandbox_error"
                records.append(item)
                break
            if final:
                candidate = directory / "final.step"
                if execution["returncode"] == 0 and regular(candidate) and candidate.stat().st_size:
                    status, artifact = "submitted", candidate
                else:
                    status = "submission_failed"
                records.append(item)
                break
            observation = (f"exit {execution['returncode']}; timeout={execution['timed_out']}\n"
                           f"stdout:\n{execution['stdout']}\nstderr:\n{execution['stderr']}\n"
                           f"Images: {', '.join(p.name for p in new_images) or 'none'}")
        records.append(item)
        messages.append({"role": "user", "content": content(
            f"Round {rnd}/{config['rounds']} · output tokens {spent}/{config['output_token_budget']}\n" + observation,
            new_images, vision=vision)})
    write_json(root / "transcript.json", messages)
    return {"status": status, "artifact": str(artifact.resolve()) if artifact else None,
            "rounds": records, "tokens": tokens, "seconds": round(time.monotonic() - start, 3)}
