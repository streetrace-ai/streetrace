# Dockerfile for GitHub Actions environment testing
# Mimics the ubuntu-latest GitHub Actions runner environment

FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PATH="/root/.local/bin:$PATH"

# Install system dependencies (matching GitHub Actions ubuntu-latest)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    software-properties-common \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Add deadsnakes PPA for Python 3.12
RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.12 as default python3 and create python symlink
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    ln -sf /usr/bin/python3.12 /usr/bin/python

# Install pip for Python 3.12
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Configure Poetry to create virtual environments in project directory
RUN poetry config virtualenvs.in-project true

# Set working directory
WORKDIR /github/workspace

# Copy project files (this will be overridden by volume mount in testing)
COPY . .

# Install project dependencies
RUN poetry install --only=main

# Create directories for GitHub Actions environment simulation
RUN mkdir -p /github/home && \
    mkdir -p /github/workflow && \
    mkdir -p /tmp

# Set GitHub Actions environment variables
ENV GITHUB_WORKSPACE=/github/workspace
ENV GITHUB_ACTIONS=true
ENV CI=true
ENV RUNNER_OS=Linux
ENV RUNNER_ARCH=X64

# Default command - can be overridden
CMD ["/bin/bash"]