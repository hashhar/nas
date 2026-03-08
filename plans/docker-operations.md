# Plan: Docker Operations

## Context

The NAS runs ~10 Docker services with a solid foundation, but several operational gaps remain: container logs can grow unboundedly, all services start together regardless of need, and there's no documented secrets template for new setups. This plan addresses those gaps.

---

## 3. Docker Logging Configuration

**Problem:** No Docker logging driver is explicitly configured. The default `json-file` driver has no size limits, meaning container logs can grow unboundedly and fill the disk.

**Recommendation:** Add a default logging config to all long-running services in `docker-compose.yml`:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

Alternatively, set it as the Docker daemon default in `/etc/docker/daemon.json` to apply globally without per-service config.

**Files:**
- `docker-compose.yml` — add `logging:` block to each service, or document the daemon-level config

---

## 12. Docker Compose Profiles for Optional Services

**Problem:** Gallery-dl uses a profile already, but other optional/development services don't. All services start together even if some aren't always needed.

**Recommendation:** Group services into profiles:
- `core`: Caddy, Plex, qBittorrent, Syncthing (always on)
- `monitoring`: Prometheus, Grafana, Alertmanager, node-exporter, smartctl-exporter
- `photos`: Immich stack
- `backup`: Restic REST server
- `tools`: gallery-dl, Dozzle, Uptime Kuma

Usage: `docker compose --profile core --profile monitoring up -d`

**Files:**
- `docker-compose.yml` — add `profiles:` to each service

---

## 14. `secrets.env.example` Templates

**Problem:** The `.env` file is committed (non-sensitive config), but `secrets.env` files are gitignored. A new setup requires reading the README to know what secrets to create.

**Recommendation:** Add `<service>.secrets.env.example` files for each service that has secrets. Example:
```
# caddy/secrets.env.example
CF_API_TOKEN=your-cloudflare-api-token-here
```

**Files:**
- New `<service>/secrets.env.example` for each service that has a gitignored `secrets.env`

---

## Verification

1. `docker compose config` — validate compose file syntax after logging changes
2. `docker compose --profile core up -d` — verify only core services start
3. `docker compose --profile monitoring up -d` — verify monitoring services start independently
4. After running with log limits: check `docker inspect <container> | grep LogConfig` to confirm limits are applied
5. Verify all `secrets.env.example` files exist for services that have gitignored secrets, and that they list all required variables
