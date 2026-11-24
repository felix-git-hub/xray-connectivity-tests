"""Run xray with the rendered profile config until the job ends."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

binary, profile = sys.argv[1:]
root = Path(__file__).resolve().parents[2]
os.umask(0o077)

with tempfile.TemporaryDirectory() as folder:
    params = Path(folder, "params.json")
    params.write_text(os.environ.pop("PROFILE_PARAMS"))
    cfg = Path(folder, "config.json")
    subprocess.run([sys.executable, root / "render.py", profile, params, cfg], check=True)
    subprocess.run([binary, "run", "-test", "-c", cfg], check=True)
    print(f"{profile}: running xray until the job ends", flush=True)

    proc = subprocess.Popen([binary, "run", "-c", cfg])
    try:
        sys.exit(proc.wait())
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
