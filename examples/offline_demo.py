"""Run a deterministic end-to-end example without network access."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from code2skill.client import ScriptedClient
from code2skill.config import AppConfig, ModelConfig
from code2skill.pipeline import Code2SkillPipeline

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"

SOURCE_TAG = {
    "keep_for_extraction": True,
    "selection_rationale": "Bounded retry and explicit failures are reusable.",
    "reusable_intent_score": 0.95,
    "procedural_steps_score": 0.92,
    "boundary_conditions_score": 0.9,
    "transferability_score": 0.93,
    "interface_sufficiency_score": 0.9,
    "non_triviality_score": 0.86,
    "selection_tags": ["bounded_retry", "error_handling"],
    "risk_tags": [],
}
SKILL = {
    "level": "composite",
    "name": "Bounded retry with explicit exhaustion",
    "summary": "Validate a positive retry budget, return the first successful operation result, and raise a terminal error when all attempts fail.",
    "worth_extracting": True,
    "worth_reason": "Reusable recovery workflow with clear boundaries.",
    "skill_value_score": 0.92,
    "generality_score": 0.94,
    "abstraction_score": 0.86,
    "inputs": ["Callable operation", "Positive attempt count"],
    "outputs": ["First successful result"],
    "workflow": [
        "Validate retry count",
        "Attempt the operation",
        "Continue after transient failure",
        "Raise after exhaustion",
    ],
    "invariants": ["Never exceed the attempt count"],
    "error_cases": ["Non-positive count", "All attempts fail"],
    "implementation_notes": ["Catch only the intended transient exception"],
    "evidence": ["Positive-count guard", "Bounded loop", "Terminal exception"],
    "anti_goals": ["Do not retry forever", "Do not hide unrelated exceptions"],
    "confidence": 0.95,
}
GENERATED = """def fetch_with_retry(fetch, attempts):
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for _ in range(attempts):
        try:
            return fetch()
        except OSError:
            continue
    raise RuntimeError("retry budget exhausted")
"""
FEATURES = {
    "transfer_title": "Bounded retry with explicit terminal failure",
    "transfer_summary": "Retry a transiently failing operation within a fixed budget and surface exhaustion.",
    "when_to_use": "Use when an operation may fail transiently but retries must remain bounded.",
    "task_family": "recovery",
    "capability_tags": ["precondition_check", "retry_backoff", "error_propagation"],
    "constraint_tags": ["return_error_on_failure"],
    "success_signal": "The first successful value is returned.",
    "success_tags": ["output_returned", "no_error"],
    "failure_modes": ["Invalid retry budget", "Retry exhaustion"],
    "interaction_pattern": "multi_step_workflow",
    "domain_hints": [],
    "retrieval_phrases": [
        "bounded retry",
        "retry exhaustion",
        "transient failure",
        "retry budget",
    ],
    "custom_tags": [],
    "notes": "The transient exception type must be chosen explicitly.",
}


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    client = ScriptedClient(
        {
            "source_tagging": SOURCE_TAG,
            "extraction": SKILL,
            "regeneration": GENERATED,
            "equivalence": {
                "equivalent": True,
                "confidence": 0.98,
                "reason": "Observable behavior matches.",
                "differences": [],
                "risk_level": "low",
            },
            "feature_tagging": FEATURES,
        }
    )
    config = AppConfig(
        model=ModelConfig(base_url="offline", model="offline"),
        output_dir=str(OUTPUT),
    )
    config.pipeline.concurrency = 1
    manifest = Code2SkillPipeline(config, client=client).run(
        str(ROOT / "mini_repo"), str(OUTPUT)
    )
    print(json.dumps(manifest["summary"], indent=2))


if __name__ == "__main__":
    main()
