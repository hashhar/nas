# NAS

This repository hosts my NAS setup and files related to it.

The end goal is to have all software that runs on the NAS be defined as docker
containers via docker-compose so that this repository can simply be cloned and
all stacks can be started.

# Initial Setup

After following initial setup once you arrive at DSM UI follow the steps below.

## Shared Folder

Create the following shares:

| Name | Description | Hide | Recycle Bin | Checksum | Compresion |
|------|-------------|:----:|:-----------:|:--------:|:----------:|
| `backups` | backup target | ✅ | - | ✅ | ✅ |
| `data` | all user data | - | ✅ | ✅ | - |
| `docker` | docker containers | ✅ | - | ✅ | - |
| `git` | git repositories | ✅ | - | ✅ | ✅ |
| `syno` | synology files like logs and reports | ✅ | ✅ | ✅ | ✅ |

## User & Group

Enable "User home service" under Advanced tab.

Set up the groups and users as described below.

> 📝 **NOTE:** How to read below tables.
> - Apply columns left to right. i.e. Read/Write then Read Only then No Access;
>   Allow Apps then Deny Apps.
> - `*` means to check everything that's unchecked after applying all left
>   columns.
> - `-` means to leave unchecked so that permissions are inherited.

### Groups

| Name | Description | Read/Write | Read Only | No Access | Allow Apps | Deny Apps |
|------|-------------|------------|-----------|-----------|------------|-----------|
| `backup` | backup users | backups, docker | `*` | - | - | `*` |
| `home` | home users | data | - | - | DSM, File Station, SMB | `*` |
| `service_ro` | read-only service accounts | docker | data | - | - | `*` |
| `service_rw` | read-write service accounts | docker, data | - | - | - | `*` |
| `<your_user>` | user private group for <your_user> | data | - | - | DSM, File Station, SMB | `*` |

### Users

| Name | Description | Groups | Read/Write | Read Only | No Access | Allow Apps | Deny Apps |
|------|-------------|--------|------------|-----------|-----------|------------|-----------|
| `restic` | restic backup | `backup` | - | - | - | - | - |
| `plex` | plex media server | `service_ro` | - | - | - | - | - |
| `arr` | *arr applications | `service_rw` | - | - | - | - | - |
| `qbittorrent` | qbittorrent | `service_rw` | - | - | - | - | - |
| `syncthing` | syncthing | `service_rw` | - | - | - | - | - |
| `ytdl` | youtube dl | `service_rw` | - | - | - | - | - |
| `<your_user>` | <your_user> | `<your_user>` | - | - | - | - | - |
| `<other_user>` | <other_user> | `home` | - | - | - | - | - |

## Security

Enable firewall and firewall notifications under "Firewall" tab.

Clone the `default` firewall profile, name it `secure` and add following rules:

| Enabled | Ports | Source | Action |
|---------|-------|--------|--------|
| ✅ | Encrypted terminal service | 192.168.1.0/24 | Allow |
| ✅ | Management UI (HTTP and HTTPS) | 192.168.1.0/24 | Allow |
| ✅ | Windows file server, WS-Discovery | 192.168.1.0/24 | Allow |
| ✅ | HTTP, HTTPS | 192.168.1.0/24 | Allow |
| ✅ | Synology Assistant | All | Allow |
| ✅ | All | 192.168.2.0/24 | Allow |
| ✅ | All | 172.18.0.0/16 | Allow |
| ✅ | All | 172.16.0.0/12 | Allow |
| - | All | All | Allow |
| ✅ | All | All | Deny |

## Package Center

Install the following apps:

- exFAT Access
- Snapshot Replication
- Storage Analyzer
- Docker
- Git Server

## Storage Manager

Schedule data scrubbing and ensure space reclamation schedule is set under
Global Settings.

## Snapshot Replication

Set up a snapshot schedule as described below:

| Name | Enabled | Days | Frequency | Retention |
|------|---------|------|-----------|-----------|
| `backups` | ✅ | Weekly | Every day | 6 monthly and 1 yearly with min 5 |
| `data` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 7 daily, 2 weekly, 1 monthly and 1 yearly with min 5 |
| `docker` | ✅ | Daily | Every 1 hour | Keep all for 1 day. 24 hourly, 7 daily, 2 weekly, 1 monthly and 1 yearly with min 5 |
| `git` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 7 daily, 2 weekly, 1 monthly and 1 yearly with min 5 |
| `homes` | ✅ | Daily | Every 1 hour | Keep all for 1 day. 24 hourly, 7 daily, 2 weekly, 1 monthly and 1 yearly with min 5 |
| `syno` | ✅ | Daily | Every day | Keep all for 1 day. 24 hourly, 7 daily, 2 weekly, 1 monthly and 1 yearly with min 5 |

# Docker Setup

## Obtain the PID and GID of Users

ssh into the system using the normal user (not the dedicated users we created
above) and run `id <username>` which should output something like:

```
uid=<UID>(<username>) gid=100(users) groups=100(users),<GID>(<group>)
```

Make sure to use the group id from one of secondary groups since in our setup
the default `users` group doesn't have permissions to anything.

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
├── Media                              [1]
│   ├── Books
│   │   └── _torrents                  [2]
│   ├── Comics
│   │   └── _torrents
│   ├── Movies
│   │   └── _torrents
│   ├── Music
│   │   └── _torrents
│   ├── TV
│   │   └── _torrents
│   └── YouTube                        [3]
│       └── _archive                   [4]
├── Personal                           [5]
│   ├── Games
│   │   ├── Steam                      [6]
│   │   └── Steam Backup               [7]
│   ├── Pictures
│   │   ├── Manual                     [8]
│   │   │   └── Camera Roll Archive
│   │   └── Synced                     [9]
│   │       ├── Camera Roll
│   │       ├── Saved Pictures
│   │       └── Screenshots
│   └── Software
│       ├── Automatic                  [10]
│       └── Manual                     [11]
├── Scratch                            [12]
└── Staging
    ├── Torrents                       [13]
    │   ├── Books
    │   ├── Comics
    │   ├── Movies
    │   ├── Music
    │   ├── TV
    │   └── temp
    ├── YouTube                        [14]
    │   └── _archive                   [15]
    └── _torrents                      [16]
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
>
> ```sh
> root='/volume1/data'
> categories_csv='Books,Comics,Movies,Music,TV'
> echo mkdir -p "$root"/Media/{$categories_csv}/_torrents "$root"/Staging/{Torrents/{$categories_csv},_torrents/{Completed,Watching/{$categories_csv}}}
> # Run the output of previous command
> mkdir -p "$root"/{Media,Staging}/YouTube/_archive
> mkdir -p "$root"/Personal/{Games/{Steam,'Steam Backup'},Pictures/{Synced/{'Camera Roll','Saved Pictures',Screenshots},Manual/'Camera Roll Archive'},Software/{Automatic,Manual}}
> mkdir -p "$root"/Scratch
>
> # May want to instead let permissions get managed by apps themselves when
> # they create these directories
> # Media
> sudo chown -R arr:service_rw "$root"/Media
> sudo chown -R ytdl:service_rw "$root"/Media/YouTube
> # Personal
> sudo chown -R hashhar:users "$root"/Personal # over SMB group is always users
> sudo chown -R syncthing:service_rw "$root"/Personal/Pictures/Synced
> # Staging
> sudo chown -R qbittorrent:service_rw "$root"/Staging
> sudo chown -R ytdl:service_rw "$root"/Staging/YouTube
> # Scratch
> sudo chown -R radon:users "$root"/Scratch # over SMB group is always users
> ```

### Directory Purposes

1.  `/Media`: Media root for apps like Plex.  
    Each subdirectory here is managed by a *arr app which moves files here from
    finished downloads from the matching subdirectory in `/Staging/Torrents`.
2.  `/Media/<category>/_torrents`: .torrent files for each category.  
    These are manually moved here to make sure we have the sources required to
    rebuild our media if needed.
3.  `/Media/YouTube`: Downloaded YouTube channels, playlists or videos.  
4.  `/Media/YouTube/_archive`: Archive files created by `youtube-dl`/`yt-dlp`,
    scripts and `youtube-dl` config files used for a particular download.

5.  `/Personal`: Manually managed personal data folder.
6.  `/Personal/Games/Steam`: Secondary Steam library folder with less played
    games network mapped to a PC.
7.  `/Personal/Games/Steam Backup`: Steam library backup created using Steam.
8.  `/Personal/Pictures/Manual`: Manually managed pictures directory.
9.  `/Personal/Pictures/Synced`: Syncthing managed pictures directory.
10. `/Personal/Software/Automatic`: Software downloaded and kept up to date
    programmatically.
11. `/Personal/Software/Manual`: Software downloaded and kept up to date
    manually.

12. `/Scratch`: This is a temporary workspace which can be used as needed.

13. `/Staging/Torrents`: Download root for torrent apps.  
    All torrent downloads get downloaded here into one of the subdirectories
    based on their category. This exactly mirrors the structure in `/Media` so
    that each of the *arr apps can move finished downloads to `/Media`.
14. `/Staging/YouTube`: In progress YouTube channel, playlist or video
    downloads.  
15. `/Staging/YouTube/_archive`: Archive files created by
    `youtube-dl`/`yt-dlp`, scripts and `youtube-dl` config files used for a
    particular download.
16. `/Staging/_torrents`: .torrent file root for torrent apps.  
    All .torrent files get placed here into `Completed` once downloaded.
    Any files placed into `Watching` get queued for downloads.

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

### Prerequisites

- Make sure your LAN is using `192.168.0.0/16` address space (i.e. subnet mask
  of `255.255.0.0`).
- Configure your DHCP server to only use `192.168.1.0/24` for the DHCP pool
  (i.e. `192.168.1.1` to `192.168.1.255`).

This will allow us to have clear identification of what network a device is on
by looking at the address and also make it easier to prevent IP collisions.

### Description

Any container running on the macvlan network cannot connect to the physical
host and neither can the physical host connect to the container on macvlan
network.  Also any other container not running on the macvlan network is not
routable from the macvlan network.

This means our reverse proxy will not be able to reach the Synology host nor
the other way around. Also any other containers running on Synology won't be
reachable from the reverse proxy making our reverse proxy pretty useless.

To solve this we create three networks:

- `192.168.1.0/24` - router's DHCP pool on which all home devices will live.
- `192.168.2.0/24` - macvlan network on Synology on which our reverse proxy
  container will live.
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

# Usage

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

## Environment Files

We have multiple environment files.

- `.env`: Contains variables we want to reference in the `docker-compose.yml`
  but not add to containers. Useful for extracting common paths and reusable
  values.
- `<service>/secrets.env`: Contains per-service environment variables injected
  into containers using `env_file` in `docker-compose.yml`. Useful for secrets.
  ***Define non-secret environment variables applicable to a single container
  using `environment` in `docker-compose.yml`.***

# Special Instructions

Some containers need a bit of manual setup which is described below.

## Caddy

Caddy requires some secrets to work. Make sure the following variables have values defined in `caddy/secrets.env`:

- `CF_API_TOKEN`: Cloudflare API token with read permissions for `Zone.Zone`
  and edit permissions for `Zone.DNS`.

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
