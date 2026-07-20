# Gallery-dl Container

Configs are mounted from `gallery-dl/config/` at runtime (not baked into the image).
The `single-profile.sh` helper script lives at `gallery-dl/scripts/single-profile.sh`.

## Running

There are two archive strategies depending on the site. Pick based on whether
you want to dedupe downloads *per profile* or *across the whole site*.

### Per-profile archives (Instagram)

Instagram is tracked at the profile level, so each profile gets its **own**
archive. `single-profile.sh -s <site>` derives per-URL paths - files go to
`/download/<site>/<profile>` and the archive to
`/download/archive/<site>/<profile>.sqlite3` (`<profile>` is the last path
component of the URL), overriding `config.json`'s default archive. Because every
profile writes to a separate SQLite file, the runs parallelize safely with
`xargs -P`.

```bash
# Full sync (public profiles, no auth)
xargs -n 1 -P 8 gallery-dl/scripts/single-profile.sh \
    -s instagram \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \
    < $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/instagram/instagram-public.txt

# Full sync (stories/highlights, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -s instagram \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile-stories-highlights.json \
    --cookies /download/cookies.txt \
    < $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/instagram/instagram-public.txt

# Full sync (reels/tagged, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -s instagram \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile-reels-tagged.json \
    --cookies /download/cookies.txt \
    < $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/instagram/instagram-public.txt

# Full sync (private profiles, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -s instagram \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \
    --cookies /download/cookies.txt \
    < $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/instagram/instagram-private.txt
```

Add `-A 10` before the URL for incremental sync (abort after 10 already-seen files instead of scanning the full archive).

### Single shared archive (Reddit, Erome, ...)

Sites where the same media is reposted across profiles (reddit, erome) use **one
archive per site** so a repost already downloaded under one profile is skipped
under another. Do **not** use `single-profile.sh` here, run gallery-dl directly
with `-i <urls.txt>` so a single process handles every URL and shares
`config.json`'s default archive (`./archive/{category}.sqlite3`, e.g.
`/download/archive/erome.sqlite3`). The config's `directory` supplies the full
layout (`{category}/...`). A single writer means **no `xargs -P`** - parallel
writers would contend on the one SQLite file.

```bash
# Erome — one process, one archive, dedupes reposts across users
sudo docker-compose run -T --rm gallery-dl \
    -c /var/gallery-dl/.config/gallery-dl/erome.json \
    -i /download/erome/erome.txt

# Reddit — same pattern (the input file lives at $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/reddit/reddit.txt)
sudo docker-compose run -T --rm gallery-dl \
    -c /var/gallery-dl/.config/gallery-dl/reddit.json \
    -i /download/reddit/reddit.txt
```

The input file (`-i`) is read *inside* the container, so use container paths:
`/download/...` maps to `$DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/`. Add `-A 10` for incremental sync.

## Cookie handling

```bash
mv ~/cookies.txt $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/cookies.txt
sudo chown syncthing:service_rw $DATA_ROOT/Personal/Pictures/Synced/Wallpapers/Fun/cookies.txt
```
