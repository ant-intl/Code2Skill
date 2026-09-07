"""End-to-end Code2Skill construction pipeline."""

from __future__ import annotations

import ast
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import normalize
from .client import OpenAICompatibleClient
from .config import AppConfig
from .prompts import (
    adjudication_messages,
    equivalence_messages,
    extraction_messages,
    feature_messages,
    regeneration_messages,
    source_tag_messages,
)
from .purpose import build_purpose_index
from .schemas import Reconstruction, SourceUnit, SourceUnitTag, UnitDecision
from .source import discover_repositories, scan_repository
from .storage import RunStore, write_json, write_jsonl


class Code2SkillPipeline:
    def __init__(self, config: AppConfig, client: Optional[Any] = None) -> None:
        config.validate()
        self.config = config
        self.client = client or OpenAICompatibleClient(config.model)

    def _json_call(
        self, store: RunStore, stage: str, unit: SourceUnit, messages: Any
    ) -> Dict[str, Any]:
        try:
            response = self.client.complete_json(stage, unit.data_id, messages)
            store.trace(unit.data_id, stage, messages, response)
            return response
        except Exception as exc:
            store.trace(unit.data_id, stage, messages, error=str(exc))
            raise

    def _text_call(
        self, store: RunStore, stage: str, unit: SourceUnit, messages: Any
    ) -> str:
        try:
            response = self.client.complete_text(stage, unit.data_id, messages)
            store.trace(unit.data_id, stage, messages, response)
            return response
        except Exception as exc:
            store.trace(unit.data_id, stage, messages, error=str(exc))
            raise

    def _tag(
        self, store: RunStore, unit: SourceUnit
    ) -> Tuple[SourceUnit, Optional[SourceUnitTag], str]:
        try:
            tag = normalize.source_tag(
                self._json_call(
                    store, "source_tagging", unit, source_tag_messages(unit)
                )
            )
            return unit, tag, ""
        except Exception as exc:
            return unit, None, str(exc)

    def _select(
        self, store: RunStore, units: Sequence[SourceUnit]
    ) -> Tuple[List[Tuple[SourceUnit, SourceUnitTag]], List[UnitDecision]]:
        tagged: List[Tuple[SourceUnit, SourceUnitTag]] = []
        rejected: List[UnitDecision] = []
        with ThreadPoolExecutor(max_workers=self.config.pipeline.concurrency) as pool:
            futures = [pool.submit(self._tag, store, unit) for unit in units]
            for future in as_completed(futures):
                unit, tag, error = future.result()
                if tag is None:
                    rejected.append(
                        self._decision(
                            unit, False, "source_tagging", "tagging_error", error=error
                        )
                    )
                elif (
                    not tag.keep_for_extraction
                    or tag.mean_score < self.config.pipeline.min_selection_score
                ):
                    rejected.append(
                        self._decision(
                            unit,
                            False,
                            "source_tagging",
                            "source_unit_selection_gate",
                            source_tag=tag,
                        )
                    )
                else:
                    tagged.append((unit, tag))
        by_repo: Dict[str, List[Tuple[SourceUnit, SourceUnitTag]]] = {}
        for item in tagged:
            by_repo.setdefault(item[0].repo_path, []).append(item)
        selected: List[Tuple[SourceUnit, SourceUnitTag]] = []
        for items in by_repo.values():
            ordered = sorted(
                items, key=lambda item: (-item[1].mean_score, item[0].data_id)
            )
            selected.extend(ordered[: self.config.scan.max_units_per_repo])
            for unit, tag in ordered[self.config.scan.max_units_per_repo :]:
                rejected.append(
                    self._decision(
                        unit,
                        False,
                        "source_tagging",
                        "per_repository_cap",
                        source_tag=tag,
                    )
                )
        return sorted(selected, key=lambda item: item[0].data_id), rejected

    def _process(
        self, store: RunStore, unit: SourceUnit, tag: SourceUnitTag
    ) -> UnitDecision:
        try:
            extracted = normalize.skill(
                self._json_call(
                    store, "extraction", unit, extraction_messages(unit, tag)
                )
            )
            if (
                not extracted.worth_extracting
                or extracted.skill_value_score
                < self.config.pipeline.min_skill_value_score
            ):
                return self._decision(
                    unit,
                    False,
                    "extraction",
                    "skill_value_gate",
                    source_tag=tag,
                    skill=extracted,
                )

            generated = normalize.strip_code_fence(
                self._text_call(
                    store, "regeneration", unit, regeneration_messages(unit, extracted)
                )
            )
            valid = bool(generated.strip())
            notes: List[str] = []
            if unit.language == "python" and valid:
                try:
                    ast.parse(generated)
                except SyntaxError as exc:
                    valid = False
                    notes.append(f"python_parse_error:{exc.msg}")
            reconstruction = Reconstruction(
                code=generated, output_valid=valid, validation_notes=notes
            )
            judgment = normalize.judgment(
                self._json_call(
                    store,
                    "equivalence",
                    unit,
                    equivalence_messages(unit, extracted, generated),
                )
            )
            if judgment.equivalent:
                decision = self._decision(
                    unit,
                    True,
                    "equivalence",
                    judgment.reason,
                    source_tag=tag,
                    skill=extracted,
                    reconstruction=reconstruction,
                    equivalence=judgment,
                )
            else:
                adjudicated = normalize.adjudication(
                    self._json_call(
                        store,
                        "adjudication",
                        unit,
                        adjudication_messages(
                            unit, extracted, generated, judgment.reason
                        ),
                    )
                )
                decision = self._decision(
                    unit,
                    adjudicated.keep,
                    "adjudication",
                    adjudicated.reason,
                    source_tag=tag,
                    skill=extracted,
                    reconstruction=reconstruction,
                    equivalence=judgment,
                    adjudication=adjudicated,
                )
            if decision.accepted:
                payload = self._feature_payload(decision)
                try:
                    decision.retrieval = normalize.features(
                        self._json_call(
                            store, "feature_tagging", unit, feature_messages(payload)
                        )
                    )
                except Exception as exc:
                    # Retrieval metadata is downstream of acceptance and must not
                    # retroactively reject a grounded skill record.
                    decision.error = f"feature_tagging_error:{exc}"
            return decision
        except Exception as exc:
            return self._decision(
                unit, False, "error", "pipeline_error", source_tag=tag, error=str(exc)
            )

    @staticmethod
    def _decision(
        unit: SourceUnit, accepted: bool, stage: str, rationale: str, **kwargs: Any
    ) -> UnitDecision:
        return UnitDecision(
            data_id=unit.data_id,
            repo_name=unit.repo_name,
            relative_path=unit.relative_path,
            symbol=unit.symbol,
            accepted=accepted,
            decision_stage=stage,
            accepted_stage=stage if accepted else "",
            rationale=rationale,
            **kwargs,
        )

    @staticmethod
    def _accepted_payload(decision: UnitDecision) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "data_id": decision.data_id,
            "repo_name": decision.repo_name,
            "relative_path": decision.relative_path,
            "symbol": decision.symbol,
            "accepted_stage": decision.accepted_stage,
            "rationale": decision.rationale,
            "skill": asdict(decision.skill) if decision.skill else {},
            "source_tag": asdict(decision.source_tag) if decision.source_tag else {},
            "equivalence": asdict(decision.equivalence) if decision.equivalence else {},
            "adjudication": asdict(decision.adjudication)
            if decision.adjudication
            else None,
        }
        # The failed generation is deliberately excluded from adjudicated-accept artifacts.
        if decision.accepted_stage == "equivalence" and decision.reconstruction:
            payload["reconstruction"] = asdict(decision.reconstruction)
        if decision.retrieval:
            payload["retrieval"] = asdict(decision.retrieval)
        return payload

    @staticmethod
    def _feature_payload(decision: UnitDecision) -> Dict[str, Any]:
        """Flatten the accepted skill to the paper's feature-tagger input schema."""
        payload: Dict[str, Any] = {
            "data_id": decision.data_id,
            "repo_name": decision.repo_name,
            "relative_path": decision.relative_path,
            "symbol": decision.symbol,
            "accepted_stage": decision.accepted_stage,
            "rationale": decision.rationale,
        }
        if decision.skill:
            payload.update(asdict(decision.skill))
            payload.pop("name", None)
            payload.pop("worth_reason", None)
        return payload

    def run(self, input_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        run_root = Path(output_dir or self.config.output_dir).expanduser().resolve()
        store = RunStore(run_root, self.config.pipeline.store_full_traces)
        repositories = discover_repositories(input_path)
        units: List[SourceUnit] = []
        skipped: List[Dict[str, str]] = []
        for repo in repositories:
            repo_units, repo_skipped = scan_repository(repo, self.config.scan)
            units.extend(repo_units)
            skipped.extend({"repo_name": repo.name, **item} for item in repo_skipped)
        selected, early_rejections = self._select(store, units)
        decisions = list(early_rejections)
        with ThreadPoolExecutor(max_workers=self.config.pipeline.concurrency) as pool:
            futures = [
                pool.submit(self._process, store, unit, tag) for unit, tag in selected
            ]
            decisions.extend(future.result() for future in as_completed(futures))
        decisions.sort(key=lambda item: item.data_id)
        accepted = [self._accepted_payload(item) for item in decisions if item.accepted]
        rejected = [item.to_dict() for item in decisions if not item.accepted]
        retrieval = [
            {
                "data_id": item.data_id,
                "repo_name": item.repo_name,
                "relative_path": item.relative_path,
                "symbol": item.symbol,
                **asdict(item.retrieval),
            }
            for item in decisions
            if item.accepted and item.retrieval
        ]
        cards: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        purpose_dropped: List[Dict[str, Any]] = []
        if self.config.pipeline.build_purpose_index:
            cards, edges, purpose_dropped = build_purpose_index(accepted)

        write_jsonl(run_root / "source_units.jsonl", [item.to_dict() for item in units])
        write_jsonl(
            run_root / "decisions.jsonl", [item.to_dict() for item in decisions]
        )
        write_jsonl(run_root / "accepted_records.jsonl", accepted)
        write_jsonl(run_root / "rejected_records.jsonl", rejected)
        write_jsonl(run_root / "retrieval_records.jsonl", retrieval)
        write_jsonl(run_root / "purpose_index.jsonl", cards)
        write_jsonl(run_root / "purpose_edges.jsonl", edges)
        write_jsonl(run_root / "purpose_dropped.jsonl", purpose_dropped)
        write_jsonl(run_root / "scan_skipped.jsonl", skipped)
        summary = {
            "repositories": len(repositories),
            "source_units": len(units),
            "selected_units": len(selected),
            "accepted_records": len(accepted),
            "rejected_records": len(rejected),
            "retrieval_records": len(retrieval),
            "purpose_cards": len(cards),
            "purpose_dropped": len(purpose_dropped),
            "scan_skipped": len(skipped),
        }
        write_json(run_root / "summary.json", summary)
        manifest = {
            "schema_version": "1.0",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "input_path": str(Path(input_path).expanduser().resolve()),
            "output_dir": str(run_root),
            "config": self.config.to_dict(),
            "summary": summary,
            "acceptance_rules": {
                "extraction": "worth_extracting=true and skill_value_score >= configured threshold",
                "direct_accept": "equivalent=true",
                "adjudicated_accept": "keep=true",
            },
        }
        write_json(run_root / "manifest.json", manifest)
        return manifest
