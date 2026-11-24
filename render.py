import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description="生成单个出口实例的 Xray 配置")
parser.add_argument("node", choices=("2h", "6h", "c2", "c6"))
parser.add_argument("params", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
params = json.loads(args.params.read_text())


def replace(value):
    if isinstance(value, dict):
        return {key: replace(item) for key, item in value.items()}
    if isinstance(value, list):
        return [replace(item) for item in value]
    if isinstance(value, str) and value.startswith(("XRAY_", "C2_XRAY_", "C6_XRAY_")):
        entry = params.get(value)
        if entry is None or entry == "":
            raise SystemExit(f"缺少参数 {value}")
        if value.endswith("_PORT"):
            port = int(entry)
            if not 1 <= port <= 65535:
                raise SystemExit(f"{value} 超出端口范围")
            return port
        return entry
    return value


template = Path(__file__).with_name(f"{args.node}.template.json")
content = json.dumps(replace(json.loads(template.read_text())), indent=2)
with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
    out.write(content + "\n")
