.PHONY: format fixformat lint fixlint typecheck security depcheck unusedcode check test coverage report quickfix publishpatch

format:
	poetry run black --check src tests

fixformat:
	poetry run black src tests

lint:
	poetry run ruff check src tests

fixlint:
	poetry run ruff check src tests --fix

fixlintunsafe:
	poetry run ruff check src tests --fix --unsafe-fixes

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
	poetry run coverage report --show-missing

quickfix: fixformat fixlint

check: format lint typecheck security depcheck unusedcode

publishpatch:
	poetry version patch
	poetry build
	poetry run poetry publish --username __token__ --password $$POETRY_PYPI_TOKEN
