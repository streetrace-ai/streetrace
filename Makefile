.PHONY: lint typed security depcheck unusedcode test coverage check publishpatch

lint:
	poetry run ruff check src tests --ignore=FIX002

typed:
	poetry run mypy src

security:
	poetry run bandit -rq src

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
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "❌ You must be on 'main' to publish."; \
		exit 1; \
	fi
	@if [ "$$(git status --porcelain)" != "" ]; then \
		echo "❌ Working directory not clean."; \
		exit 1; \
	fi
	make check
	poetry version patch
	poetry build
	@git add pyproject.toml
	@git commit -m "Release v$$(poetry version -s)"
	@git tag v$$(poetry version -s)
	@git push origin HEAD
	@git push origin v$$(poetry version -s)