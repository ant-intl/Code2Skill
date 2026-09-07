# Security

## Model endpoints

Code2Skill rejects credentials embedded in URLs and rejects public model hosts
by default. Use `--allow-public-model-url` only after confirming that sending
source code to that endpoint is permitted.

## Source scanning

The scanner skips common dependency/build directories, binary files, oversized
files, and files containing recognizable private-key or access-token patterns.
These checks are defense in depth, not a complete secret detector. Review the
input repository before processing confidential code.

## Outputs

Run directories can contain source units, model prompts, model responses, and
provenance. They are ignored by Git by default and should be treated as
sensitive until reviewed.

## Reporting

Before public release, replace this section with an organization-approved
security contact and disclosure process.
