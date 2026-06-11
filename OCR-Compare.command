#!/bin/bash
# Double-clickable macOS launcher: Finder runs .command files in Terminal.
exec /bin/bash "$(dirname "$0")/bootstrap.sh"
