FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock LICENSE ./
RUN poetry config virtualenvs.create true --local \
    && poetry config virtualenvs.in-project true --local \
    && poetry install --no-root

COPY . .
RUN poetry install

RUN useradd --create-home ciuser \
    && chown -R ciuser:ciuser /app
USER ciuser

CMD ["make", "check"]
