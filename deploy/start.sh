#!/bin/sh
set -eu

# Download once into a mounted persistent volume, never into the image.
if [ ! -f "${ASHTADHYAYI_DATA_DIR:-/data}/current" ]; then
    ashtadhyayi-mcp sync --profile full
fi
exec ashtadhyayi-mcp serve-http --host 0.0.0.0
