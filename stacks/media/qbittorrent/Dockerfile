# The only purpose of this image is to supply envsubst, which the
# custom-cont-init.d script needs to render qBittorrent.conf. Doing it here
# instead of `apk add` at container start removes a boot-time network
# dependency (which now routes through gluetun's VPN) and keeps the rootfs
# writable-free at init. No config or secrets are baked in.
#
# Keep the alpine version aligned with whatever the linuxserver base ships so
# the musl ABI matches.
FROM alpine:3.24 AS envsubst

RUN apk add --no-cache gettext-envsubst

FROM lscr.io/linuxserver/qbittorrent:5.2.3

COPY --from=envsubst /usr/bin/envsubst /usr/bin/envsubst
# envsubst is dynamically linked against libintl; the glob pulls in both the
# soname symlink and the library it points at.
COPY --from=envsubst /usr/lib/libintl.so.8* /usr/lib/
