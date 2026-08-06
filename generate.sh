#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python"
fi

cd "$SCRIPT_DIR"

# Available characters, mirrored from movie.yml for shell-side error messages.
CHARACTERS="Mrs. Brisby, Mr. Ages, Nicodemus, Timothy Frisby, Justin, Jenner, Dragon, The Great Owl"

err_no_character() {
    echo "Error: a character name is required." >&2
    echo "Available characters: $CHARACTERS" >&2
    echo "Usage: $0 <character-name>   or   $0 --character <character-name>   or   $0 --scene <scene-name>" >&2
    exit 2
}

# The first positional argument (if it does not start with '-') is treated as
# the character name and converted to --character <name>.
if [ "$#" -gt 0 ] && [[ "$1" != -* ]]; then
    CHARACTER="$1"
    shift
    exec "$PYTHON" src/blueprint.py --character "$CHARACTER" "$@"
fi

# Scan for a bare --character with no following value (either it is the last
# argument, or the next argument is another flag) and error helpfully.
prev=""
for arg in "$@"; do
    if [ "$prev" = "--character" ] && [[ "$arg" == -* ]]; then
        err_no_character
    fi
    prev="$arg"
done
if [ "$prev" = "--character" ]; then
    err_no_character
fi

exec "$PYTHON" src/blueprint.py "$@"
