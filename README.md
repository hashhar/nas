# NAS

This repository hosts my NAS setup and files related to it.

The end goal is to have all software that runs on the NAS be defined as docker
containers via docker-compose so that this repository can simply be cloned and
all stacks can be started.

In case you already have everything setup from the [Initial Setup](#initial-setup) and
[Further Setup](#further-setup) you can skip to [Usage](#usage).

# Initial Setup

After following initial setup once you arrive at DSM UI follow the steps below.

## Package Center

Add a new package source "SynoCommunity" with location
"https://packages.synocommunity.com/".

Install the following apps:

- Advanced Media Extensions
- Cloud Sync
- exFAT Access
- Log Center
- Snapshot Replication
- Storage Analyzer
- Container Manager (Docker)
- Git Server
- Tailscale
- SynoCli Disk Tools
- SynoCli File Tools
- SynoCli Monitor Tools
- SynoCli Network Tools

## Control Panel

### Shared Folder

Create the following shares:

| Name | Description | Hide | Recycle Bin | Checksum | Compression |
|------|-------------|:----:|:-----------:|:--------:|:----------:|
| `backups` | backup target | ✅ | - | ✅ | - |
| `data` | all user data | - | ✅ | ✅ | - |
| `docker` | docker containers | ✅ | - | ✅ | - |
| `git` | git repositories | ✅ | - | ✅ | ✅ |
| `synology` | synology logs and reports | ✅ | ✅ | ✅ | ✅ |
| `time_machine` | apple time machine backups | ✅ | - | ✅ | ✅ |

Additionally follow [Synology Time Machine
setup](https://kb.synology.com/en-my/DSM/tutorial/How_to_back_up_files_from_Mac_to_Synology_NAS_with_Time_Machine).

Note that enabling Bonjour is onlhy required if you don't want to manually connect to
the SMB share.

### File Services

Enable "Asynchronous read" in Advanced Settings under SMB tab.

Enable "File Fast Clone" under Advanced tab.

### User & Group

Enable "User home service" under Advanced tab.

Set up the groups and users as described below.

> 📝 **NOTE:** How to read below tables.
> - Apply columns left to right. i.e. Read/Write then Read Only then No Access;
>   Allow Apps then Deny Apps.
> - `*` means to check everything that's unchecked after applying all left
>   columns.
> - `-` means to leave unchecked so that permissions are inherited.

#### Groups

| Name | Description | Read/Write | Read Only | No Access | Allow Apps | Deny Apps |
|------|-------------|------------|-----------|-----------|------------|-----------|
| `backup` | backup users | backups, docker | `*` | - | SMB | `*` |
| `home` | home users | data | - | - | Cloud Sync, DSM, File Station, SMB, Universal Search | `*` |
| `service_ro` | read-only service accounts | docker | data | - | - | `*` |
| `service_rw` | read-write service accounts | docker, data | - | - | - | `*` |
| `time_machine` | apple time machine | time_machine | - | - | SMB | `*` |
| `<your_user>` | user private group for <your_user> | data | - | - | Cloud Sync, DSM, File Station, SMB, Universal Search | `*` |

#### Users

| Name | Description | Groups | Read/Write | Read Only | No Access | Allow Apps | Deny Apps |
|------|-------------|--------|------------|-----------|-----------|------------|-----------|
| `restic` | restic backup | `backup` | - | - | - | - | - |
| `plex` | plex media server | `service_ro` | - | - | - | - | - |
| `arr` | *arr applications | `service_rw` | - | - | - | - | - |
| `qbittorrent` | qbittorrent | `service_rw` | - | - | - | - | - |
| `syncthing` | syncthing | `service_rw` | - | - | - | - | - |
| `immich` | immich | `service_rw` | - | - | - | - | - |
| `time_machine` | apple time machine | `time_machine` | - | - | - | - | - |
| `ytdl` | youtube dl | `service_rw` | - | - | - | - | - |
| `<your_user>` | <your_user> | `<your_user>` | - | - | - | - | - |
| `<other_user>` | <other_user> | `home` | - | - | - | - | - |

### Security

Enable 2FA for users in adminstrator group under "Account" tab.

Enable account protection under "Account" tab.

Enable firewall and firewall notifications under "Firewall" tab.

Clone the `default` firewall profile, name it `secure` and add following rules:

| Enabled | Ports | Source | Action | Description |
|---------|-------|--------|--------|-------------|
| ✅ | SSH | 192.168.1.1/22 | Allow | SSH access from LAN |
| ✅ | DSM HTTP/HTTPS | 192.168.1.1/22 | Allow | DSM UI from LAN |
| ✅ | CIFS, WS-Transfer/Discovery | 192.168.1.1/22 | Allow | SMB access from LAN |
| ✅ | HTTP/HTTPS | 192.168.1.1/22 | Allow | DSM Reverse Proxy from LAN |
| ✅ | Bonjour | 192.168.1.1/22 | Allow | Bonjour service discovery |
| ✅ | SSH | 192.168.20.1/24 | Allow | SSH access from LAN |
| ✅ | DSM HTTP/HTTPS | 192.168.20.1/24 | Allow | DSM UI from LAN |
| ✅ | CIFS, WS-Transfer/Discovery | 192.168.20.1/24 | Allow | SMB access from LAN |
| ✅ | HTTP/HTTPS | 192.168.20.1/24 | Allow | DSM Reverse Proxy from LAN |
| ✅ | Bonjour | 192.168.20.1/24 | Allow | Bonjour service discovery |
| ✅ | Search Synology NAS | All | Allow | find.synology.com |
| ✅ | 22000/tcp | All | Allow | Syncthing TCP based sync traffic |
| ✅ | 22000/udp | All | Allow | Syncthing QUIC based sync traffic |
| ✅ | 21027/udp | All | Allow | Syncthing discovery broadcasts on IPv4 and multicasts on IPv6 |
| ✅ | All | 192.168.2.1/23 | Allow | All access from macvlan range (2.1 to 3.254) |
| ✅ | All | 172.18.0.0/16 | Allow | All access from Docker compose network |
| ✅ | All | 172.16.0.0/12 | Allow | All access from Docker containers |
| - | All | All | Allow | Allow by default |
| ✅ | All | All | Deny | Deny by default |

### Terminal & SNMP

Enable SSH service.

### Login Portal

Enable "Automatically redirect HTTP connection to HTTPS for DSM desktop".

### Hardware & Power

Enable automatic restart on power supply being fixed and WOL on all LAN ports.

Consider changing fan speed to "Cool mode".

Enable hibernation logs and increase hibernation time to the max of 5 hours under "HDD
Hibernation" tab.

Enable UPS support and set standby time to 1 hour.

### External Devices

Under Settings make sure that the default permissions look like you'd want them to.
Specifically make sure that non-admin users/groups have permissions if you want that.

### Indexing Service

Set thumbnail quality to High Quality.

Consider enabling conversion on a schedule to save CPU during operational hours.

## File Station

Under "Mount/Connections" tab in settings allow users in adminstrator or user private
groups to mount "Server and Cloud Service".

## Resource Monitor

Enable usage history under settings.

## Storage Manager

Schedule data scrubbing (1st of every month) and ensure space reclamation schedule is
set under Global Settings.

Create a scheduled Extended S.M.A.R.T. test (15th of every month).

Create a scheduled Quick S.M.A.R.T. test (daily midnight).

Make sure monthly drive reports and bad sector warnings are enabled under "Settings"
tab.

Change "Record File Access Time" to Never and enable "Usage Details" under the volume
settings.

## Universal Search

Disable "Skip numeric characters when indexing file contents" under Settings > System.

## Log Center

Under "Archive Settings" choose `/volume1/syno/logs` as the location to archive local
logs to once database size exceeds 1GB or logs become older than 1 month.

Enable archiving logs as text format in addition to default format.

Enable compressing log archives.

Enable archiving logs separately according to device.

## Snapshot Replication

Set up a snapshot schedule as described below:

Two configs:
- Slow moving data: Daily snapshots for 24h-30d-4w-6m
- Main data: Hourly snapshots for 168h-30d-12w-12m-1y

| Name | Enabled | Days | Frequency | Retention |
|------|---------|------|-----------|-----------|
| `backups` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 30 daily, 4 weekly, 6 monthly and 0 yearly with min 5 |
| `data` | ✅ | Daily | Every 1 hour | Keep all for 1 day. 168 hourly, 30 daily, 12 weekly, 12 monthly and 1 yearly with min 5 |
| `docker` | ✅ | Daily | Every 1 hour | Keep all for 1 day. 168 hourly, 30 daily, 12 weekly, 12 monthly and 1 yearly with min 5 |
| `git` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 30 daily, 4 weekly, 6 monthly and 0 yearly with min 5 |
| `homes` | ✅ | Daily | Every 1 hour | Keep all for 1 day. 168 hourly, 30 daily, 12 weekly, 12 monthly and 1 yearly with min 5 |
| `synology` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 30 daily, 4 weekly, 6 monthly and 0 yearly with min 5 |
| `time_machine` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 30 daily, 4 weekly, 6 monthly and 0 yearly with min 5 |

## Storage Analyzer

In Settings configure saving reports to `syno/reports/storage` and collect volume usage
history daily.

Create a report task called "Storage Report" which generates weekly reports.

## Security Advisor

Enable regular scan schedule with monthly reports saved to `syno/reports/security`.

## Tailscale

Follow the instructions at https://tailscale.com/kb/1103/exit-nodes/ to enable using the
Synology as an exit node for the Tailscale network.

Also disable key expiry from machine settings for the node if there's a chance that
you'll be unable to re-authenticate to Tailscale every 3 months.

Follow the instructions at https://tailscale.com/kb/1131/synology#schedule-automatic-updates
to schedule automatic updates.

# Further Setup

Once you've configured everything as needed on DSM we can move to configuring things for
SSH and other use.

## PublicKey Auth for SSH

```sh
ssh-copy-id -i ~/.ssh/id_rsa <ssh_user>@<synology_ip>
```

You might also want to add following to `~/.ssh/config`:

```ssh-config
Host <synology_ip> <hostname>.local <hostname> <dns_name>
  HostName <synology_ip>
  User <ssh_user>
  IdentityFile ~/.ssh/id_rsa
```

## Passwordless Sudo

Since Synology's Docker requires sudo always it's a good idea to enable passwordless
sudo as below:

```sh
cat << EOF | sudo tee /etc/sudoers.d/99-passwordless-sudo
<ssh_username> ALL=(ALL) NOPASSWD: ALL
EOF
```

## Directory Setup

Each volume within a container gets treated as its own filesystem. This means
that if we move files across volumes then Docker does a copy and then delete -
creating unwanted disk IO and temporarily taking up double the space.

So we setup a structure such that everything that our containers need to touch
lies under a single root.

Here's the structure we are going to follow (which also includes additional
manually managed folders):

```
.
├── Games
│   ├── Setups                         [1]
│   └── Steam                          [2]
├── Media                              [3]
│   ├── Books
│   │   └── _torrents                  [4]
│   ├── Comics
│   │   └── _torrents
│   ├── Movies
│   │   └── _torrents
│   ├── Music
│   │   └── _torrents
|   ├── Sports                         [5]
│   ├── TV
│   │   └── _torrents
│   └── YouTube                        [6]
│       └── _archive                   [7]
├── Personal                           [8]
│   ├── OneDrive                       [9]
│   ├── Pictures
│   │   ├── Manual                     [10]
│   │   └── Synced                     [11]
│   └── Software                       [12]
├── Scratch                            [13]
└── Staging
    ├── Torrents                       [14]
    │   ├── Books
    │   ├── Comics
    │   ├── Movies
    │   ├── Music
    │   ├── TV
    │   └── temp
    ├── YouTube                        [15]
    │   └── _archive                   [16]
    └── _torrents                      [17]
        ├── Completed
        └── Watching
            ├── Books
            ├── Comics
            ├── Movies
            ├── Music
            └── TV
```

> 📝 **NOTE:** You can use the below snippet to create the structure - make
> sure to change `/volume1/` to whatever is appropriate in your case.  
> **Replace *hashhar* with your username, not the SSH user.**
>
> ```sh
> root='/volume1/data' # path to share where you want this directory structure
> private_user='hashhar' # name of your user (not the SSH user)
> categories_csv='Books,Comics,Movies,Music,TV'
> echo mkdir -p "$root"/Media/{$categories_csv}/_torrents "$root"/Staging/{Torrents/{$categories_csv},_torrents/{Completed,Watching/{$categories_csv}}}
> # Execute the output of previous command
> mkdir -p "$root"/Games/{Setups,Steam}
> mkdir -p "$root"/Media/Sports
> mkdir -p "$root"/{Media,Staging}/YouTube/_archive
> mkdir -p "$root"/Personal/{Pictures/{Synced,Manual},Software}
> mkdir -p "$root"/Scratch
>
> # May want to instead let permissions get managed by apps themselves when
> # they create these directories
> # Games
> sudo chown -R "$private_user":users "$root"/Games # over SMB group is always users
> # Media
> sudo chown -R arr:service_rw "$root"/Media
> sudo chown -R ytdl:service_rw "$root"/Media/YouTube
> sudo chown -R "$private_user":users "$root"/Media/Sports # over SMB group is always users
> # Personal
> sudo chown -R "$private_user":users "$root"/Personal # over SMB group is always users
> sudo chown -R syncthing:service_rw "$root"/Personal/Pictures/Synced
> # Staging
> sudo chown -R qbittorrent:service_rw "$root"/Staging
> sudo chown -R ytdl:service_rw "$root"/Staging/YouTube
> # Scratch
> sudo chown -R "$private_user":users "$root"/Scratch # over SMB group is always users
> ```

### Directory Purposes

1.  `/Games/Setups`: Setup files for games.  
2.  `/Games/Steam`: Secondary Steam library folder with less played games; network
    mapped to a PC.

3.  `/Media`: Media root for apps like Plex.  
    Each subdirectory here is managed by a *arr app which moves files here from finished
    downloads from the matching subdirectory in `/Staging/Torrents`.
4.  `/Media/<category>/_torrents`: .torrent files for each category.  
    These are manually moved here to make sure we have the sources required to rebuild
    our media if needed.
5.  `/Media/Sports`: Downloaded sports matches and highlights.
6.  `/Media/YouTube`: Downloaded YouTube channels, playlists or videos.  
7.  `/Media/YouTube/_archive`: Archive files created by `yt-dlp`, scripts and `yt-dlp`
    config files used for a particular download.

8.  `/Personal`: Manually managed personal data folder.
9.  `/Personal/OneDrive`: A mirror of OneDrive maintained using CloudSync.
10.  `/Personal/Pictures/Manual`: Manually managed pictures directory.
11. `/Personal/Pictures/Synced`: Syncthing managed pictures directory.
12. `/Personal/Software`: Software installers and archives including OS ISOs.

13. `/Scratch`: This is a temporary workspace which can be used as needed.

14. `/Staging/Torrents`: Download root for torrent apps.  
    All torrent downloads get downloaded here into one of the subdirectories based on
    their category. This exactly mirrors the structure in `/Media` so that each of the
    *arr apps can move finished downloads to `/Media`.
15. `/Staging/YouTube`: In progress YouTube channel, playlist or video downloads.
16. `/Staging/YouTube/_archive`: Archive files created by `yt-dlp`, scripts and `yt-dlp`
    config files used for a particular download.
17. `/Staging/_torrents`: .torrent file root for torrent apps.  
    All .torrent files get placed here into `Completed` once downloaded. Any files
    placed into `Watching` get queued for downloads.

## Obtain the PID and GID of Users

ssh into the system using the normal user (not the dedicated users we created
above) and run `id <username>` which should output something like:

```
uid=<UID>(<username>) gid=100(users) groups=100(users),<GID>(<group>)
```

Make sure to use the group id from one of secondary groups since in our setup
the default `users` group doesn't have permissions to anything.

# Usage

First we need to copy this repository over onto the NAS.

```sh
# SSH into synology
cd /volume1/git
mkdir -p path/repo
cd path/repo
git init --bare
```

```sh
# On local machine with this repo cloned
git remote add <synology remote> <ssh user>@<synology host>:/volume1/path/repo
git push <synology remote> <local branch>
```

```sh
# SSH into synology
cd /volume1/docker/apps/nas
git clone /volume1/git/path/repo .
```

All the services here are defined using Docker Compose.

To start containers:

```sh
docker-compose up --build --detach
```

To stop containers:

```sh
docker-compose stop
```

To pull new containers:

```sh
docker-compose pull
```

To update changed containers e.g. when service definition changes or when a
newer image has been pulled:

```sh
docker-compose up --build --detach
```

To start a stopped service without using any changes:


```sh
docker-compose up --detach --no-recreate
```

To run gallery-dl (profile-gated, exits when done):

```sh
docker-compose --profile gallery-dl up --build --detach gallery-dl
```

## Environment Files

We have multiple environment files.

- `.env`: Contains variables we want to reference in the `docker-compose.yml`
  but not add to containers. Useful for extracting common paths and reusable
  values.
- `<service>/secrets.env`: Contains per-service environment variables injected
  into containers using `env_file` in `docker-compose.yml`. Useful for secrets.
  ***Define non-secret environment variables applicable to a single container
  using `environment` in `docker-compose.yml`.***

## Special Instructions

Some containers need a bit of manual setup which is described below.

### Caddy

Caddy requires some secrets to work. Make sure the following variables have values defined in `caddy/secrets.env`:

- `CF_API_TOKEN`: Cloudflare API token with read permissions for `Zone.Zone`
  and edit permissions for `Zone.DNS`.

### Plex

When Plex runs using a bridge network it incorrectly identifies LAN traffic as
coming from internet and doesn't allow to finish Plex Media Server setup.

Synology doesn't allow TCP forwarding on SSH for any user other than `root` or
`admin`. So we will temporarily re-enable the default `admin` user to create a
SSH tunnel.

If Synology is exposed outside the LAN then make sure to limit access before
re-enabling the default `admin` for security.

- Re-enable default `admin` user.
- Expose port `32400` from the Plex container.
- Create a SSH tunnel as `ssh <server> -L 32400:127.0.0.1:32400`.
- Access Plex at `http://localhost:32400/web` and finish the server setup to claim Plex.
- Close the SSH tunnel and disable the default `admin` account.

See more at:
- [Plex Support][plex-installation]
- [Plex Docker image docs][plex-docker-docs]

[plex-installation]: https://support.plex.tv/articles/200288586/#toc-2
[plex-docker-docs]: https://github.com/plexinc/pms-docker#running-on-a-headless-server-with-container-using-host-networking

### Syncthing

Syncthing needs to use host networking for local discovery to work. So
Syncthing container's network mode is set to host and we use a DNS name
pointing to the NAS host (the IP address can be used as well) as the reverse
proxy target in Caddy.

Since Syncthing uses host network we also need to make sure firewall rules
exist to allow connections to 22000/tcp, 22000/udp (data transfer) and
21027/udp (local discovery) from all IP addresses.

Make sure to enable authentication on the web UI.

### qBittorrent

Create `qbittorrent/secrets.env` with WebUI credentials:

```env
QBITTORRENT_WEBUI_USERNAME=<your-username>
QBITTORRENT_WEBUI_PASSWORD=<PBKDF2-hashed-password>
```

Generate the password hash using the included script:

```sh
python qbittorrent/gen_password.py
```

Copy the `@ByteArray(...)` value from the output into `QBITTORRENT_WEBUI_PASSWORD`.

### Restic Rest Server

You need to create the username using the `create_user` script within the
image. This will generate a `.htpasswd` file in the `$RESTIC_ROOT/restic`
which you can then keep reusing.

### Grafana

Create `grafana/secrets.env` with an admin password:

```env
GF_SECURITY_ADMIN_PASSWORD=<your-chosen-password>
```

### Alertmanager

Alertmanager sends alerts via Gmail SMTP using an App Password (not your regular account password).

1. Go to [myaccount.google.com](https://myaccount.google.com) → Security → 2-Step Verification → App passwords
2. Create a new app password named `Alertmanager` and copy the 16-character code

Create `alertmanager/secrets.env`:

```env
SMTP_FROM=your-gmail@gmail.com
SMTP_PASSWORD=abcd-efgh-ijkl-mnop
ALERT_EMAIL_TO=your-email@example.com
```

### Immich

Create `immich/secrets.env` with a shared database password:

```env
DB_PASSWORD=<random alphanumeric>
POSTGRES_PASSWORD=<same value as DB_PASSWORD>
```

**Remote ML workers:**

The NAS (DS1821+) is underpowered for ML. Instead, run ML workers on more capable machines using the compose files in `immich/`:

- **CPU-only** (macOS / Linux): `immich/docker-compose.remote-ml.yml`
- **NVIDIA CUDA** (Windows WSL2 / Linux with NVIDIA GPU): `immich/docker-compose.remote-ml-cuda.yml`

```sh
# CPU-only (e.g. MacBook)
# MacBook CPU: 1-2 workers
MACHINE_LEARNING_WORKERS=2 docker compose -f immich/docker-compose.remote-ml.yml up -d

# NVIDIA CUDA (e.g. Windows Desktop with RTX 4090 via WSL2)
# Prerequisites: Docker Desktop with WSL2 backend, NVIDIA driver 545+
# RTX 4090 can comfortably do 2-4 workers
MACHINE_LEARNING_WORKERS=3 docker compose -f immich/docker-compose.remote-ml-cuda.yml up -d
```

Default is 1 worker. This is not stored in `.env` since it varies per machine.
Verify CUDA is active by checking container logs for `CUDAExecutionProvider`.

In Immich admin UI (Administration → Machine Learning Settings), add ML worker URLs with fallback order:
1. `http://<desktop-ip>:3003` (primary — CUDA-accelerated)
2. `http://<macbook-ip>:3003` (fallback — CPU-only)
3. `http://immich-machine-learning:3003` (last resort — NAS-local, slow)

`immich-machine-learning` resolves via Docker's internal DNS from `immich-server` (same bridge network) — no IP needed.

If the primary is offline, Immich falls back to the next URL. The NAS-local worker ensures ML is always available even when all remote machines are offline.

**Post-deployment configuration:**

1. Access `immich.nas.hashhar.com` and create an admin account
2. In Administration → Storage Template, enable and set template to:
   `{{y}}/{{#if album}}{{{album}}}{{else}}{{y}} - {{MM}}{{/if}}/{{{filename}}}`
   (organises by year, then album name if set, otherwise by year-month)
3. Configure ML worker URLs as described above
4. Create a dedicated user for each user, do not use admin user
5. Install the Immich mobile app and connect to `https://immich.nas.hashhar.com`
6. Photos are synced to the NAS via Syncthing — do **not** enable in-app backup

To add an external library: Administration → External Libraries → Create, then set the import path (e.g. `/volume1/data/Personal/Pictures/Synced/Wallpapers`).

# Appendix

## Docker macvlan Networking

### Why?

Synology shares the same instance of Nginx for both it's main UI (DSM) as well
as the inbuilt Reverse Proxy. Nginx has some rules which redirect any unmatched
subdomain to the DSM login page. This means that if you reverse proxy
`nas.example.com` then any request to `other.nas.example.com` would get
redirected to DSM login page unless you also reverse proxy
`other.nas.example.com` to some IP and port explcitly. This makes using
wildcard subdomains a semi-manual process since you have to setup reverse proxy
entries for every single subdomain in the UI.

A possible fix is to edit the generated Nginx config for the reverse proxy to
remove the check on `$host` and allow wildcard subdomains in the `server_name`
but these changes will either be undid everytime you change a setting on the
NAS which touches Nginx or when DSM version is updated depending on how you
apply it.

We don't want to deal with this problem. So we can setup a separate network
stack unrelated to Synology's default which will have port 80 and 443 free for
us to run our own choice of reverse proxy on them like Caddy, Nginx, Traefik
etc.

### Description

Any container running on the macvlan network cannot connect to the physical
host and neither can the physical host connect to the container on macvlan
network.  Also any other container not running on the macvlan network is not
routable from the macvlan network.

This means our reverse proxy will not be able to reach the Synology host nor
the other way around. Also any other containers running on Synology won't be
reachable from the reverse proxy making our reverse proxy pretty useless.

To solve this we create three networks:

- `192.168.0.0/22` - secure management network.
  - `192.168.2.0/24` - macvlan network on Synology on which our reverse proxy
    container will live.
- `192.168.20.0/24` - home network.
- `172.18.0.0/16` - Docker bridge network on which other containers will run.

Our reverse proxy container will attach to both the macvlan network as well as
the Docker bridge. The macvlan will make our reverse proxy reachable from other
hosts on the home network (except the Docker host itself i.e. Synology) while
the Docker bridge will make it reachable from other containers so that we can
reverse proxy to them.

To make the macvlan network be able to talk to the host we need to add explicit
routes. Since we don't have a need to make the reverse proxy reachable from the
Synology host yet we skip this part for now but it's documented if it's ever
needed. Note that the routes and interfaces will go away on a restart.

```sh
macvlan_iface='macvlan0'
parent_iface='eth0'
host_macvlan_addr='192.168.2.50/32'
macvlan_subnet='192.168.2.0/24'

sudo ip link add "$macvlan_iface" link "$parent_iface" type macvlan mode bridge
sudo ip addr add "$host_macvlan_addr" dev "$macvlan_iface"
sudo ip link set "$macvlan_iface" up
sudo ip route add "$macvlan_subnet" dev "$macvlan_iface"
```

See [this article][1] for more details.

[1]: https://web.archive.org/web/20220706105432/https://www.linuxtechi.com/create-use-macvlan-network-in-docker/

## Tailscale Routing

Our docker-compose stack has two networks, a MacVLAN network with subnet 192.168.2.0/24 and a Docker bridge network with subnet 172.18.0.0/16.

Tailscale binds itself to the primary interface of the Synology, i.e. neither to the MacVLAN or the Docker bridge network. This means while we can use Tailscale to access Synology itself we cannot access anything that's not exposed on the host network.

To access services and containers on non-host networks we need to enable subnet routing. The goal is to be able to connect to our docker-compose stack over Tailscale using DNS names with HTTPS enabled.

The below steps are collected from:

- [Tailscale docs on subnet routers][tailscale-subnet-routers]
- [Run your own mesh VPN and DNS with Tailscale and PiHole][tailscale-mesh-vpn-dns]

[tailscale-subnet-routers]: https://tailscale.com/kb/1019/subnets/
[tailscale-mesh-vpn-dns]: https://shotor.com/blog/run-your-own-mesh-vpn-and-dns-with-tailscale-and-pihole/

- ```sh
  echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.conf
  echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.conf
  sudo sysctl -p /etc/sysctl.conf
  ```
- ```sh
  # Advertise a route to just the Caddy container
  #sudo tailscale up --advertise-routes=172.18.0.3/32
  # Advertise a route to entire Docker bridge network
  sudo tailscale up --advertise-routes=172.18.0.0/16
  ```
- Enable "Use tailscale subnets" on the client devices

Now you can register DNS records similar to below:

```bind
nas.ts.hashhar.com	1	IN	A	172.18.0.3 ; Caddy over Tailscale
*.nas.ts.hashhar.com	1	IN	CNAME	nas.ts.hashhar.com.	; Wildcard domain over Tailscale
```

Now you can access Caddy itself at nas.ts.hashhar.com and services at
*.nas.ts.hashhar.com when connected to Tailscale.

# Inspiration

A lot of the content in this setup came from the following sources in no
particular order:

- [Better Synology User Management][better-synology-user-management] by Storage Alchemist
- [Directory Setup Guide][directory-setup-guide] by Dr_Frankenstein
- [Setting up a restricted Docker user and obtaining IDs][restricted-docker-user] by Dr_Frankenstein
- [Use Docker to Set Up Plex on a Synology NAS][docker-plex-synology] by WunderTech
- [TRaSH Guides][trash-guides] by TRaSH-
- [How to Create and Use MacVLAN Network in Docker][macvlan-linuxtechi] by LinuxTechi
- [Free your Synology ports for Docker][free-synology-ports] by Tony Lawrence
- [StackOverflow - DockerMacvlan network inside container is not reaching to its own host][so-macvlan-host] by yananet
- [Reddit - Example of macvlan container communicating with other containers][reddit-traefik] by /u/lachlanhunt

[better-synology-user-management]: https://www.storagealchemist.com/synology-user-management/
[directory-setup-guide]: https://drfrankenstein.co.uk/step-1-directory-setup-guide/
[restricted-docker-user]: https://drfrankenstein.co.uk/step-2-setting-up-a-restricted-docker-user-and-obtaining-ids/
[docker-plex-synology]: https://www.wundertech.net/use-docker-to-set-up-plex-on-a-synology-nas/
[trash-guides]: https://trash-guides.info/
[macvlan-linuxtechi]: https://www.linuxtechi.com/create-use-macvlan-network-in-docker/
[free-synology-ports]: http://tonylawrence.com/posts/unix/synology/free-your-synology-ports/
[so-macvlan-host]: https://stackoverflow.com/a/67835834
[reddit-traefik]: https://www.reddit.com/r/synology/comments/s2skjl/comment/hsjw4al/
