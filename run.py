#!/usr/bin/env python3
"""One-command setup and launcher for InterviewForge. Works the same on Windows, macOS and Linux.

    python run.py              install whatever is missing, start the app and open http://localhost:5173
    python run.py install      only install / update dependencies
    python run.py test         run the backend and frontend test suites

Options: --no-browser (don't open a browser tab), --smoke (start, check both servers answer, then stop; used by CI).

Only the Python standard library is used here, so this script runs before anything is installed.
On Windows you can also double-click start.bat.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"
IS_WINDOWS = os.name == "nt"
VENV_PY = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
API_PORT = int(os.environ.get("INTERVIEWFORGE_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("INTERVIEWFORGE_WEB_PORT", "5173"))
APP_URL = f"http://localhost:{WEB_PORT}"
HEALTH_URL = f"http://127.0.0.1:{API_PORT}/api/health"
# Every pinned backend dependency ships prebuilt Windows/macOS/Linux wheels for these versions.
MIN_PY, MAX_PY = (3, 11), (3, 14)
MIN_NODE = (20, 19)


def say(msg: str = "") -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    say()
    say(f"  ERROR: {msg}")
    say()
    sys.exit(1)


def child_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    # UTF-8 everywhere: Windows consoles otherwise default to a legacy code page.
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", **extra)
    return env


def run(cmd: list[str], cwd: Path = ROOT, **extra_env: str) -> None:
    say(f"  > {' '.join(str(c) for c in cmd)}")
    code = subprocess.call(cmd, cwd=str(cwd), env=child_env(**extra_env))
    if code != 0:
        fail(f"command failed (exit code {code}): {' '.join(str(c) for c in cmd)}")


def digest(*files: Path) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- prerequisites


def check_python() -> None:
    v = sys.version_info[:2]
    if not (MIN_PY <= v <= MAX_PY):
        fail(
            f"Python {v[0]}.{v[1]} is not supported. Install Python 3.12 or 3.13 from https://www.python.org/downloads/ "
            f"(supported: {MIN_PY[0]}.{MIN_PY[1]} to {MAX_PY[0]}.{MAX_PY[1]})."
            + (" On Windows, tick 'Add python.exe to PATH' in the installer." if IS_WINDOWS else "")
        )


def find_npm() -> str:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        fail("Node.js was not found. Install the LTS version from https://nodejs.org/ and open a new terminal.")
    out = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout.strip().lstrip("v")
    try:
        version = tuple(int(p) for p in out.split(".")[:2])
    except ValueError:
        version = (0, 0)
    if version < MIN_NODE:
        fail(f"Node.js {out or '?'} is too old. Install the LTS version (22 or newer) from https://nodejs.org/.")
    return npm  # type: ignore[return-value]


# --------------------------------------------------------------------------- install


def venv_ok() -> bool:
    if not VENV_PY.exists():
        return False
    probe = "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] else 1)"
    return subprocess.call([str(VENV_PY), "-c", probe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def install_backend(dev: bool, force: bool = False) -> None:
    if not venv_ok():
        say("Creating the Python virtual environment (backend/.venv) ...")
        if VENV.exists():
            shutil.rmtree(VENV, ignore_errors=True)  # broken, e.g. the folder was moved or Python was upgraded
        code = subprocess.call([sys.executable, "-m", "venv", str(VENV)])
        if code != 0 or not VENV_PY.exists():
            hint = "sudo apt install python3-venv" if sys.platform.startswith("linux") else "reinstall Python"
            fail(f"could not create a virtual environment. Try: {hint}")
        force = True
    req = BACKEND / ("requirements-dev.txt" if dev else "requirements.txt")
    stamp = VENV / ".installed"
    want = f"{'dev' if dev else 'app'}:{digest(BACKEND / 'requirements.txt', BACKEND / 'requirements-dev.txt')}"
    have = stamp.read_text(encoding="utf-8").splitlines() if stamp.exists() else []
    # A dev install also covers the app requirements.
    if not force and (want in have or (not dev and want.replace("app:", "dev:", 1) in have)):
        return
    say("Installing backend dependencies (first run takes a minute) ...")
    run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"])
    run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req)])
    stamp.write_text(want + "\n", encoding="utf-8")


def install_frontend(force: bool = False) -> None:
    npm = find_npm()
    modules = FRONTEND / "node_modules"
    stamp = modules / ".interviewforge-installed"
    want = digest(FRONTEND / "package-lock.json")
    if not force and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == want:
        return
    say("Installing frontend dependencies (first run takes a minute) ...")
    run([npm, "ci", "--no-audit", "--no-fund", "--loglevel=error"], cwd=FRONTEND)
    stamp.write_text(want, encoding="utf-8")


def install(dev: bool = False, force: bool = False) -> None:
    check_python()
    find_npm()
    install_backend(dev, force)
    install_frontend(force)


# --------------------------------------------------------------------------- start


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def fetch(url: str, timeout: float = 2.0) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except (OSError, http.client.HTTPException):  # refused, timed out, reset, HTTP error status
        return 0, b""


def report_ai_status(health: bytes) -> None:
    try:
        h = json.loads(health)
    except ValueError:
        return
    if h.get("llm") == "ok":
        say(f"  Local AI: connected ({h.get('model')})")
        return
    say("  Local AI: not connected - the app still works with its built-in offline engine.")
    if h.get("ollama_server") != "ok":
        say("            For AI questions and feedback, install Ollama from https://ollama.com/download")
        say(f"            and run:  ollama pull {h.get('model') or 'qwen2.5:3b'}")
    elif h.get("installed_models"):
        say(f"            '{h.get('model')}' is not installed. Either run:  ollama pull {h.get('model')}")
        say(f"            or choose one of your models ({', '.join(h['installed_models'])}) in the app under Settings.")
    else:
        say(f"            Ollama is running but has no models. Run:  ollama pull {h.get('model') or 'qwen2.5:3b'}")


def stop(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    deadline = time.time() + 5
    for p in procs:
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()


def start(open_browser: bool, smoke: bool) -> None:
    for port, what in ((API_PORT, "backend"), (WEB_PORT, "frontend")):
        if port_busy(port):
            if port == API_PORT and fetch(HEALTH_URL)[0] == 200:
                fail(f"InterviewForge already seems to be running. Open {APP_URL} or stop the other window first.")
            fail(
                f"port {port} (needed for the {what}) is used by another program. Close it, or pick other ports, "
                "e.g. set INTERVIEWFORGE_API_PORT=8010 and INTERVIEWFORGE_WEB_PORT=5180."
            )

    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    node = shutil.which("node")
    if not vite.exists() or not node:
        fail("frontend dependencies are missing. Run: python run.py install")

    procs = [
        subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
            cwd=str(BACKEND),
            env=child_env(CORS_ORIGINS=f"http://localhost:{WEB_PORT},http://127.0.0.1:{WEB_PORT}"),
        ),
        subprocess.Popen(
            [node, str(vite), "--port", str(WEB_PORT), "--strictPort"],
            cwd=str(FRONTEND),
            env=child_env(VITE_API_TARGET=f"http://127.0.0.1:{API_PORT}"),
        ),
    ]
    try:
        say("Starting InterviewForge ...")
        health = b""
        web_ok = False
        deadline = time.time() + 90
        while time.time() < deadline and not (health and web_ok):
            if any(p.poll() is not None for p in procs):
                fail("a server stopped while starting; see the messages above.")
            if not health:
                code, body = fetch(HEALTH_URL)
                health = body if code == 200 else b""
            if not web_ok:
                web_ok = fetch(APP_URL)[0] == 200
            time.sleep(0.5)
        if not (health and web_ok):
            fail("the servers did not start within 90 seconds; see the messages above.")

        say()
        say("  ============================================================")
        say(f"   InterviewForge is running:  {APP_URL}")
        say("   Keep this window open. Press Ctrl+C to stop.")
        say("  ============================================================")
        report_ai_status(health)
        say()
        if smoke:
            code, _ = fetch(f"{APP_URL}/api/health")  # through the Vite proxy, as the browser does
            if code != 200:
                fail("the frontend could not reach the backend through its /api proxy.")
            say("Smoke test passed.")
            return
        if open_browser:
            webbrowser.open(APP_URL)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        fail("a server stopped unexpectedly; see the messages above.")
    except KeyboardInterrupt:
        say("\nStopping ...")
    finally:
        stop(procs)


# --------------------------------------------------------------------------- main


def main(argv: list[str]) -> None:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    command = args[0] if args else "start"
    os.chdir(ROOT)
    if command == "install":
        install(dev="--dev" in flags, force=True)
        say("Done. Start the app with: python run.py")
    elif command == "test":
        install(dev=True)
        run([str(VENV_PY), "-m", "pytest", "-q"], cwd=BACKEND)
        run(
            [shutil.which("node") or "node", str(FRONTEND / "node_modules" / "vitest" / "vitest.mjs"), "run"],
            cwd=FRONTEND,
        )
        say("All tests passed.")
    elif command == "start":
        install(dev=False)
        start(open_browser="--no-browser" not in flags and "--smoke" not in flags, smoke="--smoke" in flags)
    else:
        say(__doc__ or "")
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
