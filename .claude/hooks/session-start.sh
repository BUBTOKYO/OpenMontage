#!/bin/bash
# SessionStart hook: install OpenMontage dependencies in Claude Code cloud sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# Python venv + requirements, Remotion npm deps, Piper TTS, HyperFrames npx cache, .env.
# All steps are idempotent (pip/npm skip what is already installed; .env is never overwritten).
make setup
# pytest and friends for running the test suite.
make install-dev

# Make the project venv the default python for the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export VIRTUAL_ENV=\"$PWD/.venv\"" >> "$CLAUDE_ENV_FILE"
  echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
