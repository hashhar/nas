# Plan: Self-Hosted LLM (Open WebUI on NAS + Ollama on desktop GPU)

## Context

Add a self-hosted LLM chat setup on the NAS, with actual model inference
offloaded to the desktop (i9-13900k / RTX 4090 / 128 GB RAM). The NAS
(DS1821+, embedded Ryzen V1500B, no GPU) cannot run useful LLMs itself, so this
mirrors the pattern already established for Immich: a lightweight coordinator
container on the NAS, and a GPU worker on the desktop reached over the network
(commit `aebcc75`, `stacks/photos/immich/docker-compose.remote-*.yml`).

> **Layout note (post stacks restructure):** there is no longer a root
> `docker-compose.yml`. Open WebUI lands in its own new **`llm`** stack at
> `stacks/llm/docker-compose.yml` (`name: llm`), with its config dir at
> `stacks/llm/open-webui/`; the paths below are written accordingly.

**Architecture / components:**

| Component | Runs on | Role |
|-----------|---------|------|
| **Open WebUI** (`ghcr.io/open-webui/open-webui`) | NAS (bridge network) | Chat UI, user auth, chat history, RAG/doc upload. Holds no model weights. |
| **Ollama** (`ollama/ollama`) | Desktop (RTX 4090, WSL2) | Inference engine, GPU-accelerated. Serves models over its `:11434` API. |
| **Caddy** (existing) | NAS | Reverse-proxies `chat.nas.hashhar.com` / `.ts.hashhar.com` → Open WebUI. |

**Connection:** Open WebUI (NAS bridge) reaches Ollama at the desktop's LAN IP
`http://192.168.1.40:11434` — the same outbound-to-LAN path Immich uses to reach
the desktop ML worker at `:3003`.

**Decisions (confirmed with user):**
- Engine: **Ollama** (simplest model management, mirrors existing offload pattern).
- Desktop offline: **no LLM fallback** — Open WebUI stays up but lists no models
  until the desktop is on. No NAS CPU model, no Wake-on-LAN.
- Expose **Open WebUI only** (its OpenAI-compatible endpoint covers IDE/CLI use
  via an API key); do not proxy raw Ollama.

---

## 1. Open WebUI service on the NAS

**File:** `stacks/llm/docker-compose.yml` — new service on the bridge network,
modeled on the `immich-server` block in `stacks/photos/docker-compose.yml`.

```yaml
  open-webui:
    depends_on:
      caddy:
        condition: service_started
    image: ghcr.io/open-webui/open-webui:main   # plain image — NOT the :ollama bundle
    container_name: open-webui
    user: "$OPENWEBUI_UID:$OPENWEBUI_GID"
    environment:
      # Desktop RTX 4090 Ollama, reached over the LAN (same path immich uses for :3003).
      # When the desktop is off, Open WebUI simply lists no models.
      - OLLAMA_BASE_URL=http://192.168.1.40:11434
      - WEBUI_URL=https://chat.nas.hashhar.com
      - TZ=$TZ
    env_file:
      - open-webui/secrets.env
    volumes:
      - $DOCKER_DATA/open-webui/data:/app/backend/data
      - /etc/localtime:/etc/localtime:ro
    networks:
      - bridge   # external nas_bridge; dynamic IP — no pin (bridge --ip-range keeps dynamic off the pinned range)
    restart: unless-stopped
```

No `ports:` mapping — Caddy proxies over the bridge by container name. The
`llm` stack references the shared external networks the same way every other
stack does (`bridge: {external: true, name: nas_bridge}`).

## 2. Ollama worker on the desktop (overlay compose + systemd)

Modeled directly on `stacks/photos/immich/docker-compose.remote-ml-cuda.yml`
and its systemd template. Simpler than the Immich worker because Ollama needs
**no** access back to the NAS (no DB/Redis/secrets) — the NAS reaches *it*.

**New file:** `stacks/llm/open-webui/docker-compose.remote-ollama.yml`

```yaml
name: ollama_remote
services:
  ollama:
    container_name: ollama_remote
    image: ollama/ollama:latest
    volumes:
      - ollama-models:/root/.ollama   # model weights live on the desktop's fast disk
    restart: unless-stopped
    ports:
      - 11434:11434
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu, compute, utility]
volumes:
  ollama-models:
# Pinned outside 172.16.0.0/12 to avoid colliding with the NAS bridge routed
# over Tailscale (same rationale as the immich remote overlays).
networks:
  default:
    ipam:
      config:
        - subnet: 10.102.0.0/24
```

**New file:** `stacks/llm/open-webui/systemd/ollama-remote.service.tpl` — copy
`stacks/photos/immich/systemd/immich-remote-ml.service.tpl`, drop the
data-mount/Tailscale requirements (Ollama needs neither), point `ExecStart` at
the new overlay:

```ini
[Unit]
Description=Ollama LLM worker (RTX 4090)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=${DESKTOP_USER}
WorkingDirectory=${NAS_REPO_DIR}
ExecStart=/usr/sbin/docker compose -f stacks/llm/open-webui/docker-compose.remote-ollama.yml up -d
ExecStop=/usr/sbin/docker compose -f stacks/llm/open-webui/docker-compose.remote-ollama.yml down

[Install]
WantedBy=multi-user.target
```

Models are pulled once with `docker exec ollama_remote ollama pull <model>`
(e.g. `llama3.1:8b`, `qwen2.5-coder:14b`) — the RTX 4090's 24 GB comfortably
runs up to ~30B-class quantized models.

## 3. Caddy — expose `chat.nas.hashhar.com` (three coordinated edits)

**File:** `stacks/infra/caddy/Caddyfile` and the caddy `environment:` block in
`stacks/infra/docker-compose.yml`.

1. `stacks/infra/docker-compose.yml` caddy `environment:` — add
   `OPENWEBUI_PORT=8080` (Open WebUI's internal listen port).
2. `stacks/infra/caddy/Caddyfile` allowlist map — add `~(chat)\..* "yes"`.
3. `stacks/infra/caddy/Caddyfile` route block — add
   `import proxy-host "chat" "http://open-webui:{$OPENWEBUI_PORT}"`.

## 4. Config wiring (`.env`, secrets, user/group)

**`.env`** — new block following the existing convention in the root `.env`
(each stack symlinks it, so the `llm` stack picks these up automatically):
```
# open-webui:service_rw
OPENWEBUI_UID='<new dedicated Synology UID>'
OPENWEBUI_GID='65539'   # service_rw
# Also used by caddy
OPENWEBUI_PORT='8080'
```

**New file:** `stacks/llm/open-webui/secrets.enc.env` — SOPS+age-encrypted (no
`.example` files under the new convention; the encrypted file's variable names
are the self-documenting template). Create a plaintext `secrets.env` with the
variable below, then
`sops encrypt --filename-override stacks/llm/open-webui/secrets.enc.env stacks/llm/open-webui/secrets.env > stacks/llm/open-webui/secrets.enc.env`.
`./compose.sh decrypt` renders the gitignored plaintext at deploy time.
```
# Signs Open WebUI session JWTs. Generate with: openssl rand -hex 32
WEBUI_SECRET_KEY=change-me
```

**Synology user/group:** create a dedicated `open-webui` user with the new UID,
member of the `service_rw` group (GID 65539). It only writes its own appdata
dir (`$DOCKER_DATA/open-webui`), so no shared-data-share access is needed.
Auth is Open WebUI's built-in multi-user login (first signup becomes admin);
disable open signup after creating accounts.

## 5. Documentation & tooling sync (required by CLAUDE.md)

- **`README.md`** — add a `### Open WebUI` entry under *Special Instructions*
  documenting `WEBUI_SECRET_KEY`; add the `open-webui` user to the Users table;
  add a setup section (mirroring the Immich remote-worker section in README)
  covering: desktop prerequisites (Docker Desktop + WSL2 + NVIDIA driver 545+,
  reused from the Immich setup), rendering/enabling the systemd unit with
  `envsubst` (`DESKTOP_USER`, `NAS_REPO_DIR`, `DESKTOP_IP`), pulling models, and
  the "no models when desktop off" behavior.
- **`.github/dependabot.yml`** — add `/stacks/llm` to the `docker-compose`
  ecosystem (covers the `open-webui` NAS image in `stacks/llm/docker-compose.yml`)
  and `/stacks/llm/open-webui` so the `ollama/ollama` remote-overlay image is
  tracked too (same pattern as `/stacks/photos/immich`). No custom Dockerfile is
  added, so the `docker` ecosystem is untouched.
- **Monitoring:** intentionally **out of scope** — neither Ollama nor Open WebUI
  exports Prometheus metrics natively, and scraping the frequently-offline
  desktop would trip the existing `TargetDown` alert. Noted so it isn't missed.

---

## Verification

1. `docker compose -f stacks/llm/docker-compose.yml config` and
   `docker compose -f stacks/infra/docker-compose.yml config` — validate the new
   `llm` stack parses and the caddy env var addition in `infra` is picked up.
2. On the desktop: render the unit
   (`envsubst '$DESKTOP_USER,$NAS_REPO_DIR' < stacks/llm/open-webui/systemd/ollama-remote.service.tpl`),
   `systemctl enable --now ollama-remote`, then
   `docker exec ollama_remote ollama pull llama3.1:8b` and
   `curl http://192.168.1.40:11434/api/tags` from the NAS to confirm reachability.
3. On the NAS: `sudo ./compose.sh up llm infra` and `./compose.sh ps llm infra`
   — open-webui and caddy both healthy.
4. Browse `https://chat.nas.hashhar.com` (LAN) and
   `https://chat.nas.ts.hashhar.com` (Tailscale) — Open WebUI loads with valid
   TLS; create the admin account.
5. In Open WebUI, confirm the pulled model appears in the model dropdown and a
   chat completes (proves NAS→desktop Ollama path works).
6. Stop the desktop worker (`systemctl stop ollama-remote`) — Open WebUI still
   loads but lists no models (confirms graceful offline behavior).
