# Contributing

Code2Skill is currently being prepared for public release. Keep changes small,
testable, and traceable to a documented pipeline contract.

1. Create a local branch.
2. Add or update tests for behavioral changes.
3. Run `PYTHONPATH=src python -m unittest discover -s tests -v`.
4. Run `python -m compileall -q src tests examples`.
5. Confirm that prompts preserve the information boundaries in
   `docs/methodology.md`.
6. Do not commit model credentials, source corpora, generated run directories,
   or third-party repository contents.

Changes to acceptance semantics, prompt-visible inputs, controlled
vocabularies, or purpose clustering require a matching documentation update.
