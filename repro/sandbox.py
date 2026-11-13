from __future__ import annotations

import os
import signal
import stat
import subprocess
import uuid
from pathlib import Path


def regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def bounded(text: str, limit: int = 10000) -> str:
    data = text.encode()
    if len(data) <= limit:
        return text
    return (data[:limit // 2].decode(errors="ignore") + "\n[... middle omitted ...]\n"
            + data[-limit // 2:].decode(errors="ignore"))


def execute(command: list[str], *, cwd: Path, timeout: int, env=None) -> dict:
    with (cwd / "stdout.log").open("w") as stdout, (cwd / "stderr.log").open("w") as stderr:
        proc = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                env=env, start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    return {
        "returncode": proc.returncode, "timed_out": timed_out,
        "stdout": bounded((cwd / "stdout.log").read_text(errors="replace")),
        "stderr": bounded((cwd / "stderr.log").read_text(errors="replace")),
    }


def run_code(code: str, directory: Path, *, image: str, timeout: int,
             local_python: str | None = None) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "program.py").write_text(code)
    before = {p.name: p.read_bytes() for p in directory.glob("*.png") if regular(p)}
    name = "ip2-" + uuid.uuid4().hex
    if local_python:
        env = {k: v for k, v in os.environ.items()
               if k in ("PATH", "SYSTEMROOT", "TMPDIR", "LANG", "LC_ALL")}
        env.update(HOME=str(directory), MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1")
        # Keep the venv's executable path: resolving its symlink loses pyvenv.cfg.
        result = execute([str(Path(local_python).absolute()), "program.py"],
                         cwd=directory, timeout=timeout, env=env)
    else:
        command = ["docker", "run", "--rm", "--name", name, "--network", "none",
                   "--read-only", "--memory", "2g", "--cpus", "1", "--pids-limit", "128",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--tmpfs", "/tmp:rw,size=512m", "-v", f"{directory.resolve()}:/work:rw",
                   "-w", "/work", image, "python", "program.py"]
        try:
            result = execute(command, cwd=directory, timeout=timeout)
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20)
    # Logs are kept outside the conversation; only bounded text and changed PNGs return.
    result["images"] = [p for p in sorted(directory.glob("*.png"))
                        if regular(p) and p.stat().st_size <= 8_000_000
                        and before.get(p.name) != p.read_bytes()]
    return result


def finalise(arm: str) -> str:
    if arm == "cadquery":
        return """
import cadquery as _cq
if 'result' not in globals():
    raise ValueError('Submitted program must leave result')
_cq.exporters.export(result, 'final.step')
"""
    return """
import simplecadapi as _scad
from simplecadapi.exporter.step import export_product_package_to_step as _to_step
if 'result' not in globals():
    raise ValueError('Submitted program must leave result')
_scad.capture(result, 'final.scadpkg', include_scene=False)
_to_step(data='final.scadpkg', output_path='final.step')
"""
