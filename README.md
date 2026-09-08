# Code2Skill

Code2Skill turns source-code units into grounded, reusable procedural skill
records. It extracts a structured skill, challenges that abstraction through
source-body-blind code regeneration, checks the regenerated behavior against
the source, and retains accepted records with provenance and retrieval-facing
metadata.

This repository is a local, publication-oriented implementation aligned with
the paper **Grounded Skill Synthesis from Code at Scale for Agentic
Intelligence**. The repository is currently pre-release and privately hosted;
it is not yet a public open-source release.

## Pipeline

1. **Source-unit tagging** scores parsed functions, methods, command entry
   points, and file-level components for reusable procedural evidence.
2. **Skill extraction** emits one typed record: `atomic`, `composite`, or
   `pattern`.
3. **Source-body-blind regeneration** receives the skill and interface, but not
   the source body, repository name, or file path.
4. **Source-aware equivalence judgment** compares source and regenerated code.
5. **Adjudication** separates an unsupported skill from a failed regeneration.
6. **Feature tagging** creates one retrieval record per accepted skill using
   closed vocabularies.
7. **Purpose indexing** deterministically removes low-value records, groups
   records by `(task_family, intent_action, intent_target)`, and selects an
   existing representative for each group.

The judge is an LLM consistency check, not a proof of program equivalence.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The runtime has no third-party Python dependency. It calls an
OpenAI-compatible `/chat/completions` endpoint through the standard library.
It has no telemetry and does not upload repository content anywhere except the
model endpoint explicitly configured for a run.

## Run against a model endpoint

```bash
cp .env.example .env
# Fill the two values in .env, then load them into the current shell.
set -a
. ./.env
set +a

code2skill run /path/to/repository \
  --base-url "$CODE2SKILL_MODEL_BASE_URL" \
  --model your-model-name \
  --output-dir runs
```

Public model hosts are rejected by default. Add `--allow-public-model-url`
only when the endpoint is intentionally trusted.

To inspect the model-visible messages without making a model call:

```bash
code2skill show-prompts --stage regeneration
```

To build a new purpose index from accepted-record JSONL:

```bash
code2skill purpose-index accepted_records.jsonl purpose_index.jsonl
```

## Offline end-to-end example

The deterministic example client exercises every stage without network access:

```bash
PYTHONPATH=src python examples/offline_demo.py
```

It writes a complete run under `examples/output/`, including decisions,
accepted records, retrieval records, prompt/response traces, and a purpose
index.

## Output contract

Each run directory contains:

```text
manifest.json
summary.json
source_units.jsonl
decisions.jsonl
accepted_records.jsonl
rejected_records.jsonl
retrieval_records.jsonl
purpose_index.jsonl
purpose_edges.jsonl
traces/<data_id>/<stage>.json
```

`accepted_stage` is `equivalence` for direct accepts and `adjudication` for
adjudicated accepts. In the latter case, the skill is retained but the failed
regenerated code is not an accepted artifact.

See [docs/methodology.md](docs/methodology.md) for the paper-to-code mapping,
[docs/data-contract.md](docs/data-contract.md) for schemas, and
[docs/open-source-checklist.md](docs/open-source-checklist.md) for publication
gates.

## Resources

- [Project website](https://ant-international-research.github.io/developer-skill-hubs/)
- [DeveloperSkills-Code2Skill dataset](https://huggingface.co/datasets/ant-intl/DeveloperSkills-Code2Skill)

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests examples
```

## Release status

This is a pre-release codebase. An organization-approved open-source license,
public repository URL, archival DOI, and final paper identifier must be added
before publication. No license is implied by the current local repository.
