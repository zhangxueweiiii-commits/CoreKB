# CoreKB Testing

This document defines the canonical backend verification command for Codex tasks.

## Backend Test Layout

Backend tests currently live in two standard pytest-discovered locations:

- `backend/app/tests/`: main backend unit and API tests.
- `backend/tests/evaluation/`: evaluation fixtures and retrieval evaluation tests.

The metadata validation tests live at:

- `backend/app/tests/test_metadata_validation.py`

Integration tests live under `backend/tests/integration/` and are intentionally gated by environment variables in their own tests. They are not part of the default local backend verification command unless explicitly requested.

## Canonical Backend Test Command

Run from `backend/`:

```bash
python -m pytest -q
```

This uses `backend/pyproject.toml` pytest discovery:

```toml
testpaths = ["app/tests", "tests/evaluation"]
```

The command includes existing backend tests, metadata validation tests, and evaluation tests that are part of the normal backend verification workflow.

## Targeted Metadata Validation Test

Run from `backend/`:

```bash
python -m pytest app/tests/test_metadata_validation.py -q
```

## Notes

- Do not narrow pytest discovery to hide failing tests.
- Do not skip or weaken tests to make a task pass.
- If `make` is unavailable on the host, run the Python commands above directly and report that clearly.
