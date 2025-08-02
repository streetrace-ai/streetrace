#!/bin/bash
# Setup environment for StreetRace

set -euo pipefail

echo "Installing MCP servers..."
npm install -g @modelcontextprotocol/server-filesystem

echo "Configuring Poetry..."
poetry config virtualenvs.create true --local
poetry config virtualenvs.in-project true --local

echo "Installing dependencies..."
poetry install

echo "Environment setup complete!"