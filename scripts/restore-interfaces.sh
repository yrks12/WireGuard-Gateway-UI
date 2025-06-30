#!/bin/bash
# WireGuard Interface Restoration Shell Wrapper
# This script is called by systemd before starting the main application

set -e

# Define paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$SCRIPT_DIR/restore-interfaces.py"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"

# Log file
LOG_FILE="/var/log/wireguard-gateway/restore.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

echo "$(date): Starting WireGuard interface restoration..." >> "$LOG_FILE"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "$(date): ERROR: Restoration script not found: $PYTHON_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "$(date): ERROR: Python virtual environment not found: $VENV_PYTHON" >> "$LOG_FILE"
    exit 1
fi

# Run the restoration script
echo "$(date): Executing restoration script..." >> "$LOG_FILE"
"$VENV_PYTHON" "$PYTHON_SCRIPT"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "$(date): Interface restoration completed successfully" >> "$LOG_FILE"
else
    echo "$(date): Interface restoration failed with exit code $exit_code" >> "$LOG_FILE"
fi

exit $exit_code