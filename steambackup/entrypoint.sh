#!/bin/bash

set -euo pipefail

# Use getopt to read options
#   steam library path, archival path, sync vs new archive, compression level, threads
# List all games in library (via presence of manifest? or via list of folders in steamapps/common?)
# For each game archive the manifest + common + (anything else???)
# From manifest find installdir
#   Probably check if the game has changed since last time (size on disk? appmanifest information? buildid seems reliable. Or for config only changes maybe keep a hash of the appmanifest and compare that.)
#   If mode is new archive then check if 7z can overwrite existing file atomically otherwise create temp archive and mv it into place
#   If mode is sync then use u and modes from docs to sync
#
# Probably also the downloadsize, sizeondisk - we'll use later
# Start compression
# Find compressed size
# Output something like "downloaded x -> installed y to disk -> compressed to z"
# Probably compression ratios as well

SEVEN_Z='/opt/7z/7zz'

COMMON_ARGS=( '-bs0' '-t7z' '-m0=LZMA2' '-mx=9' '-mmt=on' '-ssw' )
# Uncomment and change if running out of memory
# COMMON_ARGS+=( '-mmemuse=p70' )

OVERWRITE_CMD=( "${SEVEN_Z}" "${COMMON_ARGS[@]}" "a" )
SYNC_CMD=( "${SEVEN_Z}" "${COMMON_ARGS[@]}" "u" "-up0q0r2x1y2z1w2" )

usage() {
    printf '%s\n'       "Usage: $0 --steam-library <path> --destination <path> --mode <sync|overwrite>"
    printf '\n'
    printf '%s\t%s\n'   "    --steam-library" "Path to directory containing steamapps folder"
    printf '%s\t%s\n'   "    --destination" "Path to directory where archives will be created (or exist already)"
    printf '%s\t\t%s\n' "    --mode" "One of sync or overwrite."
    printf '\n'
    printf '%s\n'       "    Overwrite: ${OVERWRITE_CMD[*]}"
    printf '%s\n'       "    Sync:      ${SYNC_CMD[*]}"
}

[[ $# -eq 0 ]] && { usage; exit 1; }
while [[ $# -gt 0 ]]; do
    case $1 in
        --steam-library)
            STEAM_LIBRARY_PATH="${2:?$1 expects an argument}"
            shift
            shift;;
        --destination)
            DESTINATION_PATH="${2:?$1 expects an argument}"
            shift
            shift;;
        --mode)
            OPERATION_MODE="${2:?$1 expects an argument}"
            shift
            shift;;
        *)
            echo "Unknown option $1"
            usage
            exit 1;;
    esac
done

APP_MANIFESTS=()

discover_games() {
    for manifest in "${STEAM_LIBRARY_PATH}"/steamapps/*.acf; do
        APP_MANIFESTS+=( "$manifest" )
    done
}

discover_games
for f in "${APP_MANIFESTS[@]}"; do
    echo $f
done
