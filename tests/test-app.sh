#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -n "$TEST_PYTHON" ]; then
    PYTHON="$TEST_PYTHON"
elif [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    PYTHON="python"
fi

if [ "$#" -eq 0 ]; then
    set -- tests/app
fi

if ! "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
    echo "Installing pytest into the selected Python environment..."
    "$PYTHON" -m pip install pytest
fi

mkdir -p tests/.tmp
export TMPDIR="$ROOT_DIR/tests/.tmp"
PYTEST_TEMP="tests/.tmp/pytest-temp-$$"

"$PYTHON" -m pytest --basetemp="$PYTEST_TEMP" -o cache_dir=tests/.tmp/pytest-cache "$@"
