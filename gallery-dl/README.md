# Gallery-dl Container

Configs are mounted from `gallery-dl/config/` at runtime (not baked into the image).
The `single-profile.sh` helper script lives at `gallery-dl/scripts/single-profile.sh`.

## Running

If you have a file with a list of URLs per line, use `scripts/single-profile.sh`:

```bash
# Full sync (public profiles, no auth)
xargs -n 1 -P 8 gallery-dl/scripts/single-profile.sh \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \
    < $DOCKER_DATA/gallery-dl/data/instagram-public.txt

# Full sync (stories/highlights, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile-stories-highlights.json \
    --cookies /data/cookies.txt \
    < $DOCKER_DATA/gallery-dl/data/instagram-public.txt

# Full sync (reels/tagged, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile-reels-tagged.json \
    --cookies /data/cookies.txt \
    < $DOCKER_DATA/gallery-dl/data/instagram-public.txt

# Full sync (private profiles, requires cookies)
xargs -n 1 -P 2 gallery-dl/scripts/single-profile.sh \
    -c /var/gallery-dl/.config/gallery-dl/instagram-single-profile.json \
    --cookies /data/cookies.txt \
    < $DOCKER_DATA/gallery-dl/data/instagram-private.txt
```

Add `-A 10` before the URL for incremental sync (abort after 10 already-seen files instead of scanning the full archive).

## Cookie handling

```bash
mv ~/cookies.txt $DOCKER_DATA/gallery-dl/data/cookies.txt
sudo chown syncthing:service_rw $DOCKER_DATA/gallery-dl/data/cookies.txt
```
