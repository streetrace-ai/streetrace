.PHONY: format fixformat lint fixlint typecheck security depcheck unusedcode check

format:
	poetry run black --check src tests

fixformat:
	poetry run black src tests

lint:
	poetry run ruff check src tests

fixlint:
	poetry run ruff check src tests --fix

typecheck:
	poetry run mypy src tests

security:
	poetry run bandit -r src tests

depcheck:
	poetry run deptry src tests

unusedcode:
	poetry run vulture src tests

test:
	poetry run pytest

coverage:
	poetry run coverage run --source=./src/streetrace -m pytest tests

report:
	poetry run coverage report

check: format lint typecheck security depcheck unusedcode
