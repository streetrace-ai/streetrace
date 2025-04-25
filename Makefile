.PHONY: format lint typecheck security check

format:
	black --check src tests

fixformat:
	black src tests

lint:
	ruff check src tests

fixlint:
	ruff check src tests --fix

typecheck:
	mypy src tests

security:
	bandit -r src tests

check: format lint typecheck security