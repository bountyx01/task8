#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -e .env ] || tools/gen-env.sh
docker compose build
docker compose up -d --wait db
exec docker compose run --rm workbench
