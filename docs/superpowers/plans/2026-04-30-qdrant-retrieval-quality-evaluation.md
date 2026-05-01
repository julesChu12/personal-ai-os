# Qdrant Retrieval Quality Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly requests them.

**Goal:** Add an end-to-end Qdrant retrieval quality evaluator that writes the golden dataset into Qdrant and validates top-k recall through the same vector search path used by the API.

**Architecture:** Reuse `VectorStore` for Qdrant interactions and the existing golden dataset for expected matches. The evaluator uses isolated `user_id` and `project_id` values so it can run safely against a local Docker stack without mixing with normal user memory.

**Tech Stack:** Python 3.11, Qdrant client, existing embedding provider, pytest, Docker Compose.

---

## Task 1: VectorStore Deterministic Upsert

- [x] Add tests for `upsert_memory(..., point_id=...)`.
- [x] Implement optional deterministic point id support.

## Task 2: Qdrant Evaluation Script

- [x] Add script contract tests for `scripts/evaluate_qdrant_retrieval_quality.py`.
- [x] Implement fixture ingestion into Qdrant.
- [x] Evaluate `/memory/search`-equivalent results through `VectorStore.search`.

## Task 3: Documentation And Verification

- [x] Document mock and real provider usage.
- [x] Run `make ci`.
- [x] Run the Qdrant evaluator against the current Docker stack with mock embeddings.
