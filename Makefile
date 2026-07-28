.PHONY: validate test audit lint pipeline

# Default project for audit/lint targets; override: make audit PROJECT=projects/<slug>
PROJECT ?= projects/salt-in-the-wire
SCENE   ?= ch01-sc01

validate:
	python3 scripts/validate_workspace.py

test:
	python3 -m unittest discover -s tests -v

# Deterministic hard audit (Audit 1): chronology, knowledge cutoff, promises, causal refs.
audit:
	python3 scripts/hard_audit.py $(PROJECT)

# Deterministic defaultness linter over a scene's candidates.
lint:
	python3 scripts/defaultness_lint.py $(PROJECT) $(SCENE)

# Full deterministic gate: schema/KB validation, then hard audit, then tests.
pipeline: validate audit test
