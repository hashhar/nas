#!/bin/bash

set -euo pipefail

usage() {
    echo "Usage: $0 -s <site> [gallery-dl args ...] <URL>" 1>&2
    exit 1
}

site=""
args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--site)
            [[ $# -ge 2 ]] || usage
            site="$2"
            shift 2
            ;;
        *)
            args+=( "$1" )
            shift
            ;;
    esac
done

[[ -n "$site" ]] || usage
[[ ${#args[@]} -ge 1 ]] || usage

url="${args[-1]}"
unset 'args[-1]'
profile="$(basename "$url")"
destination="/download/$site/$profile"
archive="/download/archive/$site/$profile.sqlite3"

set -x
sudo docker-compose run \
    -T \
    --rm \
    gallery-dl \
    -d "$destination" \
    --download-archive "$archive" \
    "${args[@]}" \
    "$url"

# Other useful options are:
# --cookies /download/cookies.txt
# -o cursor=<position>
set +x
