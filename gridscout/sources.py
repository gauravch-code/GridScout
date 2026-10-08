"""Verify payloads, not just HTTP status; preserve evidence for changing links."""
import json
from datetime import datetime, timezone

import requests

from .pipeline import checked_json
from .settings import ROOT, read_config


def verify_sources():
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for name, source in read_config("sources").items():
        if "url" not in source:
            continue
        try:
            if name == "transmission":
                metadata = checked_json(source["url"], {"f": "json"})
                names = [x["name"] for x in metadata.get("fields", [])]
                if "VOLTAGE" not in names:
                    raise ValueError("Missing voltage field")
                sample = checked_json(source["url"] + "/query", {"f": "geojson", "where": "1=1", "resultRecordCount": 1, "outFields": "VOLTAGE", "outSR": 4326})
                if not sample.get("features"):
                    raise ValueError("No geometry-bearing sample")
                evidence = {"ok": True, "fields": names, "editingInfo": metadata.get("editingInfo"), "sample_geometry": sample["features"][0]["geometry"]["type"]}
            else:
                with requests.get(source["url"], stream=True, headers={"Range": "bytes=0-1023"}, timeout=30) as response:
                    response.raise_for_status()
                    prefix = next(response.iter_content(1024))
                    if not prefix.startswith(b"PK"):
                        raise ValueError("Response is not ZIP data")
                    evidence = {"ok": True, "status": response.status_code, "content_type": response.headers.get("Content-Type"), "zip_signature": "PK", "last_modified": response.headers.get("Last-Modified")}
            result["sources"][name] = {"url": source["url"], **evidence}
        except Exception as error:
            result["sources"][name] = {"url": source["url"], "ok": False, "error": str(error)}
    target = ROOT / "docs/source-verification.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not all(s["ok"] for s in result["sources"].values()):
        raise RuntimeError(f"Some sources failed verification. See {target}; use local files or update sources config.")
    return result
