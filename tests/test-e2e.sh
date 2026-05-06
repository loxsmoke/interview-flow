#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ -x ".venv/bin/python" ]; then
    export E2E_PYTHON="${E2E_PYTHON:-$ROOT_DIR/.venv/bin/python}"
elif command -v python3 >/dev/null 2>&1; then
    export E2E_PYTHON="${E2E_PYTHON:-python3}"
else
    export E2E_PYTHON="${E2E_PYTHON:-python}"
fi

if [ ! -x "node_modules/.bin/playwright" ]; then
    echo "Installing Node dependencies..."
    npm install
fi

_chrome_installed() {
    case "$(uname -s)" in
        Darwin)
            [ -d "/Applications/Google Chrome.app" ] && return 0
            ls "${HOME}/Library/Caches/ms-playwright"/chrome-mac* >/dev/null 2>&1 && return 0
            ;;
        *)
            command -v google-chrome >/dev/null 2>&1 && return 0
            command -v google-chrome-stable >/dev/null 2>&1 && return 0
            ls "${HOME}/.cache/ms-playwright"/chrome-linux* >/dev/null 2>&1 && return 0
            ;;
    esac
    return 1
}

if ! _chrome_installed; then
    echo "Installing Playwright Chrome browser..."
    if [ "$(uname -s)" = "Linux" ]; then
        node_modules/.bin/playwright install --with-deps chrome
    else
        node_modules/.bin/playwright install chrome
    fi
fi

npm run test:e2e -- "$@"
