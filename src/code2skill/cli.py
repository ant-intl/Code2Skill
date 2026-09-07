"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from .config import AppConfig, ModelConfig
from .pipeline import Code2SkillPipeline
from .prompts import (
    adjudication_messages,
    demo_unit,
    equivalence_messages,
    extraction_messages,
    feature_messages,
    regeneration_messages,
    source_tag_messages,
)
from .purpose import build_purpose_index
from .schemas import SkillRecord, SourceUnitTag
from .storage import write_jsonl


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number} is not a JSON object")
            records.append(value)
    return records


def _demo_values() -> Any:
    tag = SourceUnitTag(
        True,
        "Contains retry control and an explicit terminal failure.",
        0.9,
        0.9,
        0.8,
        0.9,
        0.9,
        0.9,
    )
    skill = SkillRecord(
        level="composite",
        name="Bounded retry with terminal failure",
        summary="Attempt an operation up to a fixed bound and raise a terminal error after repeated transient failures.",
        worth_extracting=True,
        worth_reason="Reusable recovery workflow.",
        skill_value_score=0.9,
        generality_score=0.9,
        abstraction_score=0.8,
        inputs=["Operation and retry bound"],
        outputs=["First successful result"],
        workflow=[
            "Attempt the operation",
            "Retry transient failures",
            "Raise after exhaustion",
        ],
        invariants=["Never exceed the retry bound"],
        error_cases=["All attempts fail"],
        implementation_notes=["Preserve the original interface"],
        evidence=["Bounded loop and terminal raise"],
        anti_goals=["Do not retry forever"],
        confidence=0.9,
    )
    return demo_unit(), tag, skill


def _show_prompt(stage: str) -> List[Dict[str, str]]:
    unit, tag, skill = _demo_values()
    generated = "def fetch_with_retry(fetch, attempts):\n    ..."
    payload = {
        "data_id": unit.data_id,
        "repo_name": unit.repo_name,
        "relative_path": unit.relative_path,
        "symbol": unit.symbol,
        "accepted_stage": "equivalence",
        "rationale": "Equivalent",
        **asdict(skill),
    }
    payload.pop("name", None)
    payload.pop("worth_reason", None)
    builders = {
        "source_tagging": lambda: source_tag_messages(unit),
        "extraction": lambda: extraction_messages(unit, tag),
        "regeneration": lambda: regeneration_messages(unit, skill),
        "equivalence": lambda: equivalence_messages(unit, skill, generated),
        "adjudication": lambda: adjudication_messages(
            unit, skill, generated, "Missing terminal failure"
        ),
        "feature_tagging": lambda: feature_messages(payload),
    }
    return builders[stage]()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code2skill",
        description="Build grounded procedural skills from source code",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run the end-to-end pipeline")
    run.add_argument("input", help="Repository or directory of repositories")
    run.add_argument("--config", help="JSON configuration file")
    run.add_argument("--base-url", help="OpenAI-compatible API base URL")
    run.add_argument("--model", help="Model name")
    run.add_argument("--api-key-env", default="OPENAI_API_KEY")
    run.add_argument(
        "--output-dir", help="Run directory (defaults to config value or runs/latest)"
    )
    run.add_argument("--allow-public-model-url", action="store_true")

    show = subparsers.add_parser(
        "show-prompts", help="Print one stage's model-visible messages"
    )
    show.add_argument(
        "--stage",
        required=True,
        choices=[
            "source_tagging",
            "extraction",
            "regeneration",
            "equivalence",
            "adjudication",
            "feature_tagging",
        ],
    )

    purpose = subparsers.add_parser(
        "purpose-index", help="Build the deterministic purpose view"
    )
    purpose.add_argument("input", help="Accepted-record JSONL")
    purpose.add_argument("output", help="Purpose-card JSONL")
    return parser


def main(argv: Any = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show-prompts":
        print(json.dumps(_show_prompt(args.stage), ensure_ascii=False, indent=2))
        return 0
    if args.command == "purpose-index":
        output = Path(args.output).expanduser().resolve()
        cards, edges, dropped = build_purpose_index(
            _read_jsonl(Path(args.input).expanduser())
        )
        write_jsonl(output, cards)
        write_jsonl(output.with_name(output.stem + "_edges.jsonl"), edges)
        write_jsonl(output.with_name(output.stem + "_dropped.jsonl"), dropped)
        print(
            json.dumps(
                {
                    "purpose_cards": len(cards),
                    "edges": len(edges),
                    "dropped": len(dropped),
                    "output": str(output),
                },
                indent=2,
            )
        )
        return 0
    if args.config:
        config = AppConfig.load(args.config)
        if args.output_dir:
            config.output_dir = args.output_dir
    else:
        if not args.base_url or not args.model:
            raise SystemExit("run requires --config, or both --base-url and --model")
        config = AppConfig(
            model=ModelConfig(
                base_url=args.base_url,
                model=args.model,
                api_key_env=args.api_key_env,
                allow_public_url=args.allow_public_model_url,
            ),
            output_dir=args.output_dir or "runs/latest",
        )
    manifest = Code2SkillPipeline(config).run(args.input, config.output_dir)
    print(json.dumps(manifest["summary"], indent=2))
    return 0
