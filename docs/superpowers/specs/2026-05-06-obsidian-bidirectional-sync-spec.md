# Obsidian Bidirectional Sync — Specification

**Created:** 2026-05-06
**Ambiguity score:** 0.16 (gate: <= 0.20)
**Requirements:** 9 locked

## Goal

Turn Obsidian from a one-way import/write target into a safe, auditable bidirectional sync source where vault files and Personal AI OS memories converge without silent overwrite or uncontrolled deletion.

## Background

Current Obsidian support is intentionally one-way:

- `ObsidianWriter` writes new markdown files under the configured vault path.
- `ObsidianImporter` scans markdown files, skips hidden directories, parses simple frontmatter, and imports candidates through `MemoryPipeline.persist()`.
- `MemoryPipeline.persist()` updates existing memories by `user_id + project_id + memory_type + title`, writes vectors to Qdrant, and records `obsidian_path`.
- `/memory/obsidian/import`, `obsidian-import`, and `scripts/import_obsidian_vault.py` expose manual one-way import.
- File deletions do not propagate to DB/Qdrant, and DB/API edits do not update existing Obsidian files.

The missing capability is a controlled sync loop with state tracking, conflict detection, preview mode, explicit deletion behavior, and testable consistency guarantees.

## Requirements

1. **Sync state classification**: The system must classify each Obsidian-linked memory into a deterministic sync state before applying changes.
   - Current: `Memory` stores `obsidian_path` but no file hash, DB hash, last synced timestamp, deletion marker, or conflict status.
   - Target: A sync dry-run can classify records and files as `unchanged`, `vault_only`, `db_only`, `vault_changed`, `db_changed`, `both_changed`, `vault_deleted`, or `path_missing`.
   - Acceptance: A test fixture with one example of each state produces the expected dry-run classification without writing DB, Qdrant, or files.

2. **Dry-run first**: Every sync entrypoint must support previewing planned changes before mutating anything.
   - Current: The import endpoint immediately persists parsed vault files.
   - Target: API, CLI, and script sync entrypoints support a dry-run mode that returns planned operations and counts.
   - Acceptance: Running dry-run against changed files returns a structured report and leaves database rows, Qdrant point ids, and markdown contents unchanged.

3. **Vault-to-memory updates**: Vault file changes must update existing DB/Qdrant memory records without creating duplicates.
   - Current: Re-import updates by memory identity when `memory_type + title` match, but it does not use sync metadata to distinguish external file edits from stale state.
   - Target: A changed vault file linked to an existing memory updates that memory content, tags, importance, `obsidian_path`, and Qdrant vector in one sync operation.
   - Acceptance: Editing a linked markdown file and running sync updates exactly one `Memory` row and reuses or replaces the expected Qdrant point according to the existing vector upsert contract.

4. **Memory-to-vault updates**: DB/API-side changes must update the existing linked markdown file instead of creating a second note.
   - Current: `ObsidianWriter.write_memory()` always creates a timestamped file when no candidate `obsidian_path` is supplied, and update flows may point to newly created files.
   - Target: If a memory has a valid `obsidian_path`, sync writes the current DB memory back to that same file while preserving required frontmatter.
   - Acceptance: Updating a memory row and running sync changes the linked file content in place and does not create another markdown file for the same memory.

5. **Conflict detection**: If both vault and DB changed since the last successful sync, the system must not choose a winner silently.
   - Current: No last-sync baseline exists, so simultaneous edits cannot be detected.
   - Target: `both_changed` items are marked as conflicts, excluded from automatic mutation, and returned with enough metadata for manual resolution.
   - Acceptance: A test where both the file body and DB content changed reports one conflict and preserves both sides unchanged after sync.

6. **Safe deletion policy**: Deletions must be explicit and non-destructive by default.
   - Current: Removing a markdown file does not affect DB/Qdrant; deleting a DB row has no Obsidian behavior.
   - Target: Default sync reports deletions but does not delete DB rows, Qdrant vectors, or vault files unless an explicit deletion policy is selected.
   - Acceptance: With default settings, deleting a linked markdown file yields `vault_deleted` in the report and leaves the DB row and Qdrant point id intact.

7. **Scope isolation**: Sync must stay inside the configured vault and user/project boundary.
   - Current: Importer reads from the configured vault and persists under caller-provided `user_id/project_id`; write tools already enforce vault path boundaries.
   - Target: Sync rejects paths outside the configured vault, skips hidden directories, and never mutates memories outside the requested `user_id/project_id`.
   - Acceptance: A vault containing hidden files and a path escape attempt results in skipped/rejected entries, and a different user's memories are not changed.

8. **Observable sync report**: Every sync run must produce a human-readable and machine-readable report.
   - Current: Import returns only `{"imported": count}`.
   - Target: Sync reports counts by state/action, changed paths, memory ids, conflicts, skipped files, and errors through API/CLI/script JSON.
   - Acceptance: CLI `--json` output includes stable keys for `summary`, `planned`, `applied`, `conflicts`, `skipped`, and `errors`.

9. **Regression coverage**: The bidirectional behavior must be covered without depending on real Qdrant or a real user vault.
   - Current: `tests/test_obsidian_importer.py` uses a fake vector store for import coverage.
   - Target: Unit tests cover state classification, dry-run, vault-to-memory, memory-to-vault, conflict, deletion default, path safety, and CLI/API report shape using temporary vaults and fake vector stores.
   - Acceptance: The relevant pytest suite passes locally without Docker services.

## Boundaries

**In scope:**

- Bidirectional sync specification for vault files and `Memory` rows.
- Sync state tracking sufficient to detect unchanged, changed, deleted, and conflicted items.
- Dry-run and apply modes.
- Vault-to-memory update path.
- Memory-to-vault update path.
- Conflict detection without automatic conflict resolution.
- Safe deletion reporting with non-destructive default behavior.
- API, CLI, and script entrypoints for sync reports.
- Unit tests with temporary vaults and fake vector stores.

**Out of scope:**

- Real-time filesystem watcher — polling or manually triggered sync is enough for the first bidirectional phase.
- Automatic conflict merging — conflicts must be surfaced, not auto-resolved.
- Hard deletion propagation by default — destructive behavior needs a separate explicit policy.
- Multi-device sync transport — Obsidian's own file sync layer remains external to this project.
- Rich YAML parser compatibility for every Obsidian plugin format — first phase only needs the project's supported frontmatter contract.
- UI conflict resolution screen — CLI/API report is enough for this phase.

## Constraints

- The implementation must preserve the local-first model and must not require network access beyond the existing embedding/vector provider path.
- Sync must use configured `OBSIDIAN_VAULT_PATH` and reject path escape.
- Sync must preserve existing `MemoryPipeline` update-or-create and vector failure safety semantics.
- Dry-run must be side-effect free for DB, Qdrant, and files.
- Default deletion behavior must be non-destructive.
- Tests must run without Docker and without a real Obsidian vault.

## Acceptance Criteria

- [ ] Dry-run classifies unchanged, vault-only, DB-only, vault-changed, DB-changed, both-changed, vault-deleted, and path-missing states.
- [ ] Dry-run does not change database rows, Qdrant point ids, or markdown file contents.
- [ ] Applying vault-to-memory sync updates one existing memory row and its vector without creating a duplicate.
- [ ] Applying memory-to-vault sync updates the existing linked markdown file in place.
- [ ] Simultaneous vault and DB edits are reported as conflicts and are not overwritten.
- [ ] Default deletion handling reports deleted/missing files without deleting DB rows, Qdrant vectors, or vault files.
- [ ] Sync rejects or skips files outside the configured vault and hidden directories.
- [ ] API, CLI, and script entrypoints expose stable JSON reports.
- [ ] Unit tests cover the sync behavior with temporary vaults and fake vector stores.
- [ ] Project documentation states the deletion and conflict policies clearly.

## Ambiguity Report

| Dimension           | Score | Min   | Status | Notes |
|---------------------|-------|-------|--------|-------|
| Goal Clarity        | 0.90  | 0.75  | met    | Goal is convergence without silent overwrite. |
| Boundary Clarity    | 0.86  | 0.70  | met    | Real-time watcher, auto-merge, and destructive deletes are excluded. |
| Constraint Clarity  | 0.74  | 0.65  | met    | Local-first, vault boundary, dry-run safety, and test isolation are explicit. |
| Acceptance Criteria | 0.84  | 0.70  | met    | Pass/fail criteria cover the main sync states and surfaces. |
| **Ambiguity**       | 0.16  | <=0.20| met    | Ready for implementation planning. |

## Interview Log

| Round | Perspective     | Question summary | Decision locked |
|-------|-----------------|------------------|-----------------|
| 1     | Researcher      | What exists today? | Current implementation supports Obsidian writes and one-way import only. |
| 2     | Simplifier      | What is the smallest useful bidirectional version? | Manual/poll-style sync with dry-run and apply is enough; no watcher required. |
| 3     | Boundary Keeper | What is explicitly out of scope? | No real-time watcher, no auto-merge, no default destructive deletion, no UI screen. |
| 4     | Failure Analyst | What failure would make this unsafe? | Silent overwrite, path escape, cross-user mutation, and destructive deletion must be prevented. |
| 5     | Seed Closer     | What must be decided before planning? | Conflict and deletion policies are report-first and non-destructive by default. |

## Suggested Follow-up Tasks

1. Plan the sync-state model and migration.
2. Plan the sync engine API around dry-run/apply reports.
3. Plan CLI/API/script entrypoints.
4. Plan regression tests before implementation.

---

*Spec created: 2026-05-06*
*Next step: create an implementation plan for Obsidian bidirectional sync.*
