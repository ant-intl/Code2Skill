"""Deterministic purpose filtering, clustering, and representative selection."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Dict, List, Mapping, Sequence, Tuple

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "then",
    "this",
    "to",
    "use",
    "using",
    "with",
}
VERB_ALIASES = {
    "parses": "parse",
    "parsed": "parse",
    "extracts": "extract",
    "creates": "create",
    "constructs": "create",
    "builds": "build",
    "computes": "compute",
    "calculates": "compute",
    "gets": "get",
    "retrieves": "get",
    "returns": "get",
    "sets": "set",
    "updates": "update",
    "replaces": "update",
    "loads": "load",
    "saves": "save",
    "writes": "save",
    "reads": "load",
    "renders": "render",
    "handles": "handle",
    "processes": "process",
    "executes": "execute",
    "runs": "run",
    "merges": "merge",
    "converts": "convert",
    "transforms": "transform",
    "normalizes": "normalize",
    "initializes": "initialize",
    "configures": "configure",
    "verifies": "verify",
    "checks": "validate",
    "deletes": "delete",
    "removes": "remove",
    "retries": "retry",
    "recovers": "recover",
    "filters": "filter",
    "ranks": "rank",
}
INTENT_VERBS = {
    "aggregate",
    "authenticate",
    "authorize",
    "build",
    "cache",
    "check",
    "cleanup",
    "compute",
    "configure",
    "convert",
    "copy",
    "create",
    "decode",
    "delete",
    "detect",
    "dispatch",
    "encode",
    "execute",
    "extract",
    "fetch",
    "filter",
    "get",
    "handle",
    "initialize",
    "launch",
    "list",
    "load",
    "match",
    "merge",
    "navigate",
    "normalize",
    "open",
    "parse",
    "persist",
    "process",
    "query",
    "rank",
    "recover",
    "remove",
    "render",
    "retry",
    "route",
    "run",
    "save",
    "schedule",
    "serialize",
    "set",
    "split",
    "start",
    "stop",
    "sync",
    "test",
    "transform",
    "update",
    "validate",
    "verify",
}
GENERIC_TARGETS = {
    "method",
    "function",
    "object",
    "value",
    "values",
    "data",
    "item",
    "items",
    "input",
    "inputs",
    "output",
    "outputs",
    "result",
    "results",
    "return",
    "returns",
    "status",
    "self",
    "this",
}
FAMILY_HINTS = {
    "validation": {"validate", "verify", "check", "assert", "guard", "schema"},
    "parsing": {"parse", "deserialize", "decode", "json", "xml", "csv"},
    "io": {"load", "save", "read", "write", "fetch", "download", "upload"},
    "state_transition": {"update", "mutate", "transition", "state", "commit"},
    "orchestration": {"execute", "run", "schedule", "pipeline", "workflow"},
    "configuration": {"configure", "initialize", "setup", "args", "config"},
    "recovery": {"retry", "recover", "fallback", "backoff", "timeout"},
    "security": {"authorize", "authenticate", "permission", "token", "secret"},
    "aggregation": {"aggregate", "merge", "combine", "summarize", "reduce"},
    "transformation": {"convert", "transform", "normalize", "map", "format"},
    "dispatch": {"dispatch", "route", "handler", "event", "callback"},
    "lookup": {"lookup", "find", "search", "query", "match", "rank"},
}
LOW_VALUE = [
    re.compile(r"\bgetter\b|\bsetter\b", re.I),
    re.compile(r"\btrivial\b", re.I),
    re.compile(r"\bthin wrapper\b|\blogging[- ]only\b|\bconstant mapping\b", re.I),
]


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if value else []


def _tokens(value: str) -> List[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
    values = re.findall(r"[A-Za-z][A-Za-z0-9]*", expanded.lower())
    return [
        VERB_ALIASES.get(token, token)
        for token in values
        if len(token) > 1 and token not in STOPWORDS
    ]


def _skill(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("skill")
    return value if isinstance(value, Mapping) else record


def _blob(record: Mapping[str, Any], skill: Mapping[str, Any]) -> str:
    fields = [
        record.get("symbol"),
        skill.get("name"),
        skill.get("summary"),
        skill.get("when_to_use"),
    ]
    for name in (
        "workflow",
        "inputs",
        "outputs",
        "invariants",
        "error_cases",
        "anti_goals",
        "evidence",
    ):
        fields.extend(_as_list(skill.get(name)))
    return "\n".join(str(item) for item in fields if item)


def low_value_reason(record: Mapping[str, Any]) -> str:
    skill = _skill(record)
    blob = _blob(record, skill)
    for pattern in LOW_VALUE:
        if pattern.search(blob):
            return "boilerplate_or_trivial"
    workflow = _as_list(skill.get("workflow"))
    invariants = _as_list(skill.get("invariants"))
    errors = _as_list(skill.get("error_cases"))
    summary = str(skill.get("summary") or "")
    symbol = str(record.get("symbol") or "")
    if re.match(r"^(get|set|is|has)[A-Z_]", symbol) and len(workflow) <= 1:
        return "getter_setter_like"
    if len(summary) < 80 and len(workflow) <= 1 and not invariants and not errors:
        return "too_little_reusable_logic"
    if any(part in symbol for part in ("toString", "__str__", "__repr__")):
        return "representation_only"
    return ""


def infer_purpose(record: Mapping[str, Any]) -> Dict[str, Any]:
    skill = _skill(record)
    tokens = _tokens(_blob(record, skill))
    action_index = next(
        (index for index, token in enumerate(tokens) if token in INTENT_VERBS), -1
    )
    action = tokens[action_index] if action_index >= 0 else "execute"
    tail = tokens[action_index + 1 :] if action_index >= 0 else tokens
    target_parts = [
        token
        for token in tail
        if token not in INTENT_VERBS and token not in GENERIC_TARGETS
    ][:2]
    target = "_".join(target_parts) or "object"
    retrieval = (
        record.get("retrieval") if isinstance(record.get("retrieval"), Mapping) else {}
    )
    family = str(retrieval.get("task_family") or "")
    if not family:
        token_set = set(tokens)
        family, count = max(
            ((name, len(token_set & hints)) for name, hints in FAMILY_HINTS.items()),
            key=lambda item: (item[1], item[0]),
        )
        if not count:
            family = "workflow"
    inputs = _tokens(" ".join(_as_list(skill.get("inputs"))))[:2]
    outputs = _tokens(" ".join(_as_list(skill.get("outputs"))))[:2]
    lifecycle = (
        "prepare"
        if action in {"initialize", "configure", "load", "fetch", "parse"}
        else "verify"
        if action in {"validate", "verify", "test"}
        else "recover"
        if action in {"retry", "recover"}
        else "finalize"
        if action in {"save", "persist", "cleanup"}
        else "execute"
    )
    return {
        "task_family": family,
        "intent_action": action,
        "intent_target": target,
        "lifecycle_stage": lifecycle,
        "io_shape": f"{'_'.join(inputs) or 'unspecified'}->{'_'.join(outputs) or 'unspecified'}",
        "constraint_signature": _tokens(
            " ".join(
                _as_list(skill.get("invariants")) + _as_list(skill.get("anti_goals"))
            )
        )[:6],
        "failure_signature": _tokens(" ".join(_as_list(skill.get("error_cases"))))[:6],
    }


def representative_score(record: Mapping[str, Any]) -> float:
    skill = _skill(record)
    score = min(1.0, len(_as_list(skill.get("workflow"))) / 6.0) * 0.30
    score += min(1.0, len(_as_list(skill.get("invariants"))) / 5.0) * 0.20
    score += min(1.0, len(_as_list(skill.get("error_cases"))) / 5.0) * 0.20
    score += min(1.0, len(_as_list(skill.get("evidence"))) / 4.0) * 0.10
    score += min(1.0, len(str(skill.get("summary") or "")) / 600.0) * 0.10
    level = str(skill.get("level") or record.get("level") or "")
    return score + (
        0.10 if level == "pattern" else 0.06 if level == "composite" else 0.0
    )


def _stable_id(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def build_purpose_index(
    records: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    groups: Dict[str, List[Tuple[Mapping[str, Any], Dict[str, Any]]]] = {}
    edges: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for record in records:
        reason = low_value_reason(record)
        if reason:
            dropped.append({"data_id": record.get("data_id", ""), "reason": reason})
            continue
        purpose = infer_purpose(record)
        key = {
            name: purpose[name]
            for name in ("task_family", "intent_action", "intent_target")
        }
        purpose_id = _stable_id(key)
        groups.setdefault(purpose_id, []).append((record, purpose))
        edges.append(
            {
                "data_id": record.get("data_id", ""),
                "purpose_id": purpose_id,
                "purpose_key": key,
                "inferred_purpose": purpose,
            }
        )
    cards: List[Dict[str, Any]] = []
    for purpose_id, members in sorted(groups.items()):
        representative, purpose = max(
            members,
            key=lambda item: (
                representative_score(item[0]),
                str(item[0].get("data_id", "")),
            ),
        )
        skill = _skill(representative)
        repos = {str(item[0].get("repo_name", "")) for item in members}
        levels = Counter(
            str(_skill(item[0]).get("level") or "unknown") for item in members
        )
        cards.append(
            {
                "purpose_id": purpose_id,
                "purpose_key": {
                    name: purpose[name]
                    for name in ("task_family", "intent_action", "intent_target")
                },
                "support_count": len(members),
                "repo_support": len(repos),
                "level_counts": dict(sorted(levels.items())),
                "representative_data_id": representative.get("data_id", ""),
                "representative_score": round(representative_score(representative), 6),
                "transfer_title": skill.get("name")
                or skill.get("transfer_title")
                or "",
                "transfer_summary": skill.get("summary")
                or skill.get("transfer_summary")
                or "",
                "workflow": _as_list(skill.get("workflow")),
                "inputs": _as_list(skill.get("inputs")),
                "outputs": _as_list(skill.get("outputs")),
                "invariants": _as_list(skill.get("invariants")),
                "error_cases": _as_list(skill.get("error_cases")),
            }
        )
    return cards, edges, dropped
