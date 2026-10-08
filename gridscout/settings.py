import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_config(name="scoring"):
    return json.loads((ROOT / "config" / f"{name}.json").read_text(encoding="utf-8"))
