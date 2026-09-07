"""Configuration for the local Code2Skill pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


def _default_extensions() -> List[str]:
    return [
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".java",
        ".rs",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
    ]


def _default_skip_dirs() -> List[str]:
    return [
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        "target",
        "vendor",
        "third_party",
        ".next",
        ".cache",
    ]


@dataclass
class ModelConfig:
    base_url: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 120
    max_retries: int = 2
    allow_public_url: bool = False
    temperature: float = 0.0
    max_json_tokens: int = 4096
    max_code_tokens: int = 8192

    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    def resolved_base_url(self) -> str:
        if not self.base_url.startswith("env:"):
            return self.base_url
        env_name = self.base_url.removeprefix("env:").strip()
        if not env_name:
            raise ValueError("model.base_url contains an empty environment reference")
        value = os.environ.get(env_name, "").strip()
        if not value:
            raise ValueError(f"Model URL environment variable {env_name!r} is not set")
        return value


@dataclass
class ScanConfig:
    allowed_extensions: List[str] = field(default_factory=_default_extensions)
    skip_dirs: List[str] = field(default_factory=_default_skip_dirs)
    include_tests: bool = False
    min_unit_lines: int = 3
    max_file_bytes: int = 200_000
    max_unit_bytes: int = 12_000
    max_units_per_repo: int = 400


@dataclass
class PipelineOptions:
    concurrency: int = 4
    min_selection_score: float = 0.50
    min_skill_value_score: float = 0.45
    build_purpose_index: bool = True
    store_full_traces: bool = True


@dataclass
class AppConfig:
    model: ModelConfig
    scan: ScanConfig = field(default_factory=ScanConfig)
    pipeline: PipelineOptions = field(default_factory=PipelineOptions)
    output_dir: str = "runs"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AppConfig":
        model_payload = dict(payload.get("model") or {})
        if not model_payload.get("base_url") or not model_payload.get("model"):
            raise ValueError("model.base_url and model.model are required")
        return cls(
            model=ModelConfig(**model_payload),
            scan=ScanConfig(**dict(payload.get("scan") or {})),
            pipeline=PipelineOptions(**dict(payload.get("pipeline") or {})),
            output_dir=str(payload.get("output_dir") or "runs"),
        )

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Configuration root must be a JSON object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if self.pipeline.concurrency < 1:
            raise ValueError("pipeline.concurrency must be at least 1")
        if self.scan.min_unit_lines < 1:
            raise ValueError("scan.min_unit_lines must be at least 1")
        if self.scan.max_units_per_repo < 1:
            raise ValueError("scan.max_units_per_repo must be at least 1")
        for name, value in (
            ("pipeline.min_selection_score", self.pipeline.min_selection_score),
            ("pipeline.min_skill_value_score", self.pipeline.min_skill_value_score),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
