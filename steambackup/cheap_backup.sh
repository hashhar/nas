#!/bin/bash

set -euo pipefail

TIMEFORMAT=$'%3lR'

if [[ $# -ne 2 ]]; then
    echo "Usage: ${0} <backup_dest> <backup_source>"
    exit 1
fi

backup_dest="${1:?First argument should be path where archives should be created}"
backup_source="${2:?Second argument should be path which should be backed up}"

archive_dir="${backup_dest}/$(dirname "${backup_source}")"
archive_name="$(basename "${backup_source}").7z"
archive_path="${archive_dir}/${archive_name}"

mkdir -p "${archive_dir}"

common_args=( '-bso0' '-t7z' '-m0=LZMA2' '-mx=9' '-myx=9' '-mmt=on' '-ssw' '-mmemuse=p90' )
sync_args=( "${common_args[@]}" 'u' '-up1q0r2x1y2z1w2' )
create_args=( "${common_args[@]}" 'a' )

mode='create'
# If archive exists then verify it's ok
if [[ -e "${archive_path}" ]]; then
    # will still log errors, only listing is directed to /dev/null
    if ! 7zz -bso0 l "${archive_path}" >/dev/null; then
        echo "${archive_path} seems to be corrupted, will remove and re-archive."
        rm "${archive_path}"
    else
        mode='sync'
    fi
fi

if [[ "${mode}" == 'sync' ]]; then
    cmd=( '7zz' "${sync_args[@]}" "${archive_path}" "${backup_source}" )
    echo "Synchronizing: ${cmd[*]}"
    time "${cmd[@]}"
elif [[ "${mode}" == 'create' ]]; then
    cmd=( '7zz' "${create_args[@]}" "${archive_path}" "${backup_source}" )
    echo "Creating: ${cmd[*]}"
    time "${cmd[@]}"
else
    echo "Unexpected mode: ${mode}"
    exit 1
fi

# Broaden permissions to allow updating
chmod 777 "${archive_path}"

# Print some pretty output
if [[ "$OSTYPE" == linux* ]]; then
    uncompressed_bytes="$(du -bs "${backup_source}" | cut -f1)"
    compressed_bytes="$(du -bs "${archive_path}" | cut -f1)"
elif [[ "$OSTYPE" == darwin* ]]; then
    uncompressed_bytes="$(gdu -bs "${backup_source}" | cut -f1)"
    compressed_bytes="$(gdu -bs "${archive_path}" | cut -f1)"
else
    echo "Unexpected OS: ${OSTYPE}"
fi

ratio="$(echo "scale=2; (${compressed_bytes}/${uncompressed_bytes})*100" | bc)"
uncompressed_size="$(printf '%s\n' "${uncompressed_bytes}" | numfmt --to=iec-i)B"
compressed_size="$(printf '%s\n' "${compressed_bytes}" | numfmt --to=iec-i)B"
echo "${ratio}%   (   ${uncompressed_size} =>   ${compressed_size})"
