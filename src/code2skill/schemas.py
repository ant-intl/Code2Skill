"""Typed records passed between Code2Skill stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceUnit:
    data_id: str
    repo_name: str
    repo_path: str
    relative_path: str
    language: str
    symbol: str
    unit_type: str
    line_start: int
    line_end: int
    interface: str
    code: str
    parser_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceUnitTag:
    keep_for_extraction: bool
    selection_rationale: str
    reusable_intent_score: float
    procedural_steps_score: float
    boundary_conditions_score: float
    transferability_score: float
    interface_sufficiency_score: float
    non_triviality_score: float
    selection_tags: List[str] = field(default_factory=list)
    risk_tags: List[str] = field(default_factory=list)

    @property
    def mean_score(self) -> float:
        values = [
            self.reusable_intent_score,
            self.procedural_steps_score,
            self.boundary_conditions_score,
            self.transferability_score,
            self.interface_sufficiency_score,
            self.non_triviality_score,
        ]
        return sum(values) / len(values)


@dataclass
class SkillRecord:
    level: str
    name: str
    summary: str
    worth_extracting: bool
    worth_reason: str
    skill_value_score: float
    generality_score: float
    abstraction_score: float
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    workflow: List[str] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    error_cases: List[str] = field(default_factory=list)
    implementation_notes: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    anti_goals: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Reconstruction:
    code: str
    output_valid: bool
    validation_notes: List[str] = field(default_factory=list)


@dataclass
class EquivalenceJudgment:
    equivalent: bool
    confidence: float
    reason: str
    differences: List[str] = field(default_factory=list)
    risk_level: str = "high"


@dataclass
class Adjudication:
    keep: bool
    skill_is_correct: bool
    generation_failed: bool
    reason: str
    corrective_notes: List[str] = field(default_factory=list)


@dataclass
class CanonicalFeatures:
    transfer_title: str
    transfer_summary: str
    when_to_use: str
    task_family: str
    capability_tags: List[str]
    constraint_tags: List[str]
    success_signal: str
    success_tags: List[str]
    failure_modes: List[str]
    interaction_pattern: str
    domain_hints: List[str]
    retrieval_phrases: List[str]
    custom_tags: List[str]
    notes: str
    canonical_fingerprint: str = ""


@dataclass
class UnitDecision:
    data_id: str
    repo_name: str
    relative_path: str
    symbol: str
    accepted: bool
    decision_stage: str
    accepted_stage: str
    rationale: str
    source_tag: Optional[SourceUnitTag] = None
    skill: Optional[SkillRecord] = None
    reconstruction: Optional[Reconstruction] = None
    equivalence: Optional[EquivalenceJudgment] = None
    adjudication: Optional[Adjudication] = None
    retrieval: Optional[CanonicalFeatures] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
