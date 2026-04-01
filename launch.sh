#!/usr/bin/env bash
# Launch Spirit Tube TV — single instance guard, fast start

# Exit if already running
if pgrep -f 'python3.*main\.py' >/dev/null 2>&1; then
    exit 0
fi

cd /home/jott/spirit-tube-tv
exec /usr/bin/python3 main.py
