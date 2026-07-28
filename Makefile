.PHONY: validate test

validate:
	python3 scripts/validate_workspace.py

test:
	python3 -m unittest discover -s tests -v
