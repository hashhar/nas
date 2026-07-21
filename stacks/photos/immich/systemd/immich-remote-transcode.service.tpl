# System-level unit, not --user: a WSL2 distro started by Docker Desktop's
# background integration has no login session to hang a user unit off of.
[Unit]
Description=Immich remote transcode/microservices worker (NVENC)
After=docker.service mnt-data.mount tailscaled.service
Requires=docker.service
RequiresMountsFor=/mnt/data

[Service]
Type=oneshot
RemainAfterExit=yes
User=${DESKTOP_USER}
Environment=DESKTOP_IP=${DESKTOP_IP}
Environment=IMMICH_UPLOAD_LOCATION=${DATA_MOUNT}/Personal/Pictures/immich/upload
Environment=IMMICH_SYNCED_LIBRARY_LOCATION=${DATA_MOUNT}/Personal/Pictures/Synced
WorkingDirectory=${NAS_REPO_DIR}
ExecStart=/usr/sbin/docker compose -f stacks/photos/immich/docker-compose.remote-transcode.yml up -d
ExecStop=/usr/sbin/docker compose -f stacks/photos/immich/docker-compose.remote-transcode.yml down

[Install]
WantedBy=multi-user.target
