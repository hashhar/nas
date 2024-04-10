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
    args=${@:1:$length}
    url="${@: -1}"
    destination="/download/instagram/$(basename "$url")"
fi

set -x
sudo docker-compose run \
    -T \
    --rm \
    gallery-dl \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \
    -d "$destination" \
    "${args[@]}" \
    "$url"

# Other useful options are:
# --cookies /data/cookies.txt
# -o cursor=<position>
set +x
EOF

# Now run the script for each line of file
xargs -n 1 single-profile.sh --cookies /data/cookies.txt < /path/to/file-with-urls
```
