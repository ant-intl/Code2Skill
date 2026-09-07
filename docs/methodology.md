# Methodology and paper-to-code map

This implementation follows the construction method described in the paper,
while making operational choices explicit in configuration and run manifests.
It builds an evidence archive, a one-to-one retrieval view, and an optional
purpose-level index; these are separate artifacts.

| Paper stage | Implementation | Model-visible input | Decision |
| --- | --- | --- | --- |
| Source-unit tagging | `source.py`, `prompts.source_tag_messages` | Source, repository/file metadata, parser metadata, interface | Keep flag and configured mean-score gate, then per-repository cap |
| Unified extraction | `prompts.extraction_messages` | Tagged source unit and metadata | Continue iff `worth_extracting=true` and value score meets the configured threshold (paper default: 0.45) |
| Blind regeneration | `prompts.regeneration_messages` | Full skill, language, symbol, unit type, interface, optional chunk context | Output validity is metadata only |
| Equivalence judgment | `prompts.equivalence_messages` | Source and generated code, language, symbol, interface, chunk context, skill summary | Direct accept exactly when `equivalent=true` |
| Adjudication | `prompts.adjudication_messages` | First reason, source and generated code, full skill, language, symbol, interface, chunk context | Adjudicated accept exactly when `keep=true` |
| Retrieval feature tagging | `prompts.feature_messages`, `normalize.features` | Accepted skill payload and controlled vocabularies | One normalized retrieval record per accepted skill |
| Purpose indexing | `purpose.build_purpose_index` | Accepted records | Deterministic value filter, grouping, and existing-record representative selection |

## Information boundaries

The regeneration prompt deliberately contains no source body, repository name,
or file path. The equivalence judge does not receive unit type, full skill JSON,
tests, traces, type-checker output, or maintenance metadata. The adjudicator
receives the full skill but still does not receive unit type, tests, traces,
type-checker output, or maintenance metadata. Tests assert these boundaries
against sentinel values.

## What verification means

Regeneration is a challenge to the completeness of the extracted procedure. A
source-aware LLM then compares observable behavior, side effects, return
semantics, and error handling. This is an LLM consistency check, not formal
program equivalence and not a substitute for execution-based verification.

The adjudication branch separates two failure causes: an unsupported skill and
a faithful skill whose generated implementation was deficient. An adjudicated
accept retains the skill and provenance, but omits the failed generated code
from the accepted artifact.

## Purpose view

A purpose is the normalized triple `(task_family, intent_action,
intent_target)`: what broad task the record serves, what action it performs,
and what target that action operates on. The builder additionally infers
lifecycle, input/output shape, constraints, and failure signatures for audit.
It never synthesizes a new cluster-level skill. A fixed score over workflow,
invariants, error cases, evidence, summary length, and record level selects one
existing member as the representative.

## Reproducibility limits

The repository exposes prompts, normalization, thresholds, traces, and output
schemas. Exact reproduction still depends on the chosen model, endpoint,
serving parameters, repository snapshot, and parser coverage. Every run records
its effective configuration and terminal decisions in `manifest.json` and
`decisions.jsonl`.
