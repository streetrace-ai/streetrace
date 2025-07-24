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
    POETRY_VIRTUALENVS_CREATE=true

# Install system dependencies and GitHub CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    bash-completion \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for MCP tools)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Poetry
RUN pip install poetry==$POETRY_VERSION

# Set working directory
WORKDIR /workspace


# Stage 2: Development stage
FROM dependencies as development

# Create a non-root user for development
RUN useradd --create-home --shell /bin/bash --user-group --uid 1000 devuser \
    && chown -R devuser:devuser /workspace

# Switch to non-root user
USER devuser

# Configure npm for non-root user
RUN mkdir -p /home/devuser/.npm-global \
    && npm config set prefix '/home/devuser/.npm-global' \
    && echo 'export PATH=/home/devuser/.npm-global/bin:$PATH' >> /home/devuser/.bashrc

# Set default command
CMD ["/bin/bash"]