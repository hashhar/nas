#!/bin/bash

set -euo pipefail

usage() {
    echo "Usage: $0 [arg1 arg2 ...] <URL>" 1>&2
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
else
    length=$(( $# - 1 ))
    args=( "${@:1:$length}" )
    url="${@: -1}"
    profile="$(basename "$url")"
    destination="/download/instagram/$profile"
    archive="/download/archive/instagram/$profile.sqlite3"
fi

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
# --cookies /data/cookies.txt
# -o cursor=<position>
set +x
