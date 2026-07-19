# System-level unit, not --user: a WSL2 distro started by Docker Desktop's
# background integration has no login session to hang a user unit off of.
[Unit]
Description=Immich remote ML worker (CUDA)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=${DESKTOP_USER}
WorkingDirectory=${NAS_REPO_DIR}
ExecStart=/usr/sbin/docker compose -f immich/docker-compose.remote-ml-cuda.yml up -d
ExecStop=/usr/sbin/docker compose -f immich/docker-compose.remote-ml-cuda.yml down

[Install]
WantedBy=multi-user.target
