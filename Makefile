.PHONY: lint typed security depcheck unusedcode quickcheck check test coverage report publishpatch

lint:
	poetry run ruff check src tests --ignore=FIX002 --fix

typed:
	poetry run mypy src

security:
	poetry run bandit -r src tests

depcheck:
	poetry run deptry src tests

unusedcode:
	poetry run vulture src tests

test:
	poetry run pytest tests -vv --no-header --timeout=5

coverage:
	poetry run coverage run --source=./src/streetrace -m pytest tests

report:
	poetry run coverage report --show-missing

quickcheck: lint

check: lint typed security depcheck unusedcode

publishpatch:
	poetry version patch
	poetry build
	dotenv run poetry publish --username __token__ --password $$POETRY_PYPI_TOKEN
