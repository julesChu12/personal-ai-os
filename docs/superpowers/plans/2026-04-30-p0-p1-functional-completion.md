# P0 P1 Functional Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly requests them.

**Goal:** Complete the next P0-P1 functional foundation so the system can validate embeddings, exercise an end-to-end memory loop, preserve project/session semantics, and reduce duplicate memory noise.

**Architecture:** Keep the runtime path simple: provider validation stays close to the embedding provider, smoke checks remain shell-level, API semantics stay inside OpenAI-compatible routing, and memory governance stays inside `MemoryPipeline`. Obsidian file watching is intentionally deferred to a later dedicated spec because it introduces sync and conflict rules.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Qdrant, Docker Compose, pytest, Bash.

---

## Task 1: Embedding Runtime Validation

- [x] Add a provider-level dimension validation helper.
- [x] Add tests that catch vector dimension mismatch before Qdrant writes.
- [x] Add a local script for configured embedding smoke checks.

## Task 2: End-To-End Runtime Smoke

- [x] Extend `scripts/smoke_api.sh` to optionally run a chat write and memory search loop.
- [x] Keep basic smoke fast by default, but make CI run the end-to-end path.
- [x] Document the smoke modes.

## Task 3: OpenAI-Compatible Session Semantics

- [x] Support `metadata.project_id` and `metadata.user_id` in `/v1/chat/completions`.
- [x] Preserve existing defaults for Open WebUI when metadata is absent.
- [x] Add regression tests for metadata project/session routing.

## Task 4: Memory Deduplication

- [x] Skip exact duplicate memory rows within the same user/project/session/type/title/content scope.
- [x] Keep vector writes out of duplicate rows.
- [x] Add regression tests for duplicate and non-duplicate candidates.

## Task 5: Documentation And Verification

- [x] Update README and testing docs with P0-P1 behavior.
- [x] Run `make ci`.
- [x] Run Docker smoke against the current stack.
