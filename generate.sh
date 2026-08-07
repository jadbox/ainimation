#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python"
fi

cd "$SCRIPT_DIR"

# Available characters and scenes are defined in the selected film's movie.yml
# (films/<film>/movie.yml; default film is the first folder under films/, or $FILM).

err_no_character() {
    echo "Error: a character name is required." >&2
    echo "Available characters are listed in the film's movie.yml (films/<film>/movie.yml)." >&2
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
