"""Exercise one reverse profile inside a loopback-only Linux network namespace."""
import contextlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid

repo = Path.cwd()
binary = Path(sys.argv[1]).resolve()
profile = sys.argv[2]
if {name for _, name in socket.if_nameindex()} != {'lo'}:
    raise SystemExit('Run inside a network namespace with only lo')
is_xhttp = profile in ('c2', 'c6')
identity = str(uuid.uuid4())
short_id = secrets.token_hex(8)

def output(*args):
    return subprocess.check_output(args, text=True)

def save(path, contents):
    Path(path).write_text(json.dumps(contents))

def start(stack, *args):
    proc = subprocess.Popen(args)
    def stop():
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    stack.callback(stop)
    return proc

with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
    os.chdir(tmp)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                    'ec_paramgen_curve:P-256', '-nodes', '-keyout', 'key.pem',
                    '-out', 'cert.pem', '-days', '1', '-subj', '/CN=localhost',
                    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                   check=True, stderr=subprocess.DEVNULL)
    os.environ['SSL_CERT_FILE'] = str(Path('cert.pem').resolve())
    keys = dict(line.split(': ', 1) for line in output(binary, 'x25519').splitlines() if ': ' in line)
    pairs = re.findall(r'"(decryption|encryption)"\s*:\s*"([^"]+)"', output(binary, 'vlessenc'))
    enc = dict(pairs[-2:])
    stream = {'network': 'tcp', 'security': 'reality',
              'realitySettings': {'dest': '127.0.0.1:18444', 'serverNames': ['localhost'],
                                 'privateKey': keys['PrivateKey'], 'shortIds': [short_id]}}
    if is_xhttp:
        stream = {'network': 'xhttp', 'security': 'tls',
                  'tlsSettings': {'alpn': ['h2'], 'certificates': [
                      {'certificateFile': str(Path('cert.pem').resolve()), 'keyFile': str(Path('key.pem').resolve())}]},
                  'xhttpSettings': {'path': '/integration', 'mode': 'auto'}}
    params = {}
    for key in json.loads((repo / 'params.example.json').read_text()):
        field = key.split('XRAY_')[1]
        params[key] = {'ADDR': 'localhost', 'PORT': 18443, 'ID': identity,
                       'ID1': identity, 'ID2': identity, 'PUBLIC_KEY': keys['Password (PublicKey)'],
                       'SHORT_ID': short_id, 'SERVER_NAME': 'localhost', 'PATH': '/integration',
                       'MODE': 'auto', 'ENCRYPTION': enc['encryption']}[field]
    save('params.json', params)
    subprocess.run([sys.executable, repo / 'render.py', profile, 'params.json', 'client.json'], check=True)
    if is_xhttp:
        client_cfg = json.loads(Path('client.json').read_text())
        tls = client_cfg['outbounds'][-1]['streamSettings']['tlsSettings']
        tls['certificates'] = [{'certificateFile': str(Path('cert.pem').resolve()), 'usage': 'verify'}]
        save('client.json', client_cfg)
    account = {'id': identity, 'flow': 'xtls-rprx-vision', 'reverse': {'tag': 'bridge'}}
    save('portal.json', {'inbounds': [
        {'listen': '127.0.0.1', 'port': 18443, 'protocol': 'vless', 'settings': {
            'decryption': enc['decryption'] if is_xhttp else 'none', 'clients': [account]},
         'streamSettings': stream},
        {'listen': '127.0.0.1', 'port': 11080, 'protocol': 'socks', 'tag': 'probe'}],
        'outbounds': [{'tag': 'deny', 'protocol': 'blackhole'}], 'routing': {'rules': [
            {'inboundTag': ['probe'], 'outboundTag': 'bridge'}]}})
    token = secrets.token_hex(32)
    Path('challenge').write_text(token)
    start(stack, sys.executable, '-m', 'http.server', '18080', '--bind', '127.0.0.1')
    if not is_xhttp:
        start(stack, 'openssl', 's_server', '-accept', '127.0.0.1:18444', '-tls1_3',
              '-alpn', 'h2', '-cert', 'cert.pem', '-key', 'key.pem', '-quiet', '-www')
    portal = start(stack, binary, 'run', '-c', 'portal.json')
    client = start(stack, binary, 'run', '-c', 'client.json')
    for _ in range(60):
        if any(p.poll() is not None for p in (portal, client)):
            raise SystemExit('Xray exited before forwarding the challenge')
        result = subprocess.run(['curl', '-fsS', '--proxy', 'socks5h://127.0.0.1:11080',
                                 '--noproxy', '', '--max-time', '2',
                                 'http://127.0.0.1:18080/challenge'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout == token:
            print(f'{profile}: SOCKS request returned the exact challenge through reverse Xray')
            break
        time.sleep(0.5)
    else:
        raise SystemExit('No matching challenge received through Xray')
