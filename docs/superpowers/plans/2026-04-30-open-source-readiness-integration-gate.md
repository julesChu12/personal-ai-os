# Open Source Readiness And Integration Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not create git commits unless the user explicitly requests them.

**Goal:** Prepare Personal AI OS for an open-source workflow by adding release metadata, Docker-level integration checks, and security-conscious defaults without changing the current product scope.

**Architecture:** Keep unit tests fast and isolated with SQLite/stubs, then add a separate Docker smoke layer that validates the real `api + postgres + qdrant` composition. Treat license selection as a human decision and keep all runtime secrets in environment variables.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Qdrant, Docker Compose, GitHub Actions, pytest.

---

## File Structure

- Modify: `pyproject.toml` for package metadata, project URLs, optional dev dependencies, and pytest markers.
- Modify: `README.md` for open-source readiness, integration test usage, and security notes.
- Modify: `.github/workflows/ci.yml` to keep unit CI fast and optionally add Docker smoke validation.
- Modify: `.env.example` to make safe defaults explicit.
- Create: `scripts/smoke_api.sh` for local and CI API smoke checks.
- Create: `tests/test_packaging_contracts.py` for metadata and workflow contracts.
- Create: `docs/open-source-readiness.md` for release checklist and unresolved decisions.
- Optional after user decision: `LICENSE`.

## Task 1: Package Metadata Contract

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_packaging_contracts.py`

- [x] **Step 1: Write failing tests for package metadata**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


import tomllib


def load_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_has_open_source_package_metadata():
    project = load_pyproject()["project"]

    assert project["readme"] == "README.md"
    assert project["license"] == {"file": "LICENSE"}
    assert project["authors"] == [{"name": "Personal AI OS contributors"}]
    assert "License :: OSI Approved :: Apache Software License" in project["classifiers"]
```

- [x] **Step 2: Verify the metadata test fails**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: `tests/test_packaging_contracts.py` fails because metadata and markers are not fully declared.

- [x] **Step 3: Add minimal metadata**

Add package metadata with the user-selected Apache-2.0 license. Do not invent repository URLs until the canonical repository is known:

```toml
readme = "README.md"
authors = [{ name = "Personal AI OS contributors" }]
license = { file = "LICENSE" }
keywords = ["personal-ai", "rag", "open-webui", "local-first"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Framework :: FastAPI",
  "License :: OSI Approved :: Apache Software License",
]

[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "integration: tests that require Docker services",
]
```

- [x] **Step 4: Verify metadata tests pass**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: package metadata tests pass with the rest of the suite.

## Task 2: Docker Smoke Script

**Files:**
- Create: `scripts/smoke_api.sh`
- Create or modify: `tests/test_project_contracts.py`
- Modify: `README.md`

- [x] **Step 1: Write failing contract test for smoke script**

Add to `tests/test_project_contracts.py`:

```python
def test_smoke_script_documents_runtime_health_checks():
    script = read_text("scripts/smoke_api.sh")

    assert "set -euo pipefail" in script
    assert "/health" in script
    assert "/v1/models" in script
    assert "/memory/search" in script
    assert "OPENAI_COMPAT_API_KEY" in script
```

- [x] **Step 2: Verify the contract test fails**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: fails because `scripts/smoke_api.sh` does not exist.

- [x] **Step 3: Add smoke script**

```bash
#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
OPENAI_COMPAT_API_KEY="${OPENAI_COMPAT_API_KEY:-EMPTY}"

curl -fsS "${API_BASE_URL}/health" >/dev/null
curl -fsS \
  -H "Authorization: Bearer ${OPENAI_COMPAT_API_KEY}" \
  "${API_BASE_URL}/v1/models" >/dev/null
curl -fsS \
  "${API_BASE_URL}/memory/search?user_id=smoke&project_id=smoke&query=health&top_k=1" >/dev/null

echo "smoke checks passed"
```

- [x] **Step 4: Keep script runnable through bash**

Run through `bash scripts/smoke_api.sh` to avoid requiring a repository permission change.

- [x] **Step 5: Verify contract tests pass**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: script contract test passes.

## Task 3: CI Integration Gate

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/testing.md`

- [x] **Step 1: Add workflow contract test**

Extend `tests/test_project_contracts.py`:

```python
def test_ci_exposes_optional_docker_smoke_job():
    workflow = read_text(".github/workflows/ci.yml")

    assert "smoke" in workflow
    assert "docker compose up -d --build" in workflow
    assert "scripts/smoke_api.sh" in workflow
```

- [x] **Step 2: Verify the workflow contract fails**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: fails because CI does not yet define the smoke job.

- [x] **Step 3: Add Docker smoke job**

Add a separate job after unit tests:

```yaml
  smoke:
    runs-on: ubuntu-latest
    needs: test
    env:
      OPENAI_COMPAT_API_KEY: EMPTY
      EMBEDDING_PROVIDER: mock
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Start stack
        run: docker compose up -d --build

      - name: Wait for API
        run: |
          for i in {1..30}; do
            curl -fsS http://127.0.0.1:8000/health && exit 0
            sleep 2
          done
          docker compose logs api
          exit 1

      - name: Run smoke checks
        run: bash scripts/smoke_api.sh

      - name: Show logs on failure
        if: failure()
        run: docker compose logs

      - name: Stop stack
        if: always()
        run: docker compose down -v
```

- [x] **Step 4: Verify full local gate**

Run:

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: all unit and contract tests pass locally.

## Task 4: Open Source Readiness Document

**Files:**
- Create: `docs/open-source-readiness.md`
- Modify: `README.md`
- Create after user decision: `LICENSE`

- [x] **Step 1: Add readiness contract test**

Add to `tests/test_project_contracts.py`:

```python
def test_open_source_readiness_document_tracks_release_blockers():
    text = read_text("docs/open-source-readiness.md")

    assert "License" in text
    assert "Secrets" in text
    assert "CI" in text
    assert "Docker smoke" in text
    assert "未决" in text
```

- [x] **Step 2: Verify readiness test fails**

Run:

```bash
make test PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: fails because the document does not exist.

- [x] **Step 3: Create readiness checklist**

```markdown
# Open Source Readiness

## 已完成

- Fast unit and regression suite runs through `make ci`.
- Docker Compose defines API, Open WebUI, PostgreSQL, and Qdrant.
- Runtime secrets are read from environment variables.
- `.gitignore` excludes local env files, caches, virtualenvs, and runtime data.

## 未决

- License: Apache-2.0 selected and recorded in `LICENSE`.
- Repository URLs: replace placeholder URLs in `pyproject.toml`.
- Security policy: decide whether to add `SECURITY.md`.
- Code of conduct: decide whether this project needs `CODE_OF_CONDUCT.md`.

## 发布前检查

- Run `make ci PYTHON=python`.
- Run `docker compose up -d --build`.
- Run `bash scripts/smoke_api.sh`.
- Confirm `.env` is not tracked.
- Confirm README startup steps work on a clean machine.
```

- [x] **Step 4: Update README with release status**

Add a short section linking to `docs/open-source-readiness.md` and stating that Apache-2.0 is the selected license.

- [x] **Step 5: Verify full gate**

Run:

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: all tests pass.

## Task 5: Human Decision Checkpoint

**Files:**
- Optional: `LICENSE`
- Optional: `pyproject.toml`
- Optional: `README.md`

- [x] **Step 1: Ask user for license decision**

Ask for one explicit choice:

```text
请选择开源许可证：MIT、Apache-2.0、AGPL-3.0，或暂不声明。
```

- [x] **Step 2: Apply selected license only after confirmation**

If the user chooses MIT or Apache-2.0, add the corresponding standard license text to `LICENSE`, update `pyproject.toml`, and update `docs/open-source-readiness.md`.

- [x] **Step 3: Verify package metadata and docs**

Run:

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

Expected: all tests pass.

## Verification Checklist

- [x] `make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"` passes.
- [x] `docker compose config --quiet` validates compose syntax.
- [x] `docker compose ps` confirms the stack is running.
- [x] `bash scripts/smoke_api.sh` passes against the running stack.
- [x] `.env` and runtime data remain ignored.
- [x] License decision is explicit before adding `LICENSE`.
