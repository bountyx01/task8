#!/usr/bin/env bash
set -eu
if [ "$#" -ne 2 ]; then printf 'Usage: %s SOURCE NEW_REPORT_DIR\n' "$0" >&2; exit 2; fi
src=$(cd "$1" && pwd -P)
base=$(cd "$(dirname "$0")" && pwd -P)
mkdir -p "$(dirname "$2")"
parent=$(cd "$(dirname "$2")" && pwd -P)
out="$parent/$(basename "$2")"
case "$out/" in "$src/"*) printf 'Output must be outside the source tree\n' >&2; exit 2;; esac
mkdir -m 700 "$out"
flags=(--rm --read-only --tmpfs /tmp --cap-drop=ALL --security-opt no-new-privileges --cpus=2 --memory=2g --pids-limit=256 --network=bridge -u "$(id -u):$(id -g)" --mount "type=bind,src=$src,dst=/src,readonly" --mount "type=bind,src=$out,dst=/out")
for image in semgrep-scan:1.186.0 bandit-scan:1.9.4; do
    tool=${image%%-scan:*}
    docker image inspect --format '{{json .Id}} {{json .Config.Labels}}' "$image" > "$out/$tool.image"
    status=0
    docker run "${flags[@]}" "$image" > "$out/$tool.log" 2>&1 || status=$?
    printf '%s\n' "$status" > "$out/$tool.exit"
    if [ "$status" -ne 0 ] && ! { [ "$tool" = bandit ] && [ "$status" -eq 1 ]; }; then
        printf '%s failed (%s): %s/%s.log\n' "$tool" "$status" "$out" "$tool" >&2; exit 1
    fi
done
python3 -I "$base/parse_reports.py" "$src" "$out"
