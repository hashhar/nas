# Plan: Security Hardening

## Context

The NAS has TLS via Caddy, Tailscale for remote access, per-service user
isolation, and DSM firewall rules. This plan covers what is left, ordered by
how reachable each weakness actually is rather than by how bad it sounds.

Reviewed July 2026 against the running system (SSH to the NAS plus tailnet
probes from a peer). The March 2026 review is folded in; items still open are
marked as verified-open rather than assumed.

## Threat model

Assets, most valuable first:

1. `Personal/` — photos and documents. Confidentiality *and* integrity.
2. `Media/` — availability. Re-acquirable, but tediously.
3. NAS availability itself.

Adversaries, most realistic first:

1. **Untrusted content processed by an exposed service.** qBittorrent fetching
   torrents, Immich parsing uploaded images, gallery-dl scraping. This is the
   only path that starts with no credentials and no network position.
2. **A compromised device already on the tailnet.** The desktop worker holds
   the plaintext Immich DB password; any laptop or phone is a full tailnet
   peer.
3. **A shared tailnet node** (friends). Not yet real — gated on ACLs.

Explicitly out of scope, so items can be dropped deliberately rather than by
omission:

- **Internet-facing attack.** Behind CGNAT, no port forwarding, nothing
  published.
- **LAN/IoT lateral movement.** IoT lives on its own VLAN on the UDM Pro with
  no inter-VLAN routing.
- **Physical access and nation-state adversaries.**

## The single most valuable control is not in this plan

For "don't lose or leak my data", a working, verified, offsite backup outranks
every hardening item below. Ransomware and accidental deletion are far more
likely than a container escape. `--append-only` is set on the REST server, but
there is still no automated backup and no offsite copy — see
[plans/backups.md](backups.md). Do that first.

---

## Tier 0 — Do now (zero risk, no service disruption)

### 0.1 Delete the orphaned plaintext secrets

`./immich/secrets.env` and `./qbittorrent/secrets.env` sit at the repo root at
mode **0644**, left behind by `d96748b` (the `stacks/` restructure). The immich
one holds the live Postgres password. They are invisible to `git status`
because `.gitignore`'s unanchored `secrets.env` rule matches at any depth, and
they have no `secrets.enc.env` counterpart.

Rotation deliberately skipped: the exposure is local-filesystem only on a
single-user machine, and neither file ever reached git (verified with
`git log --all -S`).

### 0.2 Fix the Alertmanager entrypoint

`stacks/monitoring/alertmanager/entrypoint.sh` renders the Gmail app password
into `/tmp/alertmanager.yml` and never removes it. Verified still open — the
file is `-rw-r--r-- nobody nobody` in the running container.

- Add `umask 077` before writing, and `set -e` (currently absent, so a failed
  render still `exec`s Alertmanager against a stale config).
- Switch `sed` → `envsubst` with an explicit variable list. This reverts
  regression `0fe8bc3` and matches the documented standard in CLAUDE.md; `sed`
  also breaks on `|`, `&` or `\1` appearing in a secret.

```sh
envsubst '${SMTP_FROM},${SMTP_PASSWORD},${ALERT_EMAIL_TO}' \
    < /etc/alertmanager/alertmanager.yml.tpl > /tmp/alertmanager.yml
```

Do the same `sed` → `envsubst` switch in
`stacks/monitoring/prometheus/entrypoint.sh` for consistency — no secret is
involved there, only `${RESTIC_REST_SERVER_PORT}`.

Check whether `envsubst` exists in `prom/alertmanager`; if not, that service
already has a custom Dockerfile that can `COPY` it in (see §3.4 for the
pattern, which needs `libintl` alongside the binary).

### 0.3 Tighten `.gitignore`

It is currently two lines. Add `*.key`, `*.pem`, `*.htpasswd`, and a comment
marking the tracked `.env` as "paths, UIDs and ports only — never secrets".
Cheap guard against the next restructure orphaning another credential the way
§0.1 describes.

### 0.4 Add a second age recipient

`.sops.yaml` has exactly one recipient. Lose `~/.config/sops/age/keys.txt` and
every secret in the repo is unrecoverable; leak it and everything leaks. For a
homelab this asymmetry matters more than any capability flag below.

Generate an offline recovery key, store it in the password manager, add it as a
second recipient, and `sops updatekeys` all six encrypted files.

---

## Tier 1 — Tailnet exposure

The DSM firewall does **not** cover the `tailscale0` interface. Its rules are
per-LAN-interface, so they say nothing about tailnet traffic. Verified from a
tailnet peer against the NAS's tailnet IP: DSM `:5000`/`:5001`, SMB `:445`,
SSH `:22` and Syncthing `:8384` are all reachable. The README firewall table
reads as if it were the boundary; it is not.

Correct `TODO.md`'s claim that internal services are "already unreachable from
outside Docker" — measurably false for anything on the tailnet.

### 1.1 Authenticate Valkey (do this regardless of ACLs)

Verified from a tailnet peer: `172.18.0.10:6379` answers `PING` with `+PONG`
and serves `INFO`, with **no authentication**. It is reachable because the
bridge subnet is advertised so the desktop worker can dial Postgres and Redis
directly.

Set `requirepass` on `immich-redis` and the matching `REDIS_PASSWORD` for
`immich-server` and the remote transcode worker; add it to
`stacks/photos/immich/secrets.enc.env`.

Skipping this leaves any single compromised device of yours with a write
primitive into Immich's job queue and session store. ACLs alone do not cover
that case, which is why this is listed before them.

Postgres is fine by comparison — `pg_hba.conf` requires `scram-sha-256` for all
non-local hosts.

### 1.2 Write Tailscale ACLs — blocking prerequisite for sharing

Promoted from a `TODO.md` bullet. Without ACLs, a shared node inherits
everything the NAS advertises.

- `group:admin` → `172.18.0.0/16:*`
- sharees → `172.18.0.3:443` only (Caddy)

Live advertised routes are `0.0.0.0/0`, `::/0`, `172.18.0.0/16` and
`192.168.0.0/22`. The first two are the exit node, documented in the README.
The `/22` is live and useful (remote DSM and LAN access while travelling) but
undocumented — **document it, and note the consequence**: without ACLs a sharee
reaches DSM and SMB, not just Caddy.

### 1.3 Remove the qBittorrent subnet auth bypass

`stacks/media/qbittorrent/qBittorrent.conf.tpl` sets:

```ini
WebUI\AuthSubnetWhitelist=192.168.0.0/22
WebUI\AuthSubnetWhitelistEnabled=true
```

That grants **unauthenticated** WebUI access to the whole management subnet,
including the macvlan. It is unreachable today — qBittorrent lives in gluetun's
network namespace with no published ports, and Caddy dials from `172.18.0.3`,
which is outside the whitelist and therefore does authenticate — but it is a
footgun with no remaining purpose. Drop both lines.

Keep `WebUI\LocalHostAuth=false`. gluetun genuinely needs it to push the
NAT-PMP forwarded port over the WebUI API from `127.0.0.1`.

### 1.4 Decide on `--prometheus-no-auth`

`restic-rest-server` runs with `--prometheus --prometheus-no-auth`, so
repository metrics are served without the `.htpasswd` gate — on the bridge and,
via Caddy, at `restic-rest-server.nas.hashhar.com/metrics`. Either drop the
flag and give Prometheus credentials, or accept it in writing here.

### 1.5 Record the remote-access options

So the decision is not re-derived every time:

- **Plex** — share via plex.tv, independent of everything else. Behind CGNAT
  you lose direct connect and fall back to Plex Relay (bandwidth-capped; Plex
  Pass raises it). Worth testing before assuming friends need Tailscale at all.
- **Immich** — no built-in remote access; upstream recommends a TLS reverse
  proxy or a VPN and calls the VPN the safe default. Tailscale sharing is the
  fit.
- **Everything else** — Tailscale node sharing plus §1.2's ACLs. The cost is
  friction: each person installs Tailscale, accepts an invite, and needs
  MagicDNS working.
- **Fallback if that friction proves too high** — a cheap VPS running the
  public reverse proxy with a WireGuard tunnel back to the NAS. Real public
  ingress without Cloudflare Tunnel's §2.8 TOS problem on media.

---

## Tier 2 — Data isolation

**Problem.** `service_rw` is one shared group (GID 65539) with read/write over
the whole `data` share. `qbittorrent`, `arr`, `ytdl`, `syncthing` and `immich`
are all members, so every one of them can read and write all the others' data.
A breakout in the most exposed container — qBittorrent, which fetches untrusted
torrents — reaches the photo library and `Personal/`. The per-service UIDs give
the appearance of isolation; the shared group dissolves it.

Ownership is also set once via `chown -R` with no inheritance, so every file an
app or an SMB client creates drifts from the baseline.

### 2.1 Split by data domain, not by service

An earlier draft of this plan claimed Immich and Syncthing owned disjoint trees
and needed no shared group. **That is wrong**: `Personal/Pictures/Synced` is
bind-mounted read-write by syncthing, immich-server *and* gallery-dl.

Cut groups by data domain instead, sized for the services likely to arrive
later (a restic client backing up everything, *arr apps, Navidrome/beets/picard,
an ebooks setup, paperless, Monica):

| Group | Owns | Members |
|-------|------|---------|
| `media_rw` | `Media`, `Staging` | arr, qbittorrent, ytdl, beets/picard |
| `service_ro` (existing) | — | plex, navidrome — read via `:ro` mounts |
| `photos_rw` | `Personal/Pictures/*` | syncthing, immich, gallery-dl |
| `docs_rw` | `Personal/Documents/*` | paperless, ebooks |
| *(none)* | appdata only | Monica, Grafana — no data-share membership |
| `backup` | `/volume1/backups/restic` | restic |

Domain-scoped, so a new service joins an existing group instead of minting one.
The win is unchanged: qBittorrent gets `media_rw` and cannot touch `Personal/`.

**For a restic client that backs up everything**, do not try to express
read-but-not-write in the group bits. Make the backup user a *secondary* member
of each domain group and mount every source tree `:ro` in the backup container.
The mount is the enforcement and is far easier to reason about.

Related gap to check while doing this: `caddy`, `grafana` and `prometheus`
appdata directories are `root:root drwxr-xr-x`, so any `0640` file inside them
is **not** readable by `backup` today. Verify what restic can actually read
before trusting the backup.

**Files:** README `#### Groups`/`#### Users` tables; `.env` GIDs; each stack's
`docker-compose.yml` (`PGID` / `user:`); the README ownership `chown -R` block.

### 2.2 Make ownership self-perpetuating

Use `chmod g+s`, not ACLs. `setfacl` and `getfacl` **do not exist on DSM** —
only `/usr/syno/bin/synoacltool`, with different syntax — so the previous
draft's `setfacl` recipe was unexecutable.

Tested on scratch directories under `/volume1/data/Scratch` and
`/volume1/data/Media` (the latter carries a Synology ACL), then removed:

| Behaviour | Result |
|-----------|--------|
| Fresh `mkdir` under an ACL-bearing dir | Inherits the Synology ACL, POSIX mode `0000` (`d---------+`) |
| `chmod 2770` on it | **Strips the ACL**, converts to pure POSIX; `synoacltool -get` reports `It's Linux mode` |
| setgid after conversion | Works — `drwxrws---` |
| Group inheritance | Works — files created by a process with primary GID 0 landed as `root:service_rw` |
| umask | Fully honoured: `077` → `-rw-------`, `022` → `-rw-r--r--`, `002` → `-rw-rw-r--` |

So the approach works, and Synology does *not* override umask.

**State the consequence plainly:** `chmod g+s` converts those trees off
Synology ACLs and onto pure POSIX. That is arguably a simplification — one
permission system instead of two — but DSM's share-permission UI and Windows
ACL editing over SMB no longer govern those paths.

Two checks remain before any bulk `chown`, neither testable from the CLI:

1. Re-apply share permissions in DSM Control Panel on a scratch directory and
   re-check — this is the path that may convert Linux mode back to Synology ACL
   and undo everything.
2. Write into a setgid directory over SMB as your human user and confirm the
   group lands correctly.

### 2.3 Pin a consistent umask

The group scheme assumes files stay group-readable; a container writing `0700`
breaks plex and restic reads invisibly despite correct group ownership.

`UMASK` support is per-image, not universal. linuxserver images (plex,
qbittorrent) honour `UMASK`. `syncthing/syncthing` and the Immich Node images
do **not** read it — find the real mechanism for each, or accept that setgid
alone carries them. Per §2.2 setgid fixes the *group* regardless of the
writer's umask, so this only affects the *mode*.

### 2.4 Reconcile the SMB `users` group

SMB writes land in group `users`. The drift is real and reproducible:
`Personal/Pictures/immich/upload/thumbs/8de00597-…` is `radon:users` at mode
`d---------`, which Immich cannot read.

Set a force-group on that share in Synology's SMB advanced config so those
writes land in the right group directly. Note that setgid fixes the group but
not the mode, so the SMB umask is a separate lever.

---

## Tier 3 — Container hardening

Defence in depth. Every item here only pays off *after* an app-level RCE, which
is why it sits below Tier 1 and Tier 2 rather than at the top.

Roll out per-stack via an `x-hardened: &hardened` anchor merged into each
service, one stack at a time so any breakage is attributable. No service uses
any of these today, and no such anchor exists yet.

### 3.1 Order by exposure

Not alphabetically, and not by ease:

1. **qbittorrent** — untrusted torrents.
2. **immich-server** — untrusted uploads.
3. **caddy** — the front door, and currently runs as **uid 0** with the full
   default capability set.
4. Everything else.
5. **monitoring last** — it processes nothing hostile.

### 3.2 `no-new-privileges` and `cap_drop`

```yaml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

with minimal per-service `cap_add` determined empirically: smartctl-exporter
needs `SYS_RAWIO`, caddy needs `NET_BIND_SERVICE`, gluetun needs `NET_ADMIN`,
and the linuxserver s6 images need a `CHOWN`/`SETUID`/`SETGID`/`DAC_OVERRIDE`
class set.

Note `smartctl-exporter` is `user: "root"` **and** `cap_add: [SYS_RAWIO]` with
no drop — the root is as much of the problem as the capability. `gluetun` adds
`NET_ADMIN` on top of the full default set for the same reason.

### 3.3 `read_only: true` — expect to abandon it for most services

The s6 linuxserver images and Immich write to their root filesystem at startup.
Try it, and where it fails keep `no-new-privileges` + `cap_drop: ALL`, which
cost nothing. **Record which services were tried and failed**, so this is not
re-litigated at the next review.

### 3.4 Remove the boot-time `apk add` from qBittorrent

`stacks/media/qbittorrent/99-overwrite-config` runs `apk add --no-cache gettext`
as root on every container start.

This is a **reliability and hardening-enablement** item, not a security
finding. `apk` verifies package signatures against keys baked into the image,
so a compromised mirror does not trivially inject code, and moving the fetch to
a build stage does not change that. The genuine costs are:

1. A boot-time network dependency that now routes **through the VPN** — if the
   tunnel is down at container start, `apk add` fails and `set -e` aborts init
   with the config unrendered.
2. It requires root plus a writable rootfs at every init, which is exactly what
   blocks §3.3.
3. The gettext version is unpinned on every boot.

Fixed by a multi-stage Dockerfile that copies the binary in. Two details worth
keeping: `envsubst` is dynamically linked against `libintl.so.8`, so copying
the binary alone produces an image that builds and then fails at init; and the
owning package is `gettext-envsubst`, not the full `gettext`.

Remaining after this: the same script fetches tracker lists from
`newtrackon.com` and `raw.githubusercontent.com` on every boot. Low impact — it
is a list of URLs and failure is tolerated — but it is the last boot-time
network dependency.

Also note the script's timestamped `.bak` files accumulate forever in
`/config/qBittorrent/`, each retaining the WebUI password hash.

---

## Tier 4 — Deferred

### 4.1 Authelia / forward auth — gated on inviting friends

Each service manages its own authentication, and Prometheus has none at all.
The fix is Authelia behind Caddy's `forward_auth` for the admin services
(Prometheus, Grafana, qBittorrent, Syncthing, restic), leaving Plex and Immich
on their own auth because forward auth breaks their client apps.

Downstream of §1.2 and only worth the complexity if node sharing actually
happens — for a single-user tailnet, ACLs achieve most of the same isolation
for far less. See `TODO.md` for the full breakdown.

### 4.2 Rate limiting on Caddy — low priority

Add the `caddy-ratelimit` plugin and rate-limit auth endpoints. With no
internet ingress there is no brute-force surface, so this only becomes relevant
if something is ever exposed publicly.

### 4.3 Conflict to fix when `plans/llm.md` executes

That plan adds an `open-webui` user to the shared `service_rw` group while
stating it needs no shared-data access — directly contrary to Tier 2. Give it
no data-share membership.

---

## Deliberate exceptions

Recorded so they are not re-raised at every review.

| Item | Why it stays |
|------|--------------|
| `plex` on `:latest` | The linuxserver image updates Plex internally and the version moves too fast to track; pinning is pure toil. |
| Unpinned `pip install gallery-dl` | Dependabot's `docker` ecosystem only parses `FROM` lines, so it would never bump this. Pinning buys manual work, not safety. |
| Unpinned xcaddy `caddy-dns/cloudflare` | Same reason. |
| Tailscale key expiry disabled on the NAS | Deliberate: it prevents being locked out while travelling. Every other device expires normally. |
| `WebUI\LocalHostAuth=false` | gluetun shares the network namespace and needs it to push the NAT-PMP port. |
| `--append-only` without automated backups | Tracked in [plans/backups.md](backups.md), not here. |

---

## Verification

**Tier 0**

1. No `secrets.env` outside `stacks/*/*/`; the remaining six are mode 0600.
2. `docker exec alertmanager ls -l /tmp/alertmanager.yml` shows `0600`, and
   alerts still deliver to email end to end.
3. `sops decrypt` succeeds with the recovery key alone, on a machine without
   the primary key.

**Tier 1**

4. From a tailnet peer, `redis-cli -h 172.18.0.10 PING` fails without
   credentials and succeeds with them; Immich stays healthy and the remote
   transcode worker still picks up jobs.
5. From a device in the sharee group, Caddy on `172.18.0.3:443` is reachable
   and direct backend IPs, DSM and SMB are not.
6. qBittorrent's WebUI prompts for credentials from a `192.168.x` address.

**Tier 2**

7. `getfacl` is not used anywhere — it does not exist on DSM.
8. On a scratch directory: `chmod 2770`, write from a container, confirm group
   inheritance; then re-apply DSM share permissions and confirm the directory
   is still in Linux mode.
9. As qbittorrent, writes under `Personal/Pictures/` are denied.
10. A file written over SMB into `Personal/Pictures/immich` lands in the right
    group and is readable by Immich.
11. New files created by each service are group-readable.

**Tier 3**

12. `docker inspect --format '{{.HostConfig.SecurityOpt}} {{.HostConfig.CapDrop}}' <container>`
    reflects the anchor.
13. Each hardened stack comes up healthy, one stack at a time.
14. qBittorrent starts with no network access at init and renders its config
    correctly; the VPN killswitch still holds
    (`docker exec qbittorrent curl -s https://ipinfo.io/json` shows a Proton
    exit, not the home IP).
