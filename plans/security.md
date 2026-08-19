# Plan: Security Hardening

Reviewed **2026-08-19** against the running system — SSH to the NAS, probes from
the tailnet peer `xenon-wsl`, read-only inspection of every container. Every claim
here was measured; anything that could not be measured without changing state is
marked *(unverified)*.

This is a homelab with **one user**. Nobody else has an account, a tailnet share or
an Immich login today, so items about friends and family are prospective.

Ordering is by **reachability given the measured state** — not by how bad a
category sounds, and not by ease.

---

## 0. Corrections to the record

No actions here. These are the facts every later section refers back to, written
down once so they stop being re-derived — and so the next reviewer does not write
another `setfacl` recipe for a tool DSM does not have.

### 0.1 There is no `tailscale0`, and the firewall is source-matched

The previous plan said the DSM firewall "does not cover the `tailscale0` interface.
Its rules are per-LAN-interface." Both clauses are false.

`ip link show tailscale0` → `Device "tailscale0" does not exist`. tailscaled runs
`--tun=userspace-networking` (`NetfilterMode: 0`). Of the 30 `INPUT_FIREWALL`
rules, 28 are UI-created and matched on **source address** (`in *`), not
interface; rule 1 is `-i lo -j ACCEPT` (interface-matched) and rule 2 is the
`RELATED,ESTABLISHED` state accept.

The cause is a boot-order accident, not a platform limit.
`/var/packages/Tailscale/scripts/start-stop-status`:

```sh
if [ "${SYNOPKG_DSM_VERSION_MAJOR}" -eq "7" -a ! -e "/dev/net/tun" ]; then
    SERVICE_COMMAND="${SERVICE_COMMAND} --tun=userspace-networking"
fi
```

```
2026-08-10T02:34:29  tailscaled starts … --tun=userspace-networking
2026-08-10 02:34:37  /dev/net/tun created   ← the "Load tun module" task, added for gluetun
```

Eight seconds. `ensure_tun_created()` returns immediately on DSM 7, so the package
never creates the node itself. See §2.1.

### 0.2 Every tailnet peer looks like the NAS itself

| Path from a tailnet peer | What the receiver sees |
|---|---|
| HTTPS to Caddy `172.18.0.3:443` | Caddy log: `remote_ip: 172.18.128.0` — the bridge **gateway**, i.e. the host |
| `ssh radon@100.103.76.141` | `SSH_CONNECTION=127.0.0.1 55636 127.0.0.1 22` |
| `ssh radon@192.168.1.3` via the `/22` route | `SSH_CONNECTION=192.168.1.3 … 192.168.1.3 22` |

Consequences, all downstream of one cause:

- The DSM firewall never evaluates tailnet traffic — rule 1 is `ACCEPT all -- lo`,
  and `/22`-route traffic arrives already inside the allowed range.
- **DSM autoblock is blind for the same reason.** It is on (10 attempts / 5 min,
  `expire_day=0`) but counts against `127.0.0.1`, or against the NAS's own eth0.
- Caddy, Immich and any future fail2ban cannot tell your five devices apart. Immich
  login rate limiting is already one bucket for everyone.
- **No `remote_ip` policy is expressible** anywhere on this box. Anything in §5
  that wants to distinguish a VPS peer from your laptop is unbuildable until §2.1.

### 0.3 `/volume1/data` is governed by inherited Synology ACLs, not POSIX group bits

This invalidates the previous plan's entire Tier 2 mechanism.

```
$ synoacltool -get /volume1/data
 [2] group:service_ro:allow:r-x---a-R-c--:fd-- (level:0)
 [3] group:backup:allow:r-x---a-R-c--:fd-- (level:0)
 [4] group:home:allow:rwxpdDaARWc--:fd-- (level:0)
 [5] group:service_rw:allow:rwxpdDaARWc--:fd-- (level:0)
```

`fd--` = file+dir inherit, from the share root. Measured as the `qbittorrent` user:

```
RWX  /volume1/data/Personal          RWX  /volume1/data/bup
RWX  /volume1/data/Personal/Pictures/immich/upload    RWX  /volume1/data/macos
```

— and it read the first bytes of a live Immich DB dump. `Personal`, `bup` and
`macos` are POSIX `d---------`; they **look** locked and are not. `chown -R` to a
new group changes nothing while the share-root ACE stands.

The isolation that *does* work is the **bind-mount scoping**, and it is already
correct: `ls /volume1/data/` inside the qbittorrent container returns exactly
`Staging`. Plex mounts `Media:ro`. Immich mounts only its two trees.

### 0.4 `*.nas.hashhar.com` is unreachable from every device you own

Verified from `xenon-wsl`, which is on the LAN (`192.168.1.40/22`, so `192.168.2.3`
is directly connected) *and* on the tailnet:

```
$ ip route get 192.168.2.3
192.168.2.3 dev tailscale0 table 52 src 100.115.114.28
$ curl --resolve grafana.nas.hashhar.com:443:192.168.2.3 https://grafana.nas.hashhar.com/api/health
000   (connect failed)          # vs. the .ts name via 172.18.0.3 → 200
```

`ip rule` priority 5270 (`lookup 52`) beats 32766 (`lookup main`), and table 52
carries `192.168.0.0/22 dev tailscale0`. The advertised `/22` shadows the
directly-connected LAN route, hairpins through the subnet router, and the subnet
router cannot reach its own macvlan child. So the LAN name set is dead on any
device running `--accept-routes` — which is all of them. **"LAN" is not a
distinguishable path anywhere on this network**, which independently kills any
source-IP LAN/remote split.

### 0.5 Two internet ingress paths exist despite CGNAT

- `GET /v1/portforward` → `{"port":60739}`. A live ProtonVPN NAT-PMP mapping
  forwarding into `qbittorrent-nox`.
- Syncthing runs `globalAnnounceEnabled=true` + `relaysEnabled=true`; public relays
  bridge arbitrary internet hosts to its BEP listener.

CGNAT blocks inbound to the ISP address. Neither of these needs one. QuickConnect
and DDNS are genuinely not configured.

### 0.6 SOPS protects the git mirror, not the box

The age private key is at `/var/services/homes/radon/.config/sops/age/keys.txt`
(`0600 radon:users`) with `sops` and `age` on `PATH`. Host root is a full secret
compromise. The repo `hashhar/nas` is **public**, and public DNS answers
`nas.hashhar.com → 192.168.2.3`, `immich.nas.ts.hashhar.com → 172.18.0.3` — RFC1918,
so no ingress, but zero recon cost.

---

## Threat model

### Assets

| # | Asset | Property | Why here |
|---|---|---|---|
| 1 | `Personal/` — photos, documents, OneDrive mirror | **A > C > I** | Irreplaceable, and availability outranks confidentiality because nothing defends it. It is **not in restic** (which holds only `ludusavi`, last index write 2026-07-20). Hourly snapshots are on the same volume and deletable by root. Immich's own dumps land *inside* the tree Immich writes — inside the blast radius. |
| 2 | The age key and the secret set it unlocks | **C + A** | One key on the box decrypts the Cloudflare token, the ProtonVPN key, the Immich DB password, Grafana's admin password, the Gmail app password and qBittorrent's credentials, across all history. `.sops.yaml` has **one recipient** — losing that file makes every `secrets.enc.env` permanently unreadable. |
| 3 | Cloudflare API token + both wildcard TLS keys | **C** | The only credential whose blast radius leaves the house: DNS-edit on `hashhar.com` and issuance for anything under it. Held by `caddy`, which runs as **root with the full default capability set**. |
| 4 | Tailnet membership | **I** of the boundary | Not a transport — the *sole* authentication boundary for ~20 ports that authenticate nothing, shared flat across five devices with no ACLs, no tags and `KeyExpiry: None`. |
| 5 | NAS availability and the snapshot chain | **A** | RAID + hourly snapshots handle disk failure, not root-level deletion, and there is nothing offsite. |
| 6 | `Media/` and `Games/` | **A only** | Corrected 2026-08-19: only `Games/Steam` is genuinely re-acquirable — the torrent categories, the Sports recordings, the YouTube archive and the non-Steam `Games` trees (offline installers, ROMs) carry real reacquisition cost or none at all, making this a backup candidate (§3.4, backups.md), not an accepted loss. `Media/` is also the reason the most exposed process on the box exists. |
| 7 | Undeclared credential and data residue | **C** | **73 `*.bak.*`** in qBittorrent's config, each `qBittorrent.conf.bak.*` holding a PBKDF2 WebUI hash at 0644. **14 Immich DB dumps** under `Personal/Pictures/immich/upload/backups/`, readable by any `service_rw` member — measured, not theoretical (§0.3). |

Two things at `/volume1` are **not** assets — you confirmed you would not mind
losing them, so the action is deletion, not defence:
`backups/immich-pre-restructure.sql` (1.9 GB plaintext Immich cluster dump) and
`data/macos/hashhar.tar.gz` (54 GB). `backups/clonezilla` and `data/bup/` you *do*
care about and neither is in restic — fold them into [plans/backups.md](backups.md).

### Adversaries

| # | Actor | Entry point | Likelihood |
|---|---|---|---|
| 1 | **A compromised device of yours** | The tailnet — no ACLs, no expiry, no tags | **Highest.** The desktop alone holds an SSH key to the NAS, a repo checkout, the Immich DB password in plaintext, **the photo library bind-mounted read-write** (`docker-compose.remote-transcode.yml`), and a second root-run ML endpoint published on `0.0.0.0:3003` that `immich.json` dials over plaintext HTTP. |
| 2 | **Automated internet background noise** | Port 60739 and the Syncthing relay path (§0.5) | High volume, low per-attempt success — unauthenticated if it lands. |
| 3 | **Malicious content you fetch yourself** | Torrents, gallery-dl, photos uploaded to Immich | High; bypasses every network control by design. `immich-machine-learning` runs as **root**, unauthenticated on `:3003`, parsing arbitrary images. |
| 4 | **Compromised upstream image** | `pull` + restart, Dependabot weekly | Moderate. 16 containers, several as root, **none** with `cap_drop`/`no-new-privileges`/`read_only`. |
| 5 | **Ransomware on the Windows desktop** | SMB | Moderate. Hourly snapshots are the working defence; restic is not, because it holds only game saves. |
| 6 | **Friends and family** | Their own accounts, once they exist | Not real yet. The realistic version is that one of *their* devices becomes #1. |

### Attack paths open today

**P1 — Compromised device → tailnet → root.** The tailnet is flat, so
`ssh radon@100.103.76.141` connects. `PasswordAuthentication yes`, **no 2FA is
actually enrolled** (`otp_enforce_option=admin` is set but no OTP secret exists
under `/usr/syno/etc/preference/*/`), and `radon` has `NOPASSWD: ALL`. Brute force
is unimpeded — autoblock is counting against `127.0.0.1` (§0.2). Ends at host root
→ the age key → every secret → the domain.

**P2 — Tailscale web client on `:5252`.** `RunWebClient: true`. `GET /api/data` →
**200 unauthenticated**; `/api/auth` reports `serverMode: manage` with
`viewerIdentity.capabilities: {"*": true}` for any peer you own, gated only by an
`authorized: false` browser handshake. Write endpoints **not tested** *(would change
state)*. If a write lands: rewrite advertised routes, enable Tailscale SSH, or log
the node out — a one-request availability kill.

**P3 — Internet → port 60739 → qBittorrent → the host.** Pre-auth surface is the
BitTorrent wire protocol and metadata parsing. gluetun's kill switch blocks the LAN
and the router — but `FIREWALL_OUTBOUND_SUBNETS=172.18.0.0/16` includes the bridge
**gateway `172.18.128.0`, which is the NAS**, and DSM's daemons bind `0.0.0.0`:

```
OPEN   172.18.128.0:22  :445  :5000  :8384    ← the host
OPEN   172.18.0.10:6379 (Valkey, no password)   172.18.0.11:5432
closed 192.168.1.3:22   closed 192.168.1.1:80   ← the LAN path does hold
```

What genuinely contains it is the mount set (§0.3).

**P4 — Syncthing relay → `service_rw` on the host network.** Gated by real
device-certificate auth, which is why it ranks below P3. If the handshake code
breaks it yields uid 1031 / gid 65539 **on the host network namespace, not in a
container** — with, per §0.3, read/write over the entire `data` share. Leads
straight to P5.

**P5 — Any `service_rw` foothold → the repo → root in a container, unattended.**
The `docker` share is Read/Write for `service_rw` **and** `service_ro` (README →
Groups), inheriting to the checkout. Verified as uid 1030:

```
WRITABLE-repo-dir      WRITABLE-dotenv      WRITABLE-initscript
```

`99-overwrite-config` is bind-mounted to `/custom-cont-init.d/` and executed **as
root** by s6 on every qBittorrent start; `restart: unless-stopped` means a reboot
fires it with nobody at the keyboard. `:ro` stops the *container* editing it, not
the host-side group. Narrower than it first looks: `prometheus` and `alertmanager`
both run as uid 65534, so only `99-overwrite-config` is a root path.

**P6 — `.env` rewrite → arbitrary host mount → host root.** `.env` is mode **0777**
with the same grant, and `sudo docker compose` interpolates `DOCKER_DATA` /
`DATA_ROOT` / `*_UID` straight into `volumes:` and `user:`. What stops it is timing
only: no root crontab and none of the 17 Synology scheduled tasks runs
`docker compose`, so it waits for you to type it. That is why P5 outranks it.

**P7 — A malicious photo → `immich-machine-learning` as root.** Unauthenticated on
`:3003`, root, no capability drop, and its purpose is inference over user-supplied
images. Only mount is a named-volume cache, which is the sole thing bounding it.

**P8 — Container → host and router.** Firewall rules 28 and 29 are
`RETURN all -- 172.18.0.0/16` and `RETURN all -- 172.16.0.0/12` (29 is a strict
superset of 28). From the unprivileged `prometheus` container: `192.168.1.3:22`,
`:445`, `:5000`, `:5001`, `:8384`, **the router at `192.168.1.1:80/443`**, and
internet egress. Container → tailnet peer is closed.

**P9 — Caddy → the Cloudflare token and both wildcard keys.** Root with
`CapEff a80425fb` on both networks. Requires tailnet or LAN presence first, and
`192.168.2.3:443` measured **closed** from the tailnet — macvlan children are
unreachable from their own parent. That control works, by accident.

### Out of scope

| Item | Reasoning | What puts it back |
|---|---|---|
| Targeted / APT adversaries | Nothing here justifies a bespoke campaign; modelling it distorts every other ranking | Your home network becomes a route into an employer |
| Insider threat, separation of duties | One operator; both `administrators` accounts are yours | A second person gets an admin or sudo account |
| Compliance, audit trails, risk registers | Not a company | Never, realistically |
| Physical theft / at-rest encryption | Volume is unencrypted *(unverified)*; a burglary losing all confidentiality is a fair trade for a box in a house | The NAS leaves the house, or `Personal/` starts holding someone else's data |
| LAN / IoT lateral movement | IoT is on its own VLAN with no inter-VLAN routing; the tailnet paths dominate | The LAN gains an untrusted segment — bridged guest Wi-Fi, a housemate's device |
| The macvlan surface at `192.168.2.3` | Measured unreachable from the tailnet; only Caddy is there | A second container joins macvlan, or the router forwards to `192.168.2.x` |
| The repo being public | Removes recon cost, creates no path; no `secrets.env` ever reached git (`git log --all -S`) | A plaintext credential lands in a commit |
| Immich `publicUsers: true` | User enumeration on a login page only you can reach | §5 ships — name this in the re-run trigger |

### The control that outranks everything below

**An offsite copy of `Personal/`.** Asset #1's availability is defended by hourly
snapshots on the same volume and nothing else; P1, P5, ransomware and a house fire
all end in the same place. `--append-only` is set, but the repository contains only
game saves. See [plans/backups.md](backups.md). Do that first.

Of the items *in* this plan, §2 is the highest-value block: the tailnet is the sole
authentication boundary for ~20 ports that authenticate nothing, and
`tailscale debug netmap` shows the enforced filter is a single allow-all rule
(`Srcs: 100.64.0.0/10 → Dsts: 0.0.0.0/0:0-65535`).

---

## Status

Tracks execution against the plan below. Update the box when an item actually
lands on the running system, not when it's merged — a merged compose change with
no `up` yet is still `[ ]`.

### §1 — One-line fixes

- [x] 1. Second age recipient — `.sops.yaml` has two recipients, all six
      `secrets.enc.env` re-keyed, recovery key verified to decrypt alone and
      stored in the password manager (not on disk anywhere). 2026-08-19.
- [x] 2. Deleted `/volume1/backups/immich-pre-restructure.sql`.
      `data/macos/hashhar.tar.gz` was already gone before this pass. 2026-08-19.
- [x] 3. `chmod 0644 .env` on the NAS — done last, after the `git pull` that
      would have re-inherited the share ACL. Confirmed this also stripped the
      ACL on a plain file (the plan's item 3 caveat), not just directories.
      2026-08-19.
- [x] 4. Caddy `map` regexes anchored (`~^(x)\.`). Verified `xplex...` → 404,
      `plex...` still proxies. 2026-08-19.
- [x] 5. qBittorrent backup retention capped at 5/file in
      `99-overwrite-config`; 60 stale `.bak.*` pruned on the NAS (73 → 13).
      2026-08-19.
- [x] 6. `.gitignore` guards key material (`*.key`, `*.pem`, `*.htpasswd`);
      `.env` labeled non-secret. 2026-08-19.
- [x] 7. Dead qBittorrent `WebUI\AuthSubnetWhitelist*` lines dropped;
      `LocalHostAuth=false` kept. 2026-08-19.
- [x] 8. Alertmanager entrypoint hardened: `umask 077` + `set -e`,
      `smtp_auth_password_file` instead of templating the password into the
      YAML. Verified `0600` perms and no password in the rendered config.
      2026-08-19.

### §2 — Close the tailnet

- [ ] 2.1 Kernel-mode tailscaled (fix the boot-order accident)
- [ ] 2.2 Narrow advertised routes
- [ ] 2.3 Write Tailscale ACLs
- [ ] 2.4 Authenticate Valkey
- [ ] 2.5 Turn off the Tailscale web client
- [ ] 2.6 Close the SSH path

### §3 — Close container → host

- [ ] 3.1 Move the repo checkout out of the `docker` share
- [ ] 3.2 Narrow firewall rules 28/29
- [ ] 3.3 Narrow gluetun's outbound subnet
- [ ] 3.4 Split `data` by trust tier

### §4 — Container hardening

- [ ] 4.1–4.4 `no-new-privileges` / `cap_drop` / `read_only` / drop the
      boot-time tracker fetch, per-stack via the `x-hardened` anchor

### §5 — Public ingress

- [ ] Not decided whether this ships at all. No sub-items started.

---

## 1. One-line fixes, no service impact

Eight items, all mechanically checkable, none needing a decision.

1. **Second age recipient.** `.sops.yaml` has exactly one. The only failure mode in
   this plan that is *unrecoverable*. Generate an offline recovery key, store it in
   the password manager, add it as a second recipient, `sops updatekeys` all six
   files.
2. **Delete `/volume1/backups/immich-pre-restructure.sql`** — 1.9 GB plaintext
   cluster dump, every Immich row. POSIX `----------` makes it look safe; its ACL
   grants `group:backup` full `rwxpdDaARWc`, so `restic` can read **and delete** it.
   Also delete `/volume1/data/macos/hashhar.tar.gz` (54 GB).
3. **`chmod 0644 .env`** — currently **0777**, but the mode bits are not what grant
   write here: the inherited Synology ACL on the `docker` share gives
   `service_rw`/`service_ro` full `rwxpdDaARWc` regardless of POSIX bits (measured
   on `.env` itself). `chmod` may strip that ACL and fall back to pure POSIX —
   measured true for `chmod 2770` on a directory in §3.4, unverified for a plain
   file — but even then, the next `git pull` or checkout rewrites this tracked file
   and it re-inherits the share ACL. Do the chmod anyway, for the world-writable
   POSIX bits; the mechanism that actually closes P6 is §3.1's `mv` out of the
   share.
4. **Anchor the Caddy `map` regexes.** `~(plex)\..*` is unanchored: measured,
   `xplex.nas.ts.hashhar.com` → **200** (empty body), `notaservice…` → 404. Not
   exploitable today, but §5 leans on this allowlist. Use `~^(plex)\.`.
5. **Prune the qBittorrent backups.** 73 `*.bak.*`, oldest 2026-03-09, each
   `qBittorrent.conf.bak.*` holding a WebUI password hash at 0644. Add a retention
   cap to `99-overwrite-config` and delete the existing ones.
6. **`.gitignore`** — two lines today. Add `*.key`, `*.pem`, `*.htpasswd`, and mark
   the tracked `.env` as "paths, UIDs and ports only — never secrets".
7. **Drop the dead qBittorrent whitelist lines.** `WebUI\AuthSubnetWhitelist=192.168.0.0/22`
   + `Enabled=true`. There is **no reachable path with a `192.168.x` source at all**
   — no published port, gluetun netns, `FIREWALL_INPUT_PORTS=8080` from the bridge
   only, tailnet arrives as `172.18.128.0`. Measured 403 both via Caddy and direct.
   Dead config. Keep `WebUI\LocalHostAuth=false` — gluetun needs it.
8. **Fix the Alertmanager entrypoint.** `/tmp/alertmanager.yml` is
   `-rw-r--r-- nobody nobody`; `entrypoint.sh` has no `set -e`, so a failed render
   still `exec`s against a stale config.
   - Add `umask 077` and `set -e`.
   - **Use `smtp_auth_password_file`** (supported by `prom/alertmanager:v0.33.1`)
     and mount the password as a file — then no secret is templated at all.
   - `envsubst` is **absent** from the image (busybox base — measured) — but that
     only matters if the entrypoint switches from `sed` to `envsubst`. With
     `smtp_auth_password_file` in place, the only remaining templated values are
     `SMTP_FROM` and `ALERT_EMAIL_TO`, which the existing `sed` entrypoint already
     handles; there is no forcing reason to touch this. If it is done anyway, the
     `COPY --from` stage is required, not conditional. The pattern is already
     proven two lines long in `stacks/media/qbittorrent/Dockerfile`; it needs
     `libintl.so.8*` alongside the binary and the package is `gettext-envsubst`.
   - Note what this does *not* buy: `/api/v2/status` already serves `smtp_from` and
     `smtp_auth_username` in cleartext to any tailnet peer. Only the password is
     redacted. Treat those two as non-secret.
   - `prometheus/entrypoint.sh` already has `set -e`; its `sed` → `envsubst` switch
     is cosmetic (`${RESTIC_REST_SERVER_PORT}` only). Do it last or not at all.

---

## 2. Close the tailnet, in dependency order

### 2.1 Try kernel-mode tailscaled — do this first, it changes what is possible

`/dev/net/tun` exists now (`crw------- root root`, `tun` module live), created at
boot by the `Load tun module` task. The Tailscale package simply starts before it
(§0.1). Restarting the package should take the kernel-TUN path, which restores real
peer source IPs everywhere and makes §0.2's whole consequence list go away.

**Expected breakage — state it before you start.** With `NetfilterMode: 0`,
tailscaled installs no rules, so packets arriving on a real `tailscale0` from
`100.64.0.0/10` match no `RETURN` rule and hit rule 30 `DROP`. **You will lose
tailnet access until a firewall rule for `100.64.0.0/10` exists.**

1. Add the `100.64.0.0/10` firewall rule **first**.
2. Do the restart from a path that is not itself riding the tailnet. Per §0.4,
   there is no "LAN path" from any device you own — `ip route get 192.168.1.3` on
   `xenon-wsl` resolves via `tailscale0`, table 52, even though the box is
   physically on the LAN. Concretely: run `tailscale down` on the client first
   (the direct route returns once the tailnet route is out of the way), or use a
   device that was never enrolled in the tailnet at all. Key expiry is disabled on
   this node, so a botched switch is not also a re-auth problem.
3. `synopkg restart Tailscale`, then `ip link show tailscale0` and re-run the peer
   probe.
4. Re-test subnet-route behaviour for `172.18.0.0/16` — with no netfilter rules,
   SNAT/masquerade behaviour must be confirmed, not assumed *(unverified)*. Also
   re-test container → tailnet-peer, closed today per P8: it may **open** under
   kernel mode (e.g. `prometheus` reaching the desktop's root-run `0.0.0.0:3003` ML
   endpoint over the advertised route) — depends on masquerade/filter behaviour not
   yet characterised *(unverified)*.
5. Durable fix with no manual upkeep: append `synopkg restart Tailscale` to the
   existing `Load tun module` boot task. One line in a task that already exists.

### 2.2 Narrow the advertised routes — cheapest large win in the plan

Advertised today: `0.0.0.0/0`, `::/0`, `172.18.0.0/16`, `192.168.0.0/22`. The README
already carries the commented-out alternative.

- **`172.18.0.0/16` exposes 14 measured endpoints; three are actually dialed from
  off-NAS**: `172.18.0.3` (Caddy), `172.18.0.10` (Valkey), `172.18.0.11` (Postgres).
  Advertising `172.18.0.3/32,172.18.0.10/32,172.18.0.11/32` closes gluetun's control
  API, immich-ml, Prometheus, Alertmanager, Grafana's direct port, node-exporter,
  smartctl-exporter, restic and Plex's direct port **in one command** — no new
  secrets, no ACL file, nothing for Dependabot to track.
- **`192.168.0.0/22`** is what puts SSH, SMB and DSM on the tailnet, and per §0.4 it
  is also what breaks the `*.nas.hashhar.com` name set on every device you own.
  Dropping it is one change with two wins. Decide on it rather than documenting it —
  the cost is remote DSM and LAN access while travelling.

### 2.3 Write Tailscale ACLs

Not a prerequisite for sharing — **the only enforcement point that exists** while
the firewall is blind, and adversary #1 is your own devices, which are live today.

- The Android phone has no business reaching `:22`, `:445` or `:5252`. Grant it
  Caddy and little else.
- **Deny the exit node explicitly.** `0.0.0.0/0` + `::/0` are advertised with no
  policy, so any node you ever share can egress via your home IP. Nothing in the
  previous plan covered this.
- Shared external users **cannot** be placed in a `group:` — group members are
  specified by email within your own tailnet. Use **`autogroup:shared`**. Fix
  `TODO.md`, which says `group:friends`.
- `tag:edge` → the §5 VPS, tag-owned so it cannot inherit `group:admin`, and never
  granted the exit node or `192.168.0.0/22`.

**Know what ACLs cannot do here.** Because of §0.2's SNAT, granting a sharee
`172.18.0.3:443` gives them **every vhost Caddy serves** — grafana, prometheus,
qbittorrent, syncthing, restic — not just plex and immich. Caddy cannot tell them
from you. So a forward-auth layer or the two-listener split in §5.2 is a
**prerequisite for sharing**, not a later nicety. §2.1 does not fix this either;
it makes it *possible* to fix.

### 2.4 Authenticate Valkey

`CONFIG GET requirepass` → empty, `+PONG` from any peer container, 59 keys. Set
`requirepass` and the matching `REDIS_PASSWORD` for `immich-server` and the remote
transcode worker; add it to `stacks/photos/immich/secrets.enc.env`. Worth doing even
after §2.2, because the desktop worker still needs the route and is adversary #1.
Postgres is fine by comparison — `pg_hba.conf` requires `scram-sha-256`.

### 2.5 Turn off the Tailscale web client

`RunWebClient: true` puts an unauthenticated-read management surface on `:5252` for
every peer (P2). Nothing here uses it; the `tailscale` CLI over SSH covers the same
ground. Turn it off and deny `:5252` in §2.3 as belt and braces.

### 2.6 Close the SSH path

Ten minutes, and it removes the brute-force half of P1 — which autoblock cannot,
per §0.2:

- `PasswordAuthentication no` (keys only).
- Actually enrol 2FA. The `otp_enforce_option=admin` setting is enforcing nothing.
- Reconsider `NOPASSWD: ALL`. It exists because Synology's Docker requires sudo.
  Scoping it to `/usr/local/bin/docker` is cosmetic, not a fix: passwordless
  `docker` **is** root-equivalent (`sudo docker run -v /:/host … chroot /host`),
  so the scoped rule still leaves "sshd compromise equals instant root" true.
  Worth doing for the audit trail it leaves, not for containment it does not
  provide.

---

## 3. Close container → host

This tier decides whether §4 is worth anything at all.

### 3.1 Move the repo checkout out of the `docker` share

This is the whole of P5 and P6, and the fix is a `mv`.

```
/volume1/git    administrators rwx, backup r-x          →  qbittorrent: ---
/volume1/docker + service_rw rwx, + service_ro rwx      →  qbittorrent: rwx
```

**Verified this does not break the config bind mounts.** On a scratch directory
under `/volume1/git` (mode `d---------`, since removed):

```
$ sudo -u qbittorrent head -1 …/probe.conf
head: cannot open … Permission denied                 # host-side: denied
$ docker run --rm --user 1030:65539 -v …/probe.conf:/probe.conf:ro alpine:3.24 head -1 /probe.conf
hello-from-admin-only-share                           # in-container: reads fine
```

Docker resolves the bind-mount source as root at mount time; the host path above it
is irrelevant afterwards, and the Synology ACL does not propagate into the
container's view. Update the clone path in README → Usage.

Residual, accepted: `$DOCKER_DATA/{plex,grafana,prometheus,caddy,syncthing,immich}`
stay writable by every service account (directory-level, so files can be replaced
even where the file is 0600). Caddy's wildcard key and `grafana.db` measured **not
readable**, restic repo **not writable**. That is same-tier lateral movement, not
privilege escalation.

### 3.2 Narrow firewall rules 28/29, not rule 28 alone

Rules 28 (`RETURN all -- 172.18.0.0/16`) and 29 (`RETURN all -- 172.16.0.0/12`, a
strict superset of 28, presumably there for docker0's `172.17.0.0/16`) give every
container the DSM login page, SMB, SSH and the UDM admin interface (P8). Narrowing
rule 28 alone is a no-op — rule 29 stands and still returns the same traffic before
it reaches rule 30's `DROP`.

It is also not simply a matter of tightening a login-page exposure. Measured: the
DSM firewall wires **both** chains: `-A INPUT -j INPUT_FIREWALL` and
`-A FORWARD -j FORWARD_FIREWALL`, and `FORWARD_FIREWALL` carries the identical
30-rule set, ending in the same `DROP`. Rules 28/29 are what let container→LAN and
container→internet traffic escape that `DROP` at all — not redundant with the
final rule, but the reason new outbound connections work. Narrowing them to "the
host ports containers actually need" breaks: gluetun→Proton (the VPN tunnel — all
torrenting), caddy→Cloudflare (ACME renewals), alertmanager→Gmail SMTP,
immich-server→`192.168.1.40:3003` (the desktop ML worker), Plex metadata fetches,
and image pulls.

The fix that survives this: **insert DENY rules above 28/29**, sourced from
`172.16.0.0/12`, for the host ports that matter — `22`, `445`/`139`, `5000`/`5001`
— and leave 28/29 as the general RETURN for everything else (internet egress, LAN
service ports containers legitimately use). The mirror cuts both ways: those deny
rules also land in `FORWARD_FIREWALL`, so containers lose outbound `:22`/`:445`/
`:5000`/`:5001` to the LAN and internet too — nothing here dials those today, but
it is part of the price. Caddy needs host `:8384` for the
syncthing vhost, so `8384` must not be in the deny list. Whether the router itself
(`192.168.1.1:80/443`) can be blocked this way is unclear — DSM UI rules match
source + destination **port**, not destination **host**, so denying
container→router may not be expressible in the UI at all *(unverified)*.

### 3.3 Narrow gluetun's outbound subnet

```yaml
- FIREWALL_OUTBOUND_SUBNETS=172.18.0.3/32   # was 172.18.0.0/16
```

Removes the host gateway, Valkey and Postgres from qBittorrent's reach (P3). Caddy
at `172.18.0.3` is the **only** thing that needs to reach the WebUI — verified
against the Caddyfile and `prometheus.yml.tpl`, which does not scrape it. gluetun's
own port-forward push goes to `127.0.0.1`, unaffected. *Test that the WebUI still
loads through Caddy afterwards.*

### 3.4 Split `data` by trust tier — decided 2026-08-19

Supersedes the group-split design that previously lived here (git history has it).
Decided with the operator; one-time copy cost accepted. Three rules produced the
layout, and they are the answer to every "why isn't X its own share":

1. **The rename weld.** Every share is its own btrfs subvolume (measured:
   `cp --reflink=always` from `data` to `git` → `Invalid argument`, kernel
   4.4.302; `mv` across shares silently falls back to a full copy). So trees
   joined by rename/hardlink flows must stay in one share:
   `Staging/Torrents ↔ Media/{Books,Comics,Movies,Music,TV}` (the *arr moves,
   plus CD rips and Picard/mp3tag working over SMB into the same `Music` tree)
   and `Staging/YouTube → Media/YouTube` (ytdl). README's directory-setup
   section states this as a design goal already; a split that breaks it turns a
   recurring rename into a recurring copy, which is worse than the one-time
   migration copy.
2. **Split only across a tier that matters.** Irreplaceable personal data vs
   media; hostile-input services (qbittorrent, arr, plex, ytdl) vs photo
   services (immich, syncthing) vs none. Splitting Movies from Music, or
   YouTube from the torrent trees, moves accounts around *within* a tier — no
   share.
3. **Every share costs** a mapped drive on the desktop, a snapshot schedule, a
   permission table row and a backups.md entry. Three shares is the floor that
   still buys the separation; everything finer was polish.

| Share | Contents | Grants |
|---|---|---|
| `data` (existing — nothing moves) | `Media` (incl. `YouTube`, `Sports`), `Staging` | hashhar rw, `arr` rw, `qbittorrent` rw, `ytdl` rw, `plex` ro, `restic` ro |
| `photos` (new) | `Personal/Pictures` (`Manual`, `Synced`, `immich`) | hashhar rw, `immich` rw, `syncthing` rw, `gallery-dl` rw, `restic` ro |
| `personal` (new) | `Personal/OneDrive`, `Personal/Software`, `Games`, `Scratch` | hashhar rw, `restic` ro — **no writing service account** |
| `backups` (existing) | absorbs `data/bup` | unchanged (administrators + `restic`) |

Two clarifications so the table is not "corrected" later:

- **`personal`'s "no writing service account" means no *container* account.** DSM
  CloudSync (a Synology package, outside Docker and outside this grants table)
  writes `Personal/OneDrive` continuously, and more cloud accounts may join it.
  That is by design, not a violation of the rule.
- **A future media consumer (e.g. Navidrome) is a new user plus an ro grant on
  `data`**, exactly like `plex` — never a new share (rule 2).

**Asset correction, 2026-08-19:** only `Games/Steam` is genuinely re-acquirable.
The torrent categories, the Sports recordings and the YouTube archive all carry
real reacquisition cost or none at all — which is why `restic` holds a read grant
on all three shares, not just the personal tier. The actual source list is
[plans/backups.md](backups.md)'s call. Read-only is enforced twice: the ro share
grant *and* the `:ro` mount on whatever runs the backup. The mount is the
enforcement; the grant is the backstop.

**Users and groups restart with it:**

- Delete the permission groups: `service_rw`, `service_ro`, `home`, `backup`,
  and the private-group grant on `data`. Per-user, per-share grants (the table
  above) replace all of them.
- Keep exactly one group, `services`, holding every service account — **Deny
  all apps, zero share grants**. It replaces the one thing the old groups did
  well (centrally denying DSM/SMB/app login to service accounts) and doubles as
  a uniform `PGID`. No share carries an ACE for it, so membership grants
  nothing — the property the old groups fatally lacked.
- `gallery-dl` gets its own user. Today it runs `PUID=$SYNCTHING_UID`, so it
  *is* syncthing; the clean slate is the moment to stop that.
- hashhar is granted rw on the three data-bearing shares only. `docker`, `git`
  and `backups` stay admin-only with no standing desktop mapping — a compromised
  PC (adversary #5) should find no writable path to the restic repo.

**Migration order:**

1. Create `photos` and `personal` in DSM with snapshot schedules mirroring
   `data`'s, *before* any data lands. Set the per-user permissions per the
   table.
2. Create the `gallery-dl` user and the `services` group; move service accounts
   in.
3. `rsync -a` as root: `data/Personal/Pictures/` → `photos/`;
   `data/Personal/{OneDrive,Software}`, `data/Games`, `data/Scratch` →
   `personal/`; `data/bup` → `backups/bup`. (`data/macos` is deleted by §1.2,
   not migrated.) Synology ACLs cannot be copied by rsync and should not be —
   inheriting the new share root's ACEs is the point.
4. Update `.env`/compose for immich, syncthing and gallery-dl: new host paths,
   **container-side destinations unchanged**, so Immich's DB paths and
   Syncthing's folder configs never notice.
5. Repoint DSM CloudSync (OneDrive) and the desktop's SMB mapping for
   `Games/Steam`.
6. Verify (below), then delete the migrated trees from `data`. `data`'s
   existing snapshots keep the old copies as a rollback window until expiry —
   note the protection only lands when `Personal` actually leaves the share;
   stripping group grants earlier cannot protect a subtree the share root still
   reaches.
7. Swap `data`'s permission rows from the old group grants to the per-user set,
   and delete the dead groups.

**Verify:** re-run §0.3's probe — `sudo -u qbittorrent` against the `photos` and
`personal` roots must be denied everywhere; immich, syncthing and gallery-dl come
up healthy on the new mounts; CloudSync syncs; the Steam mapping works; `restic`
can read every declared source and write only `backups`.

**What this closes:** §0.3's measured harm (qbittorrent RWX over `Personal`,
`bup`, `macos`) becomes structurally impossible. P4's blast radius shrinks from
the whole `data` share to `photos`. Asset #7's Immich DB dumps become readable by
the photo tier only (move them out of the upload tree regardless, per backups.md).
§5.5's llm.md conflict dissolves with the groups. **What it does not touch:**
§3.1 (the repo checkout leaves the `docker` share — same disease, separate fix),
the cross-service appdata exception, and everything in §2.

**At execution time, update:** README (Shared Folder, Groups and Users tables,
the Directory Setup tree and its `chown` snippet), CLAUDE.md's storage layout
(`DATA_ROOT` splits into per-share roots), and backups.md's source list.

**Why not in-place ACL surgery** (kept so it stops being re-litigated): `chown`
is useless under inherited ACEs (§0.3); per-directory `synoacltool` ACEs are
hand-maintained and invisible to POSIX tooling; `chmod 2770` conversion strips
the Synology ACL all-or-nothing per share — it would break `plex`'s ACL-only
read on `Media/Sports` and SMB's delegation to the ACL (`skip smb perm=yes`).
All three fight the platform. Share-level permission is the unit DSM manages
natively; the split moves the security boundary to where the tool actually is.

**Live bug worth fixing regardless of the above:** `caddy`, `grafana` and
`prometheus` appdata are `root:root drwxr-xr-x`, so a `0640` file inside them is
**not** readable by `backup`. Verify what restic can actually read before trusting
the backup. That is a backup-correctness bug, not a hardening aside.

**Mode drift, measured:** no setgid directory exists anywhere under `/volume1/data`;
2216 files are `-rwxrwx--- ytdl:service_rw` (exec bit from SMB); 36 files under
`Staging/_torrents/Completed/` are **world-writable**. `UMASK` is per-image:
linuxserver images honour it, `syncthing/syncthing` and the Immich Node images do
not.

---

## 4. Container hardening

Defence in depth. Pays off only *after* an app-level RCE, which is why it sits
below §1–3. Roll out per-stack via an `x-hardened: &hardened` anchor, one stack at a
time so breakage is attributable. No service uses any of these today.

### 4.1 Order by blast radius, not input hostility

Measurement inverts the obvious ordering: qBittorrent handles the most hostile input
and has the **narrowest mounts** on the box, while `prometheus` — which processes
nothing hostile — reaches the host and the router (P8).

1. **immich-machine-learning** — root, unauthenticated on `:3003`, parses arbitrary
   images (P7). The clearest instance of adversary #3 in the fleet, and the cheapest
   fix in this tier is simply `user:` — it has one named-volume mount and no reason
   to be root. The desktop's remote-ML overlay publishes the same root-run service
   on `0.0.0.0:3003`.
2. **caddy** — root, full default capability set, holds the Cloudflare token and
   both wildcard keys (P9).
3. **smartctl-exporter** — root **and** `SYS_RAWIO` **and** eight raw `/dev/sata*`.
   The root is as much of the problem as the capability.
4. **gluetun** — root, `NET_ADMIN` on top of the full default set.
5. **node-exporter** — uid 65534, which bounds it, but `pid: host` and `/:/rootfs:ro`
   make it the widest mount in the fleet.
6. **immich-server**, **qbittorrent** — hostile input, already non-root, narrow mounts.

### 4.2 `no-new-privileges` and `cap_drop`

```yaml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

with minimal per-service `cap_add` determined empirically: smartctl-exporter needs
`SYS_RAWIO`, caddy `NET_BIND_SERVICE`, gluetun `NET_ADMIN`, and the linuxserver s6
images a `CHOWN`/`SETUID`/`SETGID`/`DAC_OVERRIDE` class set.

### 4.3 `read_only: true` — expect to abandon it for most services

The s6 linuxserver images and Immich write to their root filesystem at startup. Try
it; where it fails keep `no-new-privileges` + `cap_drop: ALL`, which cost nothing.
**Record which services were tried and failed**, so it is not re-litigated.

### 4.4 The last boot-time network dependency

The `apk add gettext` is gone — the Dockerfile already copies `envsubst` from a
build stage. What remains: `99-overwrite-config` fetches tracker lists from
`newtrackon.com` and `raw.githubusercontent.com` on every boot, **through the VPN**.
Tolerated via `|| true`, but it is what blocks §4.3 for this service.

---

## 5. Public ingress, if taken

Not decided. Recorded so the consequences are visible before the decision.

### 5.1 The options

- **Plex** — share via plex.tv, independent of everything else. Behind CGNAT you
  fall back to Plex Relay (bandwidth-capped; Plex Pass raises it). Test before
  assuming friends need Tailscale at all.
- **Immich** — no built-in remote access; upstream recommends a TLS reverse proxy or
  a VPN and calls the VPN the safe default.
- **Everything else** — Tailscale node sharing plus §2.3, subject to the "ACLs
  cannot subdivide Caddy" limit.
- **A rented VPS** (§5.2). Chosen over Cloudflare Tunnel (Cloudflare's terms of
  service bar sustained media streaming; free tier caps uploads at 100 MB, which
  breaks Immich) and over Tailscale Funnel (tailnet-owned names only).

The deciding factor is friction: extended family will not install Tailscale, and
enough sharees pushes the tailnet onto a paid plan.

### 5.2 VPS design

**Transport: a tailnet node, not WireGuard.** The subnet router already advertises
the bridge, so a VPS running `tailscale up --accept-routes` reaches Caddy with no
new keys, no DNAT and no inbound port at home. Better posture too: a WireGuard peer
is a route with no policy attached; a tagged tailnet node is governed by §2.3.

**Termination: SNI passthrough at the VPS (Caddy `layer4`), not L7.** The VPS
matches on SNI, allowlists the public names, and proxies raw TLS to home Caddy.
So the VPS never holds a private key and never sees plaintext; no ACME runs on it
(home Caddy's DNS-01 already issues the wildcards and does not care where the A
record points); and exposure is fail-closed.

**Separate the public surface by socket, not by source address.** The previous
design said home Caddy should "refuse the admin vhosts when the request arrives from
the VPS peer". Per §0.2 there **is no VPS peer address** at Caddy — every tailnet
request is `172.18.128.0`. A `remote_ip 172.18.128.0` matcher denies the admin
vhosts to *you*, over your only remote path. It is a self-lockout, not defence in
depth.

Instead: add a second site block on home Caddy bound to a dedicated port (say
`:8443`) containing **only** the public names; point the VPS's `layer4` proxy at
`172.18.0.3:8443`; grant `tag:edge` exactly `172.18.0.3:8443`. The existing `:443`
block keeps every vhost for internal use. Fail-closed by construction — a service is
public only if it is in the public block *and* named in the VPS SNI list — and it
needs no source-IP discrimination at all. It is also simpler than the original.

**`trusted_proxies` cannot name the peer** for the same reason; the narrowest
expressible grant is `172.18.128.0/32`, which means "any tailnet peer, plus the host".
With the two-listener split that is bounded — PROXY protocol v2 and `trusted_proxies`
apply only to `:8443`, so a bridge container cannot forge `X-Forwarded-For` into the
private listener. §2.1 landing first would make the original per-peer wording
achievable, which is the strongest argument for trying it before committing here.

PROXY protocol v2 from the VPS plus a matching `listener_wrappers` is still required
regardless: without it CrowdSec/fail2ban have one address, Immich's rate limiting
collapses to one bucket, and access logs are useless for incident response.

**Unified URLs.** Split-horizon DNS via a single CoreDNS container, bound per
interface and serving no recursion. But note §0.4 first: the `192.168.2.3` answer is
already unreachable from every device you own, so either drop the `192.168.0.0/22`
advertisement (§2.2) or serve `172.18.0.3` to everyone inside and retire the macvlan
answer. A design that faithfully serves an answer that does not work is worse than
no design. Expect DNS rebind protection on the UDM to drop a public name answering
with an RFC1918 address until whitelisted.

**Priced in, not discovered later:** Immich becomes internet-reachable and moves
fast, so its patch cadence becomes yours to own. That, not container hardening, is
the item most likely to matter first.

### 5.3 Authelia — a prerequisite for *sharing*, not a consequence of it

Per §2.3, ACLs cannot subdivide `172.18.0.3:443`, so a sharee gets every vhost. The
fix is Authelia behind Caddy's `forward_auth` for the admin services, or the
two-listener split above — one of the two must exist before anyone else joins.

**Do not let it look like the control that makes public ingress safe.** It is not.
What keeps admin services off the internet is the SNI allowlist plus the socket
split. And the two services family actually wants are exactly the two Authelia
cannot cover — Immich's mobile app cannot complete a forward-auth redirect at all.
Scope it to browser-reachable admin endpoints and resist making it a universal front
door, which in practice becomes a gate with a hand-maintained list of `/api/*`
bypasses.

Drop **Alertmanager** from the protected list in both this plan and `TODO.md`: it
has no Caddy vhost and is only reachable direct at the container's bridge address
(`172.18.128.7:9093`, as measured 2026-08-19 — this `/17` carve-out address is
dynamic and can shift on container recreation; prefer `alertmanager:9093` by name),
so forward-auth cannot cover it. `TODO.md` also needs its `group:friends` →
`autogroup:shared` fix and its `*.nas.ts.hashhar.com` share URLs updated.

### 5.4 Rate limiting on Caddy

`caddy-ratelimit` on auth endpoints, gated on §5.2's PROXY-protocol work. Note the
same trap applies *today*: any rate limit added now keys on `172.18.128.0` and
buckets all five of your devices plus the host together, so nobody should add it
"for the LAN" and create a self-DoS.

### 5.5 Conflict to fix when `plans/llm.md` executes

It sets `OPENWEBUI_GID='65539'` while stating no shared-data access is needed.
Per §0.3 that grants full read/write over the entire `data` share regardless of
mounts. Give it no data-share membership. Once §3.4 lands and the permission
groups are deleted, the conflict dissolves — GID 65539 will grant nothing — but
until then the instruction stands.

---

## Deliberate exceptions

| Item | Why it stays |
|---|---|
| `plex` on `:latest` | The linuxserver image updates Plex internally and the version moves too fast to track; pinning is pure toil. |
| Unpinned `pip install gallery-dl` | Dependabot's `docker` ecosystem only parses `FROM` lines, so it would never bump this. Pinning buys manual work, not safety. |
| Unpinned xcaddy `caddy-dns/cloudflare` | Same reason. |
| Tailscale key expiry disabled on the NAS | Verified: `Self.KeyExpiry` is null, all four peers carry real expiries. Deliberate — prevents lockout while travelling. |
| `WebUI\LocalHostAuth=false` | gluetun posts to `127.0.0.1:8080/api/v2/app/setPreferences` with no credential to push the NAT-PMP port. |
| Cross-service appdata write access | Every service account can write every other's `$DOCKER_DATA` dir. Fixing it means per-service shares — too much churn for same-tier lateral movement. The parts that matter (Caddy's key, `grafana.db`, the restic repo) are already out of reach. |
| The age key living on the NAS | Required for unattended `up` after a reboot. Accepted knowingly; §1's second recipient is the mitigation that matters. |
| The GitHub repo being public | Removes recon cost, creates no path. No plaintext secret has ever been committed. |
| gluetun's unauthenticated control GETs | `/v1/vpn/status`, `/v1/publicip/ip`, `/v1/openvpn/portforwarded` answer any bridge peer; `/v1/vpn/settings` → `Unauthorized`, so no credential leaks. §2.2 removes the tailnet path. |
| `restic-rest-server --prometheus-no-auth` | Decided: keep it. `/metrics` answers 200 while `/` is 401, exposing repo size and blob counts only. §2.2 closes the direct port and §2.3 gates Caddy's vhost; a scrape credential would be one more secret to rotate for near-zero gain. |
| Tracker fetch at boot | Two public URLs, failure tolerated via `|| true`. Blocks §4.3 for qBittorrent and nothing else. |
| Syncthing GUI bound to `0.0.0.0:8384` | `config.xml` says `127.0.0.1:8384`, but the `syncthing/syncthing` image sets `STGUIADDRESS=0.0.0.0:8384` as a container env var, which overrides it — measured: listens on `:::8384`, answers 200 on the bridge gateway. Has real auth (user + bcrypt password, TLS off) and the wide bind is required by Caddy's syncthing vhost, which proxies to `$HOST_ADDRESS:$SYNCTHING_PORT`. |


---

## Verification

**§1**

1. `sops decrypt` succeeds with the recovery key alone, on a machine without the
   primary key.
2. `docker exec alertmanager ls -l /tmp/alertmanager.yml` → `0600`, and alerts still
   deliver end to end.
3. `xplex.nas.ts.hashhar.com` returns 404, not 200.
4. No `*.bak.*` older than the retention cap remains in qBittorrent's config dir.

**§2**

5. `ip link` shows `tailscale0` and the cmdline no longer contains
   `--tun=userspace-networking`.
6. A tailnet request through Caddy logs the peer's `100.x` address as `client_ip`,
   not `172.18.128.0`.
7. `ssh radon@<tailnet-ip>` reports the peer's `100.x` address, not `127.0.0.1`.
8. Subnet routing survives: the desktop transcode worker reaches `172.18.0.11:5432`
   and picks up jobs.
9. After §2.2, from a tailnet peer: `172.18.0.3:443` connects; `172.18.128.1:8000`,
   `.4:3003`, `.6:9090`, `.9:9633` do not — addresses as measured 2026-08-19 from
   the dynamic `/17` carve-out; re-resolve by container name if any have been
   recreated since.
10. `tailscale debug netmap` no longer shows a single `0.0.0.0/0` allow-all rule,
    and the exit node is unusable from a restricted node.
11. `curl http://<tailnet-ip>:5252/api/data` fails.
12. Valkey `PING` fails without credentials and succeeds with them; Immich stays
    healthy and the remote worker still picks up jobs.
13. SSH with a password fails; SSH with a key succeeds; DSM prompts for a second
    factor.

**§3**

14. As `qbittorrent`: the repo checkout, `.env` and `99-overwrite-config` are all
    unwritable; every stack still comes up with `--build` and every config bind
    mount still renders.
15. From `prometheus`, `192.168.1.3:5000` and `192.168.1.1:443` are unreachable.
16. From `qbittorrent`, `172.18.128.0:22`, `172.18.0.10:6379` and `172.18.0.11:5432`
    are unreachable **and** the WebUI still loads through Caddy.
17. From a tailnet peer, direct to `gluetun:8080`, still returns 403.

**§4**

18. `docker inspect --format '{{.HostConfig.SecurityOpt}} {{.HostConfig.CapDrop}}' <container>`
    reflects the anchor; each stack comes up healthy, one at a time.
19. `docker top immich-machine-learning` no longer shows root.
20. The VPN killswitch still holds: `docker exec qbittorrent wget -qO- https://ipinfo.io/json`
    shows a Proton exit, not the home IP.

**§5 — only if public ingress ships**

21. From an off-tailnet host, `immich.nas.hashhar.com` loads and
    `prometheus.nas.hashhar.com` does **not** — verified twice, once with the VPS
    allowlist in place and once with it deliberately widened, to confirm the
    `:8443` socket split holds on its own.
22. Home Caddy's access log shows the real client address for an off-tailnet request.
23. `X-Forwarded-For` from a container on `nas_bridge` is not honoured on `:443`.
24. From the VPS, Valkey, `192.168.1.3:22`, `:5252` and DSM are unreachable and the
    exit node is unusable — `tag:edge` → `172.18.0.3:8443` is the only path.
25. Resolving an arbitrary external name against CoreDNS from off-LAN fails.
26. One URL works on LAN, on tailnet and off-network for the same service, with a
    valid certificate in all three cases.
