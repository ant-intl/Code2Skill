"""Run artifact storage."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(
                json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n"
            )


class RunStore:
    def __init__(self, root: Path, store_full_traces: bool = True) -> None:
        self.root = root
        self.store_full_traces = store_full_traces
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def trace(
        self,
        data_id: str,
        stage: str,
        messages: Any,
        raw_response: Any = None,
        error: str = "",
    ) -> None:
        if not self.store_full_traces:
            return
        payload = {
            "stage": stage,
            "messages": messages,
            "raw_response": raw_response,
            "error": error,
        }
        with self._lock:
            write_json(self.root / "traces" / data_id / f"{stage}.json", payload)
