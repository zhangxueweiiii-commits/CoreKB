# CoreKB Audit Logs

CoreKB audit logs record important user and system actions for review and troubleshooting. They are evidence for human review, not an automation trigger.

## Current Audit Scope

Audit logs are written for key actions such as:

- user login
- user creation and updates
- knowledge base changes
- permission changes
- document upload and deletion
- metadata suggestion generation, acceptance, and rejection
- search and chat requests
- index job control actions

## Request Context

When a request context is available, audit logs preserve:

- `request_id`
- IP address
- user agent
- actor user id
- target knowledge base id
- target document id

This allows metadata review and other production-impacting actions to be traced back to a request.

## Metadata Redaction

Audit metadata is sanitized before it is stored.

Sensitive keys are redacted recursively, including nested objects and arrays:

- `password`
- `api_key`
- `secret`
- `token`
- `authorization`
- `file_content`
- `content`

String metadata values are capped at 500 characters. This helps avoid storing full source documents, large prompt bodies, or oversized payloads in audit rows.

## Metadata Suggestion Audit Boundary

Metadata suggestion audit records keep only traceable review facts, such as:

- suggestion count
- reviewed field
- accepted value
- index job id

They must not store:

- full source document content
- evidence excerpts
- API keys
- passwords
- authorization headers

Accepting a metadata suggestion remains an explicit production-impacting operation because it writes `documents.metadata` and creates a reindex job. Audit logs document that reviewed action, but they do not automatically approve or apply any future suggestion.

## Current Limits

- Audit logs are stored in the application database.
- This task does not add retention policy enforcement.
- This task does not add external SIEM or log platform integration.
- This task does not change audit log schema.
- Audit logs do not automatically mutate metadata, prompts, chunking, rerank settings, source documents, or index jobs.

