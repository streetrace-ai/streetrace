.PHONY: lint typed security depcheck unusedcode test coverage check publishpatch

lint:
	poetry run ruff check src tests --ignore=FIX002

typed:
	poetry run mypy src

security:
	poetry run bandit -r src

depcheck:
	poetry run deptry src tests

unusedcode:
	poetry run vulture src vulture_allow.txt

test:
	poetry run pytest tests -vv --no-header --timeout=5 -q

coverage:
	poetry run coverage run --source=./src/streetrace -m pytest tests
	poetry run coverage report --show-missing
	poetry run coverage html

check: test lint typed security depcheck unusedcode

publishpatch:
	poetry version patch
	poetry build
	dotenv run poetry publish --username __token__ --password $$POETRY_PYPI_TOKEN
