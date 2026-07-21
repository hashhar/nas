# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NAS infrastructure-as-code repository for a Synology DS1821+ running Docker containers via docker-compose. Services are split into five independent per-stack Compose projects under `stacks/` — `infra`, `monitoring`, `media`, `photos`, `sync` — each with its own `docker-compose.yml` (with a top-level `name:`) and co-located service config subdirectories (Dockerfiles, configs, entrypoints, encrypted secrets). Each stack has a `.env` symlink back to the single root `.env`. There is no root `docker-compose.yml`.

## Commands

`./compose.sh` at the repo root is the operator wrapper over the per-stack
projects:

- `./compose.sh networks` — idempotently create the shared external networks (`nas_macvlan`, `nas_bridge`)
- `./compose.sh decrypt` — render each `stacks/*/*/secrets.enc.env` to a gitignored plaintext `secrets.env` sibling via SOPS
- `./compose.sh up|down|pull|ps|logs|build [stack…]` — run the action against the given stacks, or all of them in dependency order (`infra monitoring photos media sync`, reversed for `down`) when none are named
- `./compose.sh gallery-dl` — one-shot profile run in the media stack

Each maps to `docker compose -f stacks/<stack>/docker-compose.yml …`. On the NAS
the docker actions need root (`sudo ./compose.sh …`). See the [Usage section in
README.md](README.md#usage) for the full workflow. There are no tests or linters
— this is a declarative infrastructure repo.

## Architecture

### Networking (dual-network design)

Both Docker networks are **pre-created as external networks** (they outlive any single stack, since every stack attaches to them) via `sudo ./compose.sh networks`; each stack's compose file references them with `external: true` as `nas_macvlan` / `nas_bridge`. Caddy is the only container on both, bridging external access to internal services:

- **macvlan** (`nas_macvlan`, 192.168.2.0/24, parent: eth0): Caddy at 192.168.2.3 — bypasses Synology's built-in Nginx to get clean ports 80/443 with wildcard subdomain support
- **bridge** (`nas_bridge`, 172.18.0.0/16): All containers communicate here (cross-stack too — container names resolve on the shared user-defined network regardless of Compose project); Caddy at 172.18.0.3 reverse-proxies to services by container name
- **host network**: Syncthing (local discovery requires it) and gallery-dl

The bridge is created with `--ip-range 172.18.128.0/17`, confining Docker's dynamic allocation to the upper half so it can never collide with a static pin. **Only four load-bearing addresses are pinned**: caddy `192.168.2.3` + `172.18.0.3` (Tailscale DNS target, `IMMICH_TRUSTED_PROXIES`), immich-redis `172.18.0.10` and immich-database `172.18.0.11` (dialed directly by the desktop workers over Tailscale, where container DNS doesn't exist). Everything else addresses peers by container name and takes a dynamic IP `≥ 172.18.128.0` — new services need no IP bookkeeping.

Tailscale advertises the bridge subnet (172.18.0.0/16) for remote access. DNS records (*.nas.ts.hashhar.com) point to Caddy's bridge IP.

See the [Docker macvlan Networking appendix](README.md#docker-macvlan-networking) and [Tailscale Routing](README.md#tailscale-routing) in README for setup commands and rationale.

### Configuration patterns

- **`.env`**: Shared variables for docker-compose interpolation (paths, UIDs/GIDs, ports). Not injected into containers. Single root file; each stack symlinks `stacks/<stack>/.env -> ../../.env`.
- **`stacks/<stack>/<service>/secrets.enc.env`**: Tracked, SOPS+age-encrypted source of truth for a service's secrets, in dotenv mode so variable *names* stay readable in git while *values* are ciphertext. Encryption is governed by `.sops.yaml` (a single `path_regex` creation rule for `**/secrets.enc.env` with one age recipient). Any service that requires secrets has one. When adding one, document the required variables and their purpose in `README.md` under a `### <ServiceName>` entry in the Special Instructions section. See [Environment Files in README](README.md#environment-files) for full operational guidance.
- **`stacks/<stack>/<service>/secrets.env`**: The gitignored plaintext that `env_file:` actually points at, produced by `./compose.sh decrypt` (renders every `secrets.enc.env` to a `secrets.env` sibling, `chmod 600`). Never committed; there are **no** `secrets.env.example` files — the variable names in the tracked `.enc` file are the self-documenting template.
- **Build-time templating** (being phased out): Dockerfiles use multi-stage builds — Alpine+gettext `envsubst` or `sed` to bake config templates with build args, then copy into final image.
- **Runtime templating** (preferred): Config templates (`.tpl` files) are mounted into containers and rendered at startup via `envsubst`. See "Configuration refactoring" below.

### Configuration refactoring

#### Goals

1. **Use upstream images where possible** — eliminate custom Dockerfiles that exist only to bake config into the image
2. **Version-controlled configuration** — all config templates live in the repo
3. **No plaintext secrets in the repo** — credentials live only in SOPS+age-encrypted `secrets.enc.env` files (tracked) and their gitignored decrypted `secrets.env` siblings, injected via environment variables
4. **Single source of truth** — changing a value must not require edits in multiple places; `.env` and each service's `secrets.enc.env` are the only places values are defined
5. **Decouple runtime-modified config from repo** — apps that modify their own config at runtime (e.g. qBittorrent) must not write back to repo-tracked files; templates are rendered to a separate location on each start

#### Approach: Runtime envsubst

Render config templates at container startup using `envsubst`. Variables come from the container environment (set via `environment:` and `env_file:` in docker-compose.yml, sourced from `.env` and `secrets.env`).

- **linuxserver-based images** (qBittorrent): Use `/custom-cont-init.d/` scripts that run during the s6 init sequence
- **Other images** (Prometheus, Alertmanager): Use an entrypoint wrapper script that runs `envsubst`, writes the rendered config, then `exec`s the original entrypoint
- **Template naming**: Use `.tpl` extension to signal "this file has placeholders"

#### Alternatives considered and rejected

| Approach | Why rejected |
|----------|-------------|
| **Build-time envsubst** (current) | Bakes rendered config including secrets into image layers; requires rebuild for any config change |
| **Makefile pre-rendering** | Adds a manual `make render` step; forgetting it deploys stale config — directly contradicts the single-source-of-truth goal |
| **Multi-stage build copying only the envsubst binary** | Still a custom image; acceptable as a fallback if runtime package install isn't possible, but not preferred |

#### Risks

1. **Network dependency** — `apk add gettext` at runtime requires Alpine repos to be reachable. For a NAS that should survive network outages, consider falling back to the multi-stage approach (copy `envsubst` binary into a thin custom image layer) for critical services if this becomes an issue.
2. **envsubst variable scope** — Without an explicit variable list, `envsubst` replaces ALL `$VAR` patterns in the file. Always use explicit variable lists: `envsubst '${VAR1},${VAR2}' < template > output`.
3. **Credential handling with overwrite-on-restart** — For apps that allow credential changes via UI (e.g. qBittorrent), the startup script overwrites config on every restart. Credentials must be envsubst variables sourced from `secrets.env`, not hardcoded in templates, or they'll be wiped on restart.

#### When a custom Dockerfile is necessary

A custom Dockerfile is justified when:
- The upstream image needs a plugin or binary that requires a custom build (e.g. Caddy with xcaddy + Cloudflare DNS plugin)
- No upstream image exists at all (e.g. gallery-dl)

A custom Dockerfile is **not** justified when its only purpose is to bake config or install a single package (`gettext`, `su-exec`, etc.) that could be handled at runtime.

When in doubt, prefer the runtime envsubst approach and drop the Dockerfile. If the base image truly cannot run `apk add` at startup (no network, read-only fs), the fallback is a multi-stage Dockerfile that copies only the `envsubst` binary — no config or secrets are baked in.

### Service categories

Each row is one Compose project (its top-level `name:`), living at
`stacks/<stack>/docker-compose.yml`:

| Stack | Services |
|-------|----------|
| `infra` | caddy (reverse proxy + TLS via Cloudflare DNS challenge), restic-rest-server (backups) |
| `monitoring` | prometheus, grafana, alertmanager, smartctl-exporter (8 SATA devices), node-exporter |
| `media` | plex (read-only media), qbittorrent (downloads to Staging), gallery-dl (profile-gated) |
| `photos` | immich-server, immich-machine-learning, immich-redis, immich-database |
| `sync` | syncthing (host network) |

### Storage layout

All containers mount under two roots to avoid cross-filesystem copies:
- `DOCKER_DATA=/volume1/docker/appdata` — container configs and state
- `DATA_ROOT=/volume1/data` — user data (Media, Personal, Staging, etc.)

Plex mounts Media as read-only. qBittorrent writes to Staging. The *arr apps (not yet containerized) move files from Staging to Media.

See [Directory Setup in README](README.md#directory-setup) for the full tree.

**Volume policy (bind mount vs named volume).** A service's persistent state gets a **bind mount under `$DOCKER_DATA`** by default — that path is what restic sweeps, and restore is uniform (drop the files back, `chown`, `up`). Use a **named volume** *only* when the data is one of: regenerated on boot (nothing to restore), a large re-downloadable cache, or backed up by a separate logical dump rather than a file copy. That last rule keeps hot/torn-prone or bulky-regenerable data out of restic's `$DOCKER_DATA` sweep with no exclude rules, since named volumes live under Docker's own volume dir. Current split:

- **Bind mounts** (`$DOCKER_DATA/…`, restic-backed): caddy `/data` (TLS certs), prometheus `/prometheus` (crash-tolerant TSDB), grafana `/var/lib/grafana` (small SQLite).
- **Named volumes** (declared per-stack, name-stable via the stack's `name:`): `infra_caddy_config` (autosave, rewritten from the Caddyfile every boot), `photos_immich_model_cache` (GBs of re-downloadable weights), `photos_immich_postgres_data` (the live DB — backed up by Immich's scheduled logical `pg_dumpall` to `$DATA_ROOT/Personal/Pictures/immich/upload/backups`, which restic already covers under `$DATA_ROOT`, **not** by a file copy of the data dir).

### User/group isolation

Each service runs as a dedicated Synology user with a specific UID/GID (defined in `.env`). Groups control share-level access: `service_ro` for read-only (plex), `service_rw` for read-write (qbittorrent, syncthing, immich), `backup` for restic.

See [User & Group in README](README.md#user--group) for the full permission tables.

### Dependabot

`.github/dependabot.yml` tracks image version updates weekly via two ecosystems:

- **`docker` ecosystem**: one entry per service directory that contains a custom Dockerfile — currently `/stacks/infra/caddy`, `/stacks/monitoring/alertmanager`, `/stacks/media/gallery-dl`; watches for base image bumps
- **`docker-compose` ecosystem**: one entry per directory containing a `docker-compose.yml` — the five stack dirs (`/stacks/infra`, `/stacks/monitoring`, `/stacks/media`, `/stacks/photos`, `/stacks/sync`) plus `/stacks/photos/immich` for the remote-worker overlay files; ignores `hashhar/*` images (built locally, not from a registry) and any images pinned to a specific custom build

**Rules:**
- Adding a custom Dockerfile → add its `stacks/<stack>/<service>` directory to the `docker` ecosystem
- Removing a custom Dockerfile → remove that directory from the `docker` ecosystem
- Adding a new stack (a new `stacks/<stack>/docker-compose.yml`) → add that directory to the `docker-compose` ecosystem; likewise any new subdirectory that holds its own compose files
- Pinning an image to a custom/non-standard tag → add it to the `ignore` list with a comment explaining why

### Keeping documentation in sync

`README.md` is the setup manual for this repo — it contains the step-by-step instructions a human needs to get everything running from scratch. Keep it accurate.

| Change | What to update |
|--------|---------------|
| Add a service that needs secrets | Create `stacks/<stack>/<service>/secrets.enc.env` (populate a plaintext `secrets.env`, then `sops encrypt --filename-override … `); add a `### <ServiceName>` entry under "Special Instructions" in README documenting each required variable, its purpose, and how to generate/obtain it. No `secrets.env.example` — the encrypted file's variable names are the template |
| Remove a service that needs secrets | Delete its `secrets.enc.env` and remove its Special Instructions entry from README |
| Add a new Synology user for a service | Add the user to the Users table in README |
| Add a custom Dockerfile | Add its `stacks/<stack>/<service>` directory to the `docker` ecosystem in `dependabot.yml` |
| Remove a custom Dockerfile | Remove that directory from the `docker` ecosystem in `dependabot.yml` |
| Add a new stack or a new directory with its own compose files | Add the directory to the `docker-compose` ecosystem in `dependabot.yml` |
| Pin an upstream image to a non-standard tag | Add to `ignore` list in `dependabot.yml` with a comment explaining why |
| Change a port, path, or significant config default | Check whether README references it and update accordingly |

### Monitoring

Prometheus scrapes: itself, caddy (:80/metrics), restic-rest-server, immich (API :8081, microservices :8082), smartctl-exporter, node-exporter. Alert rules in `stacks/monitoring/prometheus/alerts.yml` cover SMART disk health, RAID degradation, filesystem space, and service availability. Alertmanager routes alerts to email via Gmail SMTP.
