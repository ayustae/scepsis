#!/bin/sh
# Scepsis installer wrapper: runs install.py with uv or, without it, with
# python3 >= 3.10. POSIX sh only, so it runs on Linux and macOS alike.
# All arguments are passed through; run with -h for the options.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v uv >/dev/null 2>&1; then
    exec uv run --quiet --no-project --python '>=3.10' "$here/install.py" "$@"
fi
for python in python3 python; do
    if command -v "$python" >/dev/null 2>&1 &&
        "$python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        exec "$python" "$here/install.py" "$@"
    fi
done
echo "error: the Scepsis installer needs uv (https://docs.astral.sh/uv/) or Python >= 3.10" >&2
exit 1
