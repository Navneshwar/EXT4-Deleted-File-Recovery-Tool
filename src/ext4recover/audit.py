"""Append-only audit trail for reproducible analysis."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def record(output: Path, action: str, **details: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    event = {"time_utc": datetime.now(timezone.utc).isoformat(), "action": action}
    event.update(details)
    with (output / "audit.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
