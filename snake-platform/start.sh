#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
chmod +x start.sh 2>/dev/null || true
exec python3 launch.py "$@"
