#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -e .env ] || tools/gen-env.sh
docker compose build workbench
exec docker compose up -d --wait
