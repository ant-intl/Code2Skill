# Data contract

All line-delimited files contain one UTF-8 JSON object per line. Run artifacts
are append-free snapshots: re-running into the same directory replaces the
named JSON/JSONL files but does not automatically remove older trace folders.

## Source unit

`data_id`, repository provenance, relative path, language, symbol, unit type,
line range, interface, source body, and parser metadata. `data_id` is a stable
hash of provenance, location, symbol, and source body.

## Extracted skill

One `level` (`atomic`, `composite`, or `pattern`), descriptive fields, three
quality scores, confidence, and bounded lists for inputs, outputs, workflow,
invariants, errors, notes, evidence, and anti-goals. Model output is normalized:
scores are clamped to `[0,1]`, summaries and list items are bounded, and unknown
levels fall back to `atomic`.

## Terminal decision

Every parsed candidate ends with an auditable decision. Accepted records use
`accepted_stage=equivalence` or `accepted_stage=adjudication`. Every result has
a `decision_stage`; rejections keep that stage and rationale in
`decisions.jsonl` while `accepted_stage` remains empty. Request or parse
failures fail closed and are recorded as errors.

## Accepted record

An accepted record contains provenance, source-unit tag, skill, equivalence
result, optional adjudication, and retrieval features. A direct accept also
contains its reconstruction. An adjudicated accept deliberately excludes the
failed reconstruction from this file; its full attempt remains auditable in
`decisions.jsonl` and traces.

## Retrieval record

The retrieval view contains a normalized task family, capability/constraint/
success tags, interaction pattern, user-facing descriptions, retrieval anchors,
and a SHA-256 canonical fingerprint. Closed-vocabulary values are enforced.
Invalid task families fall back to `workflow`, invalid interaction patterns to
`single_step`, and unknown controlled tags are dropped. Feature tagging is
one-to-one and never deduplicates accepted records. A feature-tagging failure
is recorded on the accepted decision and does not retroactively reject the
grounded skill; consequently a partial run can contain fewer retrieval records
than accepted records.

## Purpose card and edge

Each purpose card is one existing representative plus support statistics. Each
edge maps one accepted `data_id` to its purpose card and includes the inferred
purpose fields. `purpose_dropped.jsonl` records deterministic value-filter
exclusions and reasons.
