#!/bin/zsh

set -eu

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON310=/opt/homebrew/opt/python@3.10/bin/python3.10

if [[ ! -x "$PYTHON310" ]]; then
  print -u2 "Python 3.10 was not found at $PYTHON310"
  exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  uv venv --python "$PYTHON310" "$PROJECT_DIR/.venv"
fi

uv pip install \
  --python "$PROJECT_DIR/.venv/bin/python" \
  --requirement "$PROJECT_DIR/requirements-macos-libero.txt"

print "Open Teach macOS environment is ready."
print "Next: source scripts/macos_env.sh"
