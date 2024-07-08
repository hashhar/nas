#!/bin/bash

## Inspired by https://blog.onlyservers.sh/using-a-custom-folder-with-synology-photos-dsm7
## Add this as a scheduled task executed by root user.

echo "----------------------------------------"
date --iso-8601=seconds
echo "----------------------------------------"

readonly shared_sources=(
'/volume1/data/Personal/Pictures/Synced/Camera Roll'
'/volume1/data/Personal/Pictures/Synced/Camera Roll Archive'
'/volume1/data/Personal/Pictures/Synced/Piglet'
'/volume1/data/Personal/Pictures/Synced/Saved Pictures'
'/volume1/data/Personal/Pictures/Synced/Screenshots'
)
readonly shared_space_path='/volume1/photo'

readonly personal_sources=(
'/volume1/data/Personal/Pictures/Synced/Wallpapers'
)
readonly personal_space_path='/volume1/homes/hashhar/Photos'

readonly marker_file='.stfolder'

function mount_at_path() {
    source="$1"
    target="$2"

    mount_name="$(basename "${source}")"
    mount_target="${target}/${mount_name}"
    marker_path="${mount_target}/${marker_file}"
    if [[ -e "${marker_path}" ]]; then
        echo "${source} already mounted at ${mount_target}"
    else
        [[ -e "${mount_target}" ]] || mkdir -pv "${mount_target}"
        echo "Mounting ${source} at ${mount_target}"
        sudo mount --bind "${source}" "${mount_target}"
    fi
}

for source in "${shared_sources[@]}"; do
    mount_at_path "${source}" "${shared_space_path}"
done

for source in "${personal_sources[@]}"; do
    mount_at_path "${source}" "${personal_space_path}"
done

# If running on boot then need to wait sometime for the Synology Photos database to be available
echo "Waiting for Synology Photos database to start..."
while ! sudo -u postgres psql; do
    sleep 30
done
echo "Waiting for Synology Photos application to start..."
while ! pgrep -f /var/packages/SynologyPhotos/target/usr/sbin/synofoto-task-center; do
    sleep 30
done

readonly reindex_cmd="sudo /var/packages/SynologyPhotos/target/usr/bin/synofoto-bin-index-tool -t basic_reindex -i ${shared_space_path}"
echo "Starting reindexing: ${reindex_cmd}"
time $reindex_cmd
echo "Finished with: $?"

readonly reindex_motion_cmd="sudo /var/packages/SynologyPhotos/target/usr/bin/synofoto-bin-index-tool -t update_metadata -o motion_photo -i ${shared_space_path}"
echo "Starting regenerating motion photos: ${reindex_motion_cmd}"
time $reindex_motion_cmd
echo "Finished with: $?"

echo "========================================"
