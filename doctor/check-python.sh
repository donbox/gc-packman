#!/bin/sh
# Check that Python 3 is available for packman commands.
if command -v python3 >/dev/null 2>&1; then
    version=$(python3 --version 2>&1)
    echo "OK: $version"
    exit 0
else
    echo "Python 3 not found. gc packman requires Python 3."
    exit 2
fi
