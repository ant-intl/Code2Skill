"""Paper-aligned prompts and the retrieval controlled vocabularies."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Mapping

from .schemas import SkillRecord, SourceUnit, SourceUnitTag

Message = Dict[str, str]

TASK_FAMILIES = [
    "aggregation",
    "configuration",
    "dispatch",
    "initialization",
    "io",
    "lookup",
    "orchestration",
    "parsing",
    "recovery",
    "security",
    "state_transition",
    "transformation",
    "troubleshooting",
    "validation",
    "verification",
    "workflow",
]
CAPABILITY_TAGS = [
    "aggregate_results",
    "apply_defaults",
    "branch_on_condition",
    "check_identity",
    "cleanup_resource",
    "collect_inputs",
    "compare_state",
    "config_resolution",
    "constraint_enforcement",
    "deduplicate_items",
    "dispatch_by_type",
    "error_propagation",
    "exception_wrap",
    "fail_fast",
    "fallback_on_empty",
    "filter_items",
    "ground_on_tool_results",
    "initialize_resource",
    "iterate_items",
    "load_from_source",
    "lookup_by_id",
    "normalize_input",
    "parse_input",
    "permission_check",
    "post_action_refresh",
    "precondition_check",
    "rank_or_select",
    "retry_backoff",
    "return_structured_output",
    "state_toggle",
    "status_check",
    "status_refresh",
    "success_verification",
    "tool_invocation",
    "validate_input",
    "validate_output",
]
CONSTRAINT_TAGS = [
    "bounded_refuel",
    "do_not_guess_missing_state",
    "fail_closed",
    "must_recheck_after_mutation",
    "no_destructive_action",
    "no_plan_change",
    "one_tool_call_at_a_time",
    "preserve_output_format",
    "requires_identity_verification",
    "requires_user_confirmation",
    "return_error_on_failure",
    "single_action_then_verify",
    "tool_grounded_only",
]
SUCCESS_TAGS = [
    "goal_satisfied",
    "no_error",
    "output_returned",
    "policy_satisfied",
    "resource_initialized",
    "state_updated",
    "status_verified",
]
INTERACTION_PATTERNS = [
    "branching_dispatch",
    "multi_step_workflow",
    "observe_act_observe",
    "single_step",
]


def _messages(system: str, user: str) -> List[Message]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _chunk_context(unit: SourceUnit) -> str:
    count = unit.parser_metadata.get("chunk_count")
    index = unit.parser_metadata.get("chunk_index")
    parent = unit.parser_metadata.get("parent_symbol")
    if not count:
        return ""
    return (
        f"Chunk context: chunk {index} of {count} from parent symbol {parent}. "
        "Claim only behavior visible in this chunk.\n"
    )


def source_tag_messages(unit: SourceUnit) -> List[Message]:
    system = (
        "You are tagging source-code units for reusable procedural evidence. Keep only units "
        "that encode behavior a downstream coding or agent system could reuse. Penalize trivial "
        "wrappers, getters, setters, constant/config declarations, layout glue, and project-local "
        "conventions that lack transferable procedure. Do not infer behavior not supported by "
        "the code. Return strict JSON only."
    )
    user = f"""Score this source unit for skill extraction.

Use the rubric below. Scores are numbers in [0,1].
- reusable_intent: meaningful operation beyond local glue
- procedural_steps: ordered steps, branching, state/resource updates, or calls
- boundary_conditions: preconditions, invariants, validations, or error paths
- transferability: behavior describable without project-specific names or hidden context
- interface_sufficiency: inputs, outputs, side effects, and required context recoverable
- non_triviality: more than a getter, setter, thin wrapper, or boilerplate adapter

Return JSON with exactly these keys:
{{
  "keep_for_extraction": true,
  "selection_rationale": "<SHORT_REASON>",
  "reusable_intent_score": 0.0,
  "procedural_steps_score": 0.0,
  "boundary_conditions_score": 0.0,
  "transferability_score": 0.0,
  "interface_sufficiency_score": 0.0,
  "non_triviality_score": 0.0,
  "selection_tags": ["<EVIDENCE_TAG>"],
  "risk_tags": ["<TRIVIAL_OR_LOCAL_RISK>"]
}}

Repository: {unit.repo_name}
File: {unit.relative_path}
Language: {unit.language}
Symbol: {unit.symbol}
Unit type: {unit.unit_type}
Lines: {unit.line_start}-{unit.line_end}
Interface: {unit.interface}
Parser metadata: {_json(unit.parser_metadata)}

Code:
{unit.code}"""
    return _messages(system, user)


def extraction_messages(unit: SourceUnit, tag: SourceUnitTag) -> List[Message]:
    system = (
        "You are extracting a reusable skill specification from source code. Describe only "
        "behavior that is directly supported by the code. Do not invent product context or "
        "hidden requirements. Treat trivial wrappers, tiny getters/setters, and obvious "
        "boilerplate as not worth extracting. Atomic skills must still encode a meaningful "
        "reusable operation, not a single obvious statement. Return strict, compact JSON only."
    )
    user = f"""Extract a faithful skill specification from this code unit.

Return JSON with exactly these keys:
{{
  "level": "<atomic|composite|pattern>",
  "name": "<SHORT_SKILL_NAME>",
  "summary": "<BEHAVIORAL_SUMMARY>",
  "worth_extracting": true,
  "worth_reason": "<SHORT_EXPLANATION>",
  "skill_value_score": 0.0,
  "generality_score": 0.0,
  "abstraction_score": 0.0,
  "inputs": ["<INPUT_EXPECTATION>"],
  "outputs": ["<OUTPUT_OR_SIDE_EFFECT>"],
  "workflow": ["<ORDERED_STEP>"],
  "invariants": ["<INVARIANT>"],
  "error_cases": ["<FAILURE_OR_EDGE_CASE>"],
  "implementation_notes": ["<CONSTRAINT>"],
  "evidence": ["<SUPPORTED_BEHAVIOR>"],
  "anti_goals": ["<EXCLUDED_BEHAVIOR>"],
  "confidence": 0.0
}}

Score and confidence fields are numbers in [0,1]. Keep summary under 80 words.
Keep each array to at most 6 items and each item under 25 words. Do not reproduce source code in JSON.

Repository: {unit.repo_name}
File: {unit.relative_path}
Language: {unit.language}
Symbol: {unit.symbol}
Unit type: {unit.unit_type}
Lines: {unit.line_start}-{unit.line_end}
Interface: {unit.interface}
{_chunk_context(unit)}Source-unit tag:
{_json(asdict(tag))}

Code:
{unit.code}"""
    return _messages(system, user)


def regeneration_messages(unit: SourceUnit, skill: SkillRecord) -> List[Message]:
    system = (
        "You generate code only from a provided skill specification and interface contract. "
        "Preserve the observable behavior described in the skill. Do not add new features. "
        "Return code only."
    )
    user = f"""Generate the corresponding code unit from this skill specification.

Constraints:
- Output code only. No explanation.
- Use language: {unit.language}
- Preserve the target interface as closely as possible.
- Keep the same observable behavior and edge-case handling.
- Do not rely on unavailable project-global state unless the skill explicitly requires it.

Target symbol: {unit.symbol}
Target unit type: {unit.unit_type}
Target interface: {unit.interface}
{_chunk_context(unit)}
Skill specification:
{_json(asdict(skill))}"""
    return _messages(system, user)


def equivalence_messages(
    unit: SourceUnit, skill: SkillRecord, generated_code: str
) -> List[Message]:
    system = (
        "You are a strict functional equivalence judge for source code regeneration. Focus on "
        "behavior, side effects, return semantics, and error handling. Ignore style and naming "
        "differences. Return strict JSON."
    )
    user = f"""Compare the original code unit and the regenerated code unit.

Return JSON with exactly these keys:
{{
  "equivalent": true,
  "confidence": 0.0,
  "reason": "<CONCISE_EXPLANATION>",
  "differences": ["<BEHAVIORALLY_IMPORTANT_DIFFERENCE>"],
  "risk_level": "<low|medium|high>"
}}

Confidence is a number in [0,1].
Language: {unit.language}
Symbol: {unit.symbol}
Interface: {unit.interface}
{_chunk_context(unit)}Skill summary: {skill.summary}

Original code:
{unit.code}

Generated code:
{generated_code}"""
    return _messages(system, user)


def adjudication_messages(
    unit: SourceUnit,
    skill: SkillRecord,
    generated_code: str,
    equivalence_reason: str,
) -> List[Message]:
    system = (
        "You are resolving a disagreement between extracted skill quality and regenerated code "
        "quality. Decide whether the skill itself is faithful to the source even if the regenerated "
        "code is not. Return strict JSON."
    )
    user = f"""The first equivalence pass judged these code units inconsistent:
{equivalence_reason}

Decide whether the extracted skill itself is still correct and should be kept.

Return JSON with exactly these keys:
{{
  "keep": true,
  "skill_is_correct": true,
  "generation_failed": false,
  "reason": "<CONCISE_EXPLANATION>",
  "corrective_notes": ["<SHORT_NOTE>"]
}}

Language: {unit.language}
Symbol: {unit.symbol}
Interface: {unit.interface}
{_chunk_context(unit)}
Source code:
{unit.code}

Extracted skill:
{_json(asdict(skill))}

Generated code:
{generated_code}"""
    return _messages(system, user)


def feature_messages(payload: Mapping[str, Any]) -> List[Message]:
    system = (
        "You are canonicalizing extracted software skills into a retrieval-friendly representation. "
        "Your job is to rewrite each skill into a transferable, benchmark-facing skill card. "
        "Prefer generic reusable language over repo-specific names. Choose task families and tags "
        "from the provided controlled vocabularies when possible. Only output valid JSON."
    )
    user = f"""Canonicalize the following skill into a retrieval-ready representation.

Allowed task families: {_json(TASK_FAMILIES)}
Allowed capability tags: {_json(CAPABILITY_TAGS)}
Allowed constraint tags: {_json(CONSTRAINT_TAGS)}
Allowed success tags: {_json(SUCCESS_TAGS)}
Allowed interaction patterns: {_json(INTERACTION_PATTERNS)}

Return JSON with exactly these keys:
{{
  "transfer_title": "<6-12_WORD_TITLE>",
  "transfer_summary": "<1-2_SENTENCES>",
  "when_to_use": "<TRIGGER_PARAGRAPH>",
  "task_family": "<ALLOWED_TASK_FAMILY>",
  "capability_tags": ["<3-8_ALLOWED_TAGS>"],
  "constraint_tags": ["<0-5_ALLOWED_TAGS>"],
  "success_signal": "<ONE_SENTENCE>",
  "success_tags": ["<1-4_ALLOWED_TAGS>"],
  "failure_modes": ["<2-6_FAILURES>"],
  "interaction_pattern": "<ALLOWED_PATTERN>",
  "domain_hints": ["<0-4_SHORT_HINTS>"],
  "retrieval_phrases": ["<4-8_ANCHORS>"],
  "custom_tags": ["<0-4_EXTRA_TAGS>"],
  "notes": "<OPTIONAL_TRANSFER_LIMIT>"
}}

Focus on transferable behavior, not original function names. Capture mutate-then-check,
exact status verification, and hard boundaries explicitly. Retrieval phrases are lexical anchors.

Skill payload:
{_json(dict(payload))}"""
    return _messages(system, user)


def demo_unit() -> SourceUnit:
    return SourceUnit(
        data_id="demo",
        repo_name="example",
        repo_path="/redacted",
        relative_path="retry.py",
        language="python",
        symbol="fetch_with_retry",
        unit_type="function",
        line_start=1,
        line_end=8,
        interface="fetch_with_retry(fetch, attempts)",
        code="def fetch_with_retry(fetch, attempts):\n    for _ in range(attempts):\n        try:\n            return fetch()\n        except OSError:\n            pass\n    raise RuntimeError('exhausted')",
    )
