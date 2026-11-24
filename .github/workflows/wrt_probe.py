"""Accept a single round-trip proof through the configured wrt1k reverse peer."""
import hmac
import json
import os
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import sys
import tempfile
import time

binary, profile = sys.argv[1:]
root = Path(__file__).resolve().parents[2]
os.umask(0o077)
nonce = secrets.token_hex(32)


class Proof(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == f"/{profile}/challenge":
            data = nonce.encode()
        elif hmac.compare_digest(self.path.encode(), (f"/{profile}/confirm/" + nonce).encode()):
            self.server.confirmed = True
            data = b"ok"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory() as folder, HTTPServer(("127.0.0.1", 18080), Proof) as server:
    server.timeout = 1
    server.confirmed = False
    params = Path(folder, "params.json")
    params.write_text(os.environ.pop("PROFILE_PARAMS"))
    cfg = Path(folder, "probe.json")
    subprocess.run([sys.executable, root / "render.py", profile, params, cfg], check=True)
    config = json.loads(cfg.read_text())
    peer = next(item for item in config["outbounds"] if item["protocol"] == "vless")
    tag = peer["settings"]["reverse"]["tag"]
    config["outbounds"] = [
        {"tag": "deny", "protocol": "blackhole"},
        {"tag": "proof", "protocol": "freedom", "settings": {
            "redirect": "127.0.0.1:18080",
            "finalRules": [{"action": "allow", "network": "tcp", "ip": ["127.0.0.1/32"], "port": "18080"}],
        }},
        peer,
    ]
    config["routing"] = {"rules": [
        {"type": "field", "inboundTag": [tag], "network": "tcp", "ip": ["127.0.0.1/32"],
         "port": "18080", "outboundTag": "proof"},
    ]}
    cfg.write_text(json.dumps(config))
    subprocess.run([binary, "run", "-test", "-c", cfg], check=True)
    proc = subprocess.Popen([binary, "run", "-c", cfg])
    try:
        end = time.monotonic() + 150
        while time.monotonic() < end and proc.poll() is None and not server.confirmed:
            server.handle_request()
        if not server.confirmed:
            raise SystemExit("No round-trip proof from wrt1k")
        print(f"{profile}: wrt1k returned the challenge from this runner")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
