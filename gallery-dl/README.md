# Gallery-dl Container

If you have a file with a list of URLs per line you can do something like:

```bash
cat <<'EOF' > single-profile.sh
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
#-c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \

# Other useful options are:
# --cookies /data/cookies.txt
# -o cursor=<position>
set +x
EOF

# Now run the script for each line of file
xargs -n 1 single-profile.sh --cookies /data/cookies.txt < /path/to/file-with-urls
```

And some example commands which use the above script:

```bash
# Cookie handling
mv ~/cookies.txt ../../appdata/gallery-dl/data/cookies.txt
sudo chown syncthing:service_rw ../../appdata/gallery-dl/data/cookies.txt

# Full sync
xargs -n 1 -P 8 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile.json < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile-stories-highlights.json --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile-reels-tagged.json --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile.json --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-private.txt

# Incremental sync (-A is for abort instead of skip)
xargs -n 1 -P 8 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile.json -A 10 < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile-stories-highlights.json -A 10 --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile-reels-tagged.json -A 10 --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-public.txt
xargs -n 1 -P 2 ../../appdata/gallery-dl/single-profile.sh -c /data/instagram-single-profile.json -A 10 --cookies /data/cookies.txt < ../../appdata/gallery-dl/data/instagram-private.txt
```
