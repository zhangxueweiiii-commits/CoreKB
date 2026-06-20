# Evaluation Workflow Hardening Audit

This document audits the current CoreKB evaluation workflow and identifies hardening work that should be completed before evaluation outputs become more deeply connected to operational review workflows.

It is documentation only. It does not add runtime behavior, database schema, API changes, frontend behavior, indexing behavior, or automated fixes.

## Scope Of This Audit

Reviewed workflow areas:

- retrieval and assistant evaluation runs
- evaluation fixture readiness and smoke runners
- persisted evaluation case results
- run metadata and run comparison
- failed case drill-down
- case-level human annotations
- annotation summary and annotation list
- improvement item generation and explicit case-result links
- improvement regression records
- trend views
- failure triage notes and batch triage operations

Out of scope:

- changing prompts
- changing metadata values
- changing chunking behavior
- changing rerank configuration
- changing retrieval or indexing behavior
- creating suggestions from evaluation results
- triggering reindexing
- creating workflow automation or task assignment

## Current Safety Controls

### PR-Only Development Control

CoreKB uses the Codex PR-only workflow described in `AGENTS.md`.

Current controls:

- every task uses an `agent/task-XXX-task-name` branch
- every task creates an `agent/results/XXX_result.md` file
- GitHub Actions run backend tests and result-file validation on PRs
- Codex must not push directly to `main` or `develop`
- production-impacting changes must be explicitly scoped by the task

Hardening status: strong for repository workflow. Continue enforcing PR-only changes.

### Evaluation Fixture And Runner Control

CoreKB has several evaluation entry points:

- fixture shape validation through `make eval`
- deterministic retrieval smoke testing through `make eval-smoke`
- live API-backed retrieval evaluation through `make eval-real`
- retrieval and assistant evaluation APIs for admin users

Current controls:

- fixture validation is read-only
- smoke evaluation uses deterministic fake retrieval
- live evaluation requires explicit API execution and admin credentials
- Evaluation KB readiness checks prevent silent evaluation against missing fixtures

Hardening status: good. The remaining risk is operational: teams must avoid comparing runs built from different case sets without reading comparability warnings.

### Evaluation Run Metadata Control

Evaluation runs can store:

- `run_label`
- `change_type`
- `change_summary`
- `operator_notes`
- `config_snapshot`

Current controls:

- run metadata is manually provided by operators
- config snapshots make retrieval mode and case set context visible
- display labels and mode summaries improve run selector clarity
- run compare APIs report comparability warnings

Hardening status: good for human explanation. It intentionally does not infer Git commits, code diffs, or true business cause.

### Case Snapshot Control

Evaluation case results persist snapshots of evaluation-time evidence:

- query
- expected document and metadata
- pass/fail result
- failure reason
- suggested fix type
- used metadata filter
- rerank flags
- answer excerpt
- citations
- retrieved results with bounded chunk excerpts and scores

Current controls:

- drill-down reads persisted snapshots only
- drill-down does not rerun Search, Chat, Rerank, or LLM calls
- historical runs without snapshots return unavailable rather than fabricating evidence
- stored excerpts are bounded and do not store complete source documents

Hardening status: strong. Continue preserving the no-rerun rule for all drill-down features.

### Human Annotation Control

Case-level human annotations are separate from system judgment.

Current controls:

- system fields remain intact
- human fields are stored separately
- admin-only APIs manage annotations
- annotations can be filtered and summarized
- annotations can influence improvement item attribution, but do not automatically resolve or mutate production data

Hardening status: good. Future work should avoid turning annotation status into automatic metadata or prompt changes.

### Improvement Item Control

Improvement items summarize failed cases into actionable groups.

Current controls:

- generated from evaluation failures and optional human annotations
- uses an explicit join table between improvement items and case results
- retains `affected_case_ids` as a compatibility summary
- supports status tracking and regression status
- does not automatically change prompt, metadata, chunking, rerank, source documents, or indexes

Hardening status: good for advisory review. Future implementation should keep remediation actions explicit and separate.

### Regression And Trend Control

Regression records connect before and after evaluation runs.

Current controls:

- regression compares persisted evaluation runs
- regression stores before/after metrics, deltas, resolved cases, and still-failed cases
- trend APIs read from existing evaluation runs and regression records
- no automatic alerting, scheduled evaluation, or BI dashboard is created

Hardening status: good. Continue to treat regression pass/fail as a rule-based signal, not proof of business correctness.

### Failure Triage Note Control

Failure triage notes are quick advisory notes attached to evaluation case results.

Current controls:

- notes are separate from annotations and improvement items
- notes support status values: `open`, `reviewing`, `resolved`, `ignored`
- batch triage operations update only triage notes
- batch operations do not create annotations, improvement items, evaluation runs, suggestions, or reindex jobs

Hardening status: acceptable for lightweight review. Continue treating triage notes as scratchpad-level evidence, not source-of-truth root-cause records.

## Current Data Mutation Boundaries

Evaluation workflow features may write evaluation-domain records such as:

- `evaluation_runs`
- `evaluation_case_results`
- case annotations
- improvement items
- improvement-case-result links
- regressions
- triage notes

Evaluation workflow features must not directly write:

- `documents.metadata`
- metadata suggestions
- source documents
- prompts
- chunking settings
- rerank settings
- vector index entries
- indexing jobs
- retrieval configuration

Any future bridge from evaluation findings to production-impacting actions must require explicit human review, audit logging, and a separate task scope.

## Risk Register

| Risk | Current Control | Hardening Recommendation |
| --- | --- | --- |
| Comparing non-comparable runs | comparability warnings and config snapshots | Add reviewer checklist in docs before declaring improvement success. |
| Treating rule-based failure reasons as truth | human annotations are separate from system reasons | Keep system and human judgments visually distinct. |
| Triage notes being mistaken for structured root cause | notes are separate from annotations | Use annotations for root cause; keep triage notes lightweight. |
| Over-automating improvement items | advisory-only documentation | Do not auto-apply prompt, metadata, chunking, rerank, or parser changes. |
| Missing evidence for older runs | drill-down returns unavailable | Do not backfill snapshots by rerunning evaluation under current code. |
| Case excerpts exposing sensitive material | bounded excerpts only | Review excerpt length and masking requirements before using real confidential data. |
| Batch triage mistakes | selected count and backend validation | Consider confirmation dialogs only if operators report accidental bulk edits. |
| Evaluation output creating production mutation pressure | explicit boundaries | Future bridges must create pending review artifacts, not direct writes. |

## Recommended Hardening Phases

### Phase 1: Documentation And Reviewer Discipline

Status: this audit.

Recommended actions:

- keep this audit updated when evaluation workflow behavior changes
- add reviewer checklists for run comparison and regression acceptance
- clarify when to use triage notes versus annotations versus improvement items

### Phase 2: Evidence Integrity Checks

Potential future tasks:

- add tests that drill-down never reruns retrieval or chat
- add tests that case result excerpts remain bounded
- add tests that compare APIs use persisted snapshots only
- add tests that old runs without snapshots stay unavailable

### Phase 3: Human Review Guardrails

Potential future tasks:

- add explicit UI copy distinguishing system judgment and human judgment
- require notes when marking high-impact annotations as resolved or ignored
- add audit logs for annotation and improvement status updates if not already covered

### Phase 4: Safe Bridge Design

Potential future tasks:

- design validation-report-to-suggestion or evaluation-to-suggestion bridges as pending-review only
- require admin confirmation for any suggestion creation
- prevent evaluation findings from directly changing `documents.metadata`
- require audit logs for any bridge-generated pending artifact

### Phase 5: Operational Readiness

Potential future tasks:

- add a reviewer checklist for accepting an improvement regression
- document required evaluation modes for release gates
- define retention expectations for evaluation case snapshots
- define sensitive data review rules for case excerpts before using real production materials

## Non-Goals

This audit does not propose or implement:

- automatic prompt rewriting
- automatic metadata repair
- automatic chunking or rerank tuning
- automatic reindexing
- scheduled evaluation
- alerting
- BI dashboards
- workflow assignment
- LLM-based failure analysis
- ERP, MES, OA, or ticketing integration

## Summary

CoreKB's evaluation workflow is currently shaped as a controlled, evidence-preserving review loop. The strongest controls are persisted case snapshots, no-rerun drill-down, PR-only development, run metadata, and clear separation between system judgments, human annotations, improvement items, regressions, and triage notes.

The main hardening priority is preserving advisory boundaries as the workflow grows. Evaluation outputs should continue to inform human review, not directly mutate production metadata, prompts, documents, indexes, or retrieval configuration.

## Boundary Regression Test Coverage

Task 023 adds regression tests under `backend/app/tests/test_evaluation_boundary_regression.py` to make the advisory boundary executable in CI.

Covered boundaries:

- case drill-down reads saved evaluation snapshots without modifying `documents.metadata`, metadata suggestions, index jobs, annotations, improvement items, improvement links, regressions, or triage notes
- compare-case requests with a missing before/after snapshot return `unavailable` without creating new `evaluation_case_results` or rerunning retrieval/chat logic
- batch triage operations create or update only `evaluation_failure_triage_notes`, and do not create structured annotations, improvement items, suggestions, index jobs, regressions, or metadata mutations

These tests are intentionally narrow. They do not prove every future evaluation feature is safe, but they create a regression fence around the most important current boundary: evaluation review actions can persist advisory evaluation-domain records, but must not silently mutate production knowledge data or indexing state.
