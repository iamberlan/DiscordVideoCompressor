#!/usr/bin/env bash
# run.sh - Launch Discord Video Compressor

# Navigate to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Detect Python executable
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
elif command -v py &>/dev/null; then
    PYTHON_CMD="py -3"
else
    echo "Error: Python was not found in your PATH."
    echo "Please ensure Python 3 is installed and added to PATH."
    exit 1
fi

echo "Starting Discord Video Compressor with $PYTHON_CMD..."
$PYTHON_CMD run.py "$@"

