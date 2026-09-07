"""Strict normalization of untrusted model outputs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, List, Mapping, Sequence

from .prompts import (
    CAPABILITY_TAGS,
    CONSTRAINT_TAGS,
    INTERACTION_PATTERNS,
    SUCCESS_TAGS,
    TASK_FAMILIES,
)
from .schemas import (
    Adjudication,
    CanonicalFeatures,
    EquivalenceJudgment,
    SkillRecord,
    SourceUnitTag,
)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0", "", "null", "none"}:
            return False
    return False


def score(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def text(value: Any, max_words: int = 80) -> str:
    result = " ".join(str(value or "").split())
    words = result.split()
    return " ".join(words[:max_words])


def string_list(value: Any, maximum: int, item_words: int = 25) -> List[str]:
    if isinstance(value, str):
        values: Iterable[Any] = [value]
    elif isinstance(value, Sequence):
        values = value
    else:
        values = []
    result: List[str] = []
    for item in values:
        normalized = text(item, item_words)
        if normalized and normalized not in result:
            result.append(normalized)
        if len(result) >= maximum:
            break
    return result


def source_tag(payload: Mapping[str, Any]) -> SourceUnitTag:
    return SourceUnitTag(
        keep_for_extraction=as_bool(payload.get("keep_for_extraction")),
        selection_rationale=text(payload.get("selection_rationale"), 60),
        reusable_intent_score=score(payload.get("reusable_intent_score")),
        procedural_steps_score=score(payload.get("procedural_steps_score")),
        boundary_conditions_score=score(payload.get("boundary_conditions_score")),
        transferability_score=score(payload.get("transferability_score")),
        interface_sufficiency_score=score(payload.get("interface_sufficiency_score")),
        non_triviality_score=score(payload.get("non_triviality_score")),
        selection_tags=string_list(payload.get("selection_tags"), 8),
        risk_tags=string_list(payload.get("risk_tags"), 8),
    )


def skill(payload: Mapping[str, Any]) -> SkillRecord:
    level = text(payload.get("level"), 1).lower()
    if level not in {"atomic", "composite", "pattern"}:
        level = "atomic"
    return SkillRecord(
        level=level,
        name=text(payload.get("name"), 12),
        summary=text(payload.get("summary"), 80),
        worth_extracting=as_bool(payload.get("worth_extracting")),
        worth_reason=text(payload.get("worth_reason"), 60),
        skill_value_score=score(payload.get("skill_value_score")),
        generality_score=score(payload.get("generality_score")),
        abstraction_score=score(payload.get("abstraction_score")),
        inputs=string_list(payload.get("inputs"), 6),
        outputs=string_list(payload.get("outputs"), 6),
        workflow=string_list(payload.get("workflow"), 6),
        invariants=string_list(payload.get("invariants"), 6),
        error_cases=string_list(payload.get("error_cases"), 6),
        implementation_notes=string_list(payload.get("implementation_notes"), 6),
        evidence=string_list(payload.get("evidence"), 6),
        anti_goals=string_list(payload.get("anti_goals"), 6),
        confidence=score(payload.get("confidence")),
    )


def judgment(payload: Mapping[str, Any]) -> EquivalenceJudgment:
    risk = text(payload.get("risk_level"), 1).lower()
    if risk not in {"low", "medium", "high"}:
        risk = "high"
    return EquivalenceJudgment(
        equivalent=as_bool(payload.get("equivalent")),
        confidence=score(payload.get("confidence")),
        reason=text(payload.get("reason"), 80),
        differences=string_list(payload.get("differences"), 8),
        risk_level=risk,
    )


def adjudication(payload: Mapping[str, Any]) -> Adjudication:
    return Adjudication(
        keep=as_bool(payload.get("keep")),
        skill_is_correct=as_bool(payload.get("skill_is_correct")),
        generation_failed=as_bool(payload.get("generation_failed")),
        reason=text(payload.get("reason"), 80),
        corrective_notes=string_list(payload.get("corrective_notes"), 8),
    )


def _closed(value: Any, allowed: Sequence[str], fallback: str) -> str:
    normalized = text(value, 3).lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in allowed else fallback


def _closed_list(value: Any, allowed: Sequence[str], maximum: int) -> List[str]:
    candidates = string_list(value, maximum * 2, 5)
    result: List[str] = []
    for item in candidates:
        normalized = item.lower().replace("-", "_").replace(" ", "_")
        if normalized in allowed and normalized not in result:
            result.append(normalized)
        if len(result) >= maximum:
            break
    return result


def features(payload: Mapping[str, Any]) -> CanonicalFeatures:
    result = CanonicalFeatures(
        transfer_title=text(payload.get("transfer_title"), 12),
        transfer_summary=text(payload.get("transfer_summary"), 60),
        when_to_use=text(payload.get("when_to_use"), 80),
        task_family=_closed(payload.get("task_family"), TASK_FAMILIES, "workflow"),
        capability_tags=_closed_list(
            payload.get("capability_tags"), CAPABILITY_TAGS, 8
        ),
        constraint_tags=_closed_list(
            payload.get("constraint_tags"), CONSTRAINT_TAGS, 5
        ),
        success_signal=text(payload.get("success_signal"), 30),
        success_tags=_closed_list(payload.get("success_tags"), SUCCESS_TAGS, 4),
        failure_modes=string_list(payload.get("failure_modes"), 6),
        interaction_pattern=_closed(
            payload.get("interaction_pattern"), INTERACTION_PATTERNS, "single_step"
        ),
        domain_hints=string_list(payload.get("domain_hints"), 4, 5),
        retrieval_phrases=string_list(payload.get("retrieval_phrases"), 8, 10),
        custom_tags=string_list(payload.get("custom_tags"), 4, 5),
        notes=text(payload.get("notes"), 40),
    )
    canonical = json.dumps(
        result.__dict__, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    result.canonical_fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result


def strip_code_fence(value: str) -> str:
    cleaned = value.strip()
    match = re.fullmatch(
        r"```(?:[A-Za-z0-9_+.-]+)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL
    )
    return match.group(1).strip() if match else cleaned
