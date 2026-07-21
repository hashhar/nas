# Restructure into folder-per-stack compose projects (greenfield redeploy)

## Context

The repo runs 15 services from a single 329-line `docker-compose.yml`, and Loki, Dozzle, the *arr apps, and Paperless are incoming — the file would roughly double. The chosen direction is **independent per-stack compose projects** (folder-per-stack), the dominant homelab idiom, giving per-stack lifecycles and blast radius. The remote Immich worker files already follow this pattern.

This is the **greenfield version** of the plan: we accept a full redeploy (recreate secrets, move files, migrate state) in exchange for a cleaner end state. Compared to the conservative variant it additionally: co-locates service config dirs with their stack, replaces all named volumes with bind mounts under `$DOCKER_DATA`, adopts SOPS+age encrypted secrets in-repo, reserves the static-IP range on the bridge network, and folds in the pending `plans/security.md` hardening. Existing data (Immich DB, certs, metrics history) is *carried over* by file copy — "greenfield" refers to layout and config, not data loss.

Stack grouping (5 stacks): **infra** (caddy, restic-rest-server) · **monitoring** (prometheus, grafana, alertmanager, smartctl-exporter, node-exporter; Loki/Dozzle later) · **media** (plex, qbittorrent, gallery-dl; *arrs later) · **photos** (immich ×5) · **sync** (syncthing). Paperless becomes a new stack later.

## Target directory tree

```
nas/
├── .env                          # shared vars, single source of truth (tracked)
├── .sops.yaml                    # SOPS creation rules: age recipients for **/secrets.enc.env
├── compose.sh                    # POSIX wrapper: networks|decrypt|up|down|pull|ps|logs|build|gallery-dl
├── stacks/
│   ├── infra/
│   │   ├── docker-compose.yml    # name: infra — caddy, restic-rest-server
│   │   ├── .env -> ../../.env
│   │   └── caddy/                # Dockerfile, Caddyfile, secrets.enc.env
│   ├── monitoring/
│   │   ├── docker-compose.yml    # name: monitoring
│   │   ├── .env -> ../../.env
│   │   ├── prometheus/           # prometheus.yml.tpl, alerts.yml, entrypoint.sh
│   │   ├── grafana/              # provisioning, secrets.enc.env
│   │   └── alertmanager/         # Dockerfile, config tpl, secrets.enc.env
│   ├── media/
│   │   ├── docker-compose.yml    # name: media — plex, qbittorrent, gallery-dl (profile-gated)
│   │   ├── .env -> ../../.env
│   │   ├── qbittorrent/          # custom-cont-init.d, config tpl, secrets.enc.env
│   │   └── gallery-dl/           # Dockerfile, config/, scripts/
│   ├── photos/
│   │   ├── docker-compose.yml    # name: photos — immich ×5
│   │   ├── .env -> ../../.env
│   │   └── immich/               # immich.json, secrets.enc.env,
│   │                             # docker-compose.remote-{transcode,ml,ml-cuda}.yml, systemd/
│   └── sync/
│       ├── docker-compose.yml    # name: sync — syncthing (host network)
│       └── .env -> ../../.env
├── docker-compose.yml            (DELETED)
├── <old root service dirs>       (MOVED into stacks/, per above)
├── README.md  CLAUDE.md  .github/dependabot.yml  .gitignore  TODO.md  plans/   (updated)
```

## Design decisions

1. **Co-located service dirs.** Each stack dir contains its compose file and its services' config dirs; relative paths are plain `./caddy/…`. The desktop-run Immich remote-worker files and systemd templates move with the photos stack (`stacks/photos/immich/`) — the systemd `.service.tpl` files get their `-f` paths updated to `stacks/photos/immich/docker-compose.remote-*.yml` and are re-rendered on the desktop during cutover.
2. **No named volumes — bind mounts under `$DOCKER_DATA`.** The six named volumes become bind mounts, matching every other service in the repo: caddy `/data`→`$DOCKER_DATA/caddy/data`, `/config`→`$DOCKER_DATA/caddy/config`; `$DOCKER_DATA/prometheus/data`; `$DOCKER_DATA/grafana/data`; `$DOCKER_DATA/immich/postgres`; `$DOCKER_DATA/immich/model-cache`. One storage root, uniform restic coverage, and the volume-adoption/project-rename hazard disappears permanently. Ownership per service UID/GID is set once during cutover (postgres and grafana images run as their own internal users — chown to the uid the container actually uses, verified at cutover).
3. **SOPS + age encrypted secrets in-repo.** Tracked `secrets.enc.env` per secretful service (caddy, qbittorrent, grafana, alertmanager, immich), encrypted with age recipients for the NAS, the desktop, and the operator's personal key via `.sops.yaml` creation rules. `./compose.sh decrypt` renders gitignored plaintext `secrets.env` next to each encrypted file; `env_file:` points at the plaintext as today. SOPS dotenv mode keeps variable *names* plaintext in git (self-documenting — the `secrets.env.example` files are retired), values encrypted. Bootstrap for a fresh host: install `sops` + `age` static binaries, place the age key at `~/.config/sops/age/keys.txt`, run `./compose.sh decrypt`. This closes the repo's "clone and simply deploy" goal — secrets become versioned and recoverable.
4. **Networks: pre-created external, with the dynamic pool carved out.**
   ```sh
   docker network create --driver macvlan --opt parent=eth0 --subnet 192.168.2.0/24 nas_macvlan
   docker network create --driver bridge --subnet 172.18.0.0/16 --ip-range 172.18.128.0/17 nas_bridge
   ```
   `--ip-range` confines dynamic allocation to the high half so it can never collide with pinned addresses — a latent bug in the current design now that multiple projects share the pool. **Only load-bearing IPs stay pinned**: caddy `192.168.2.3` + `172.18.0.3` (Tailscale DNS target, `IMMICH_TRUSTED_PROXIES`), immich-redis `172.18.0.10` and immich-database `172.18.0.11` (dialed directly by the desktop workers over Tailscale, where container DNS doesn't exist). All other pins are dropped — Caddy, Prometheus, and Grafana already address everything by container name. Future services need no IP bookkeeping (supersedes the `TODO.md` Authelia `.17` allocation).
5. **Cross-stack DNS**: every service keeps `container_name:` equal to its service name; container names resolve on a shared user-defined network regardless of compose project.
6. **Project names**: top-level `name: infra|monitoring|media|photos|sync` per stack file (requires Compose v2).
7. **Wrapper**: POSIX `./compose.sh` (`make`/`just` not guaranteed on DSM): `networks` (idempotent creates), `decrypt` (sops → plaintext secrets.env), `up|down|pull|ps|logs|build [stack…]` (default all; order infra→monitoring→photos→media→sync, reversed for down), `gallery-dl` (profile run against media).
8. **Hardening folded in** (from `plans/security.md`, applied while every block is rewritten anyway): per-stack `x-hardened: &hardened` anchor with `security_opt: ["no-new-privileges:true"]` + `cap_drop: [ALL]`, merged into each service with minimal per-service `cap_add` exceptions (known: smartctl-exporter `SYS_RAWIO`; caddy `NET_BIND_SERVICE`; linuxserver s6 images (plex, qbittorrent) need `CHOWN/SETUID/SETGID/DAC_OVERRIDE`-class caps — determine the minimal set empirically per service, it's a start-and-observe exercise). Pin plex off `latest` to the current release tag. Point `immich.json`'s first ML URL and the remote-transcode `DESKTOP_IP` usage at the desktop's Tailscale MagicDNS name instead of the hardcoded LAN IP `192.168.1.40`.

## Implementation steps

1. **`git mv` service dirs** into their stack homes per the tree above (preserves history). Delete `secrets.env.example` files.
2. **Write the five `stacks/*/docker-compose.yml`** from the old file's service blocks with: top-level `name:`; cross-stack `depends_on: caddy` dropped (intra-stack deps kept: grafana→prometheus, immich-server→redis/database health-gated); relative paths now `./<svc>/…`; named-volume mounts replaced with the `$DOCKER_DATA` bind mounts (decision 2); only the four IP pins retained (decision 4); external network blocks (`name: nas_bridge` / `nas_macvlan`, macvlan in infra only, none in sync); `x-hardened` anchor applied (decision 8); plex pinned. No top-level `volumes:` blocks anywhere.
3. **`.env` symlinks** (`stacks/<name>/.env -> ../../.env`), committed.
4. **SOPS setup**: `.sops.yaml` with age recipients and a path rule for `**/secrets.enc.env`; encrypt freshly-created secrets for the five secretful services; update `.gitignore` (`secrets.env` stays ignored; `secrets.enc.env` tracked).
5. **`compose.sh`** per decision 7; delete root `docker-compose.yml`.
6. **Systemd templates** in `stacks/photos/immich/systemd/`: update `-f` paths and any `WorkingDirectory`-relative references.
7. **`.github/dependabot.yml`**: `docker` ecosystem → `/stacks/infra/caddy`, `/stacks/monitoring/alertmanager`, `/stacks/media/gallery-dl`; `docker-compose` ecosystem → the five `/stacks/<name>` dirs plus `/stacks/photos/immich` (remote-worker files; carries the existing `hashhar/*` and immich-postgres ignore rules).
8. **Docs**:
   - **README.md**: Usage → bootstrap section (install sops+age, place age key, `./compose.sh networks`, `./compose.sh decrypt`) + `./compose.sh` operations + per-stack `docker compose -f stacks/<name>/docker-compose.yml …` equivalents + new gallery-dl invocation. Environment Files section rewritten for the SOPS workflow. Special Instructions entries keep documenting each service's variables (names are now also visible in the encrypted files). Remote-worker section: new paths + MagicDNS. Macvlan/Tailscale appendices: networks are pre-created external; document `--ip-range`; subnets/DNS targets unchanged.
   - **CLAUDE.md**: overview (five stacks under `stacks/`, config dirs co-located), networking (external networks, ip-range carve-out, which three IPs are pinned and why), configuration patterns (SOPS secrets replace gitignored-only secrets.env; no named volumes — all state under `$DOCKER_DATA`), dependabot rules with new paths, service-category table → stack names.
   - `plans/security.md`: mark items 1–3 (no-new-privileges, cap_drop, plex pin) as folded into this restructure. `TODO.md`: Authelia entry → infra stack, no IP pin needed. `plans/llm.md`: path touch-ups.

## Cutover runbook (on the NAS + desktop, ~15–30 min downtime)

1. **Pre-checks**: Compose v2 present (`docker compose version`); `sops`/`age` binaries installed on NAS and desktop, age key distributed; branch pushed.
2. **Safety net**: `docker exec immich-database pg_dumpall -U postgres > /volume1/backups/immich-pre-restructure.sql`.
3. **Down old project** from the old checkout: `docker-compose --profile gallery-dl down`. Confirm old `nas_macvlan`/`nas_bridge` networks are gone (name collision otherwise) and the six `nas_*` volumes still exist.
4. **Migrate volume data → bind mounts** (containers stopped; paths under `/volume1/@docker/volumes/`):
   ```sh
   cp -a /volume1/@docker/volumes/nas_immich_postgres_data/_data/. "$DOCKER_DATA/immich/postgres/"
   cp -a /volume1/@docker/volumes/nas_caddy_data/_data/.          "$DOCKER_DATA/caddy/data/"
   cp -a /volume1/@docker/volumes/nas_prometheus_data/_data/.     "$DOCKER_DATA/prometheus/data/"
   cp -a /volume1/@docker/volumes/nas_grafana_data/_data/.        "$DOCKER_DATA/grafana/data/"
   # skip: nas_caddy_config (autosave, rebuildable), nas_immich_model_cache (cache, re-downloads)
   ```
   Then `chown -R` each to the uid:gid the container runs as (verify postgres/grafana internal uids). The Immich postgres copy is the one that matters — everything else is re-issuable/rebuildable history-vs-convenience.
5. **`git pull`** the restructure → `./compose.sh decrypt` → `./compose.sh networks`.
6. **`./compose.sh up`** (ordered infra-first; caddy/alertmanager/gallery-dl rebuild via `--build`).
7. **Desktop**: pull repo, place age key + decrypt, re-render + reinstall systemd units with the new paths, restart the remote-ml and remote-transcode stacks.
8. **After verification**: `docker volume rm nas_caddy_data nas_caddy_config nas_prometheus_data nas_grafana_data nas_immich_postgres_data nas_immich_model_cache`.
9. **Rollback** (any point before step 8): `./compose.sh down` → `docker network rm nas_macvlan nas_bridge` (old compose can't adopt label-less networks) → `git checkout` prior commit → recreate plaintext `secrets.env` files from SOPS (`sops -d`) or backups → `docker-compose up --build --detach`. The named volumes are untouched until step 8, so old-world state is intact.

## Verification

- `docker compose config` clean in all five stack dirs (symlinked `.env` interpolation, decrypted secrets present).
- `docker network inspect nas_bridge`: subnet `172.18.0.0/16`, ip-range `172.18.128.0/17`; caddy at `.3`, redis `.10`, database `.11`; dynamically-placed containers all ≥ `.128.0`.
- Every service starts under `no-new-privileges` + `cap_drop: ALL` with its minimal `cap_add` set (iterate per service; check logs for permission errors — this is the step most likely to need tuning).
- Immich: albums, people, edit history intact (proves the postgres copy); uploads work (proves chown); ML and transcode jobs land on the desktop worker via MagicDNS.
- HTTPS via Caddy on `*.nas.hashhar.com` and `*.nas.ts.hashhar.com` without cert re-issuance (proves caddy data copy); Prometheus `/targets` all up with history retained; Grafana admin login works.
- `docker compose -f stacks/media/docker-compose.yml --profile gallery-dl up --build gallery-dl` runs and exits.
- Fresh-clone drill (proves the greenfield goal): on any machine with docker + the age key, `git clone && ./compose.sh decrypt && docker compose -f stacks/monitoring/docker-compose.yml config` succeeds with no manually-created files.
- Next Dependabot run opens PRs against `stacks/*` files and the moved Dockerfile dirs.

## Appendix: options considered

- **Conservative in-place split** (previous version of this plan): keep service dirs at root with `../../` paths, pin volume `name: nas_*`, keep gitignored-only secrets — chosen against once a full redeploy was on the table, since every one of those was a workaround for live state.
- **include-based split** (one project, per-stack files via compose `include`): lowest migration risk, single `up -d`, but no per-stack lifecycle.
- **Mini-PC + NAS-as-NFS-storage**: deferred. NFSv4 (not CIFS) would be the transport, but Plex/*arr/Paperless SQLite state can't live on NFS, forcing local app-state + a new backup path + cross-machine UID/GID mapping — and the 4090 desktop already covers heavy compute better than any mini-PC. Revisit if the desktop should stay off while hardware transcode is still needed.
- **Single file with anchors/x- fields**: merely postpones the split; 15–20 services is the usual breaking point and the repo is at 15.
