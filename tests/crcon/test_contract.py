from __future__ import annotations

import json
from pathlib import Path


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "crcon_http" / "get_api_documentation_min.json"
REQUIRED_ENDPOINTS = {
    "get_map_rotation": "GET",
    "get_public_info": "GET",
    "add_map_to_rotation": "POST",
    "set_next_map": "POST",
}


def test_contract_fixture_contains_required_endpoints():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    catalog = {entry["name"]: entry for entry in data.get("result", [])}

    missing = [name for name in REQUIRED_ENDPOINTS if name not in catalog]
    assert not missing, f"Missing endpoints: {missing}"

    for name, method in REQUIRED_ENDPOINTS.items():
        entry = catalog[name]
        assert entry.get("method") == method
        assert isinstance(entry.get("args"), list)
