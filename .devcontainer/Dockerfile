# Multi-stage build for better caching and smaller final image
# Stage 1: Dependencies stage
FROM python:3.12-slim as dependencies

# Set environment variables for Python and Poetry
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_PATH=/workspace/.venv

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    bash-completion \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for MCP tools)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Poetry
RUN pip install poetry==$POETRY_VERSION

# Set working directory
WORKDIR /workspace

# Copy Poetry configuration files, LICENSE, and README
COPY pyproject.toml poetry.lock LICENSE README.md ./

# Install dependencies
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# Stage 2: Development stage
FROM dependencies as development

# Create a non-root user for development
RUN useradd --create-home --shell /bin/bash --user-group --uid 1000 devuser \
    && chown -R devuser:devuser /workspace

# Note: bash configuration files (.bashrc, .bash_aliases) are mounted from host
# via devcontainer.json mounts configuration for live synchronization

# Switch to non-root user
USER devuser

# Set PATH to include Poetry virtual environment
ENV PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH=/workspace/src

# Set default command
CMD ["/bin/bash"]