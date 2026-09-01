"""Stable JSON reports that distinguish observations from conclusions."""

import json
from pathlib import Path
from typing import Any


def write_report(output: Path, name: str, report: dict[str, Any]) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    path = output / name
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def limitations() -> list[str]:
    return [
        "Unallocated inode metadata is a candidate, not proof of deletion.",
        "Data may have been overwritten, reused, or fragmented.",
        "JBD2 journal correlation is not implemented in this release.",
        "Signature checks support consistency; they do not prove provenance.",
    ]
