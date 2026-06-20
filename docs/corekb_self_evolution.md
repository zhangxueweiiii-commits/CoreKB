# CoreKB Controlled Self-Evolution Loop

CoreKB can use evaluations, metadata prechecks, failed-case analysis, and human annotations to improve knowledge quality over time. This document defines the controlled loop for that improvement work.

## Principle

CoreKB may generate suggestions, reports, and improvement items, but automatic suggestions cannot directly mutate production data.

Any change that affects production behavior must be reviewed and explicitly approved by an administrator or operator. This includes metadata changes, prompt changes, chunking changes, rerank configuration changes, dictionary changes, reindexing, and any future bulk repair action.

## Loop

1. Collect evidence
   - Run retrieval or assistant evaluation.
   - Review failed cases and drill-down snapshots.
   - Run metadata precheck reports.
   - Review metadata suggestions and dictionary gaps.

2. Produce advisory findings
   - Summarize failed cases.
   - Generate improvement items.
   - Identify metadata normalization candidates.
   - Record human annotations where expert judgement is needed.

3. Human review
   - Confirm whether the finding is valid.
   - Decide whether the fix belongs to prompt, metadata, chunking, rerank, parser, source document, dictionary, or test case updates.
   - Reject or ignore findings that are not actionable.

4. Apply explicit changes
   - Apply only the reviewed change.
   - Keep changes small and traceable.
   - Reindex only when metadata or document-derived retrieval payloads changed.

5. Verify
   - Re-run the same evaluation set.
   - Compare before and after runs.
   - Check regression warnings and case-level evidence.
   - Record risk notes and remaining limitations.

## Closed-Loop Verification

The metadata quality loop is verified as a sequence of explicit boundaries:

1. `documents.metadata` is inspected by the read-only validator.
2. Validation issues can be persisted as `validation_reports`.
3. A validation report can create pending metadata suggestions through the bridge.
4. The bridge stage must not mutate `documents.metadata`.
5. The bridge stage must not create index jobs or enqueue reindexing.
6. A reviewer must explicitly accept or reject each suggestion.
7. Accepting a suggestion is the only step in this loop that writes formal document metadata and submits a single-document reindex.
8. Rejecting a suggestion must preserve formal metadata and index state.
9. Audit logs must distinguish bridge generation, acceptance, and rejection.

This keeps advisory evidence separate from production-impacting actions.

## Guardrails

- No automatic production metadata overwrite.
- No automatic acceptance of metadata suggestions.
- No automatic prompt rewrite.
- No automatic chunking or rerank parameter changes.
- No automatic production reindex unless explicitly triggered by an approved operation.
- No secrets, API keys, passwords, or full document contents in agent task results.
- No new dependencies or production configuration changes without a scoped task.

## Agent Task Contract

Every future Codex task should specify:

- Allowed paths
- Non-goals
- Whether runtime code may be changed
- Whether database migrations are allowed
- Verification commands
- Expected output format

If the task scope is unclear, the agent should stop before editing production-impacting files and ask for clarification.

## Current Entry Points

- `make agent-test`: verifies that the agent workflow files exist.
- `make eval`: placeholder for a future read-only evaluation command.

The `eval` target is intentionally a placeholder in this initialization step. A later task can connect it to the CoreKB retrieval and assistant evaluation workflow once the command contract is defined.
