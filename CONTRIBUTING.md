# Contributing

1. Create a `feature/` or `fix/` branch; do not push changes directly to main.
2. Keep ingestion definitions in `workspace/`, source tools in `scripts/`,
   schema changes in versioned migrations, and explanations in `docs/`.
3. Add descriptions to Fabric items and activities. Document function inputs,
   outputs and non-obvious processing decisions, rather than narrating syntax.
4. Run credential-free validation and tests before opening a pull request.
5. Include the problem, changed behaviour, verification evidence and rollback
   considerations. State whether a test used fixtures or physical source Copy.
6. Do not run rebuilds, source mutations, promotions or schedules as part of
   documentation work. Cloud operations need their own scoped approval.

```bash
python -m pip install -r requirements.txt
python deploy/check_repository.py
python scripts/check_publication.py
pytest -q
```

No source datasets or commercial adoption claims belong in a pull request.
Do not claim exactly-once processing merely because a replay fixture passes.
Keep diagrams, metric definitions and implementation status aligned with code.
