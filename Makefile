PYTHON ?= python
DATABASE_URL ?= sqlite:///:memory:

.PHONY: ci compile test migration-smoke

ci: compile test migration-smoke

compile:
	DATABASE_URL="$(DATABASE_URL)" "$(PYTHON)" -m compileall -q app tests

test:
	DATABASE_URL="$(DATABASE_URL)" "$(PYTHON)" -m pytest -q

migration-smoke:
	DATABASE_URL="$(DATABASE_URL)" "$(PYTHON)" scripts/run_migrations.py --dry-run
