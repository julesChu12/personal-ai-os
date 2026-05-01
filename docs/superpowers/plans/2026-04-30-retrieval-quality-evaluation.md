# Retrieval Quality Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly requests them.

**Goal:** Add a repeatable retrieval quality evaluation path that works offline with mock embeddings and can be switched to a real OpenAI-compatible embedding provider.

**Architecture:** Keep ranking and metrics in a small pure module, keep fixture data in `tests/fixtures`, and expose a script for local/CI use. The script reuses the existing embedding provider configuration and does not require Qdrant.

**Tech Stack:** Python 3.11, pytest, existing embedding provider abstraction, JSON fixtures.

---

## Task 1: Golden Dataset

- [x] Add retrieval quality fixture with memory records, query records, expected memory ids, and default `top_k`.
- [x] Add tests that load and validate the fixture shape.

## Task 2: Evaluator Module

- [x] Add cosine similarity, memory ranking, query evaluation, and aggregate hit-rate calculation.
- [x] Add tests for top-k hits, misses, and invalid vector dimensions.

## Task 3: Evaluation Script

- [x] Add `scripts/evaluate_retrieval_quality.py`.
- [x] Support default fixture path, `--top-k`, and `--json`.
- [x] Reuse `build_embedding_provider()`.

## Task 4: Documentation And Verification

- [x] Document mock and real provider usage.
- [x] Add contract tests for script and docs.
- [x] Run `make ci`.
- [x] Run the evaluation script with mock provider.
