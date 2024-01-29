ARG VERSION
ARG CONFIG=/data/config

FROM alpine:latest AS builder

ARG DATA_ROOT
ARG LISTENING_PORT

RUN apk add --no-cache gettext

COPY ./qBittorrent.conf .
COPY ./categories.json .
COPY ./watched_folders.json .

ARG CONFIG
RUN mkdir -p ${CONFIG} \
  && export TORRENT_ROOT="${DATA_ROOT}/Staging" \
  && envsubst '${LISTENING_PORT},${TORRENT_ROOT}' < ./qBittorrent.conf > ${CONFIG}/qBittorrent.conf \
  && envsubst '${TORRENT_ROOT}' < ./categories.json > ${CONFIG}/categories.json \
  && envsubst '${TORRENT_ROOT}' < ./watched_folders.json > ${CONFIG}/watched_folders.json

FROM lscr.io/linuxserver/qbittorrent:${VERSION}

RUN apk add --no-cache rsync

COPY ./99-overwrite-config /etc/cont-init.d/99-overwrite-config

# Copy the generated config to some location, the 99-overwrite-config will
# replace the in-container config files with these on every start
ARG CONFIG
ENV DEFAULT_CONFIG=/default-config
COPY --from=builder ${CONFIG}/* ${DEFAULT_CONFIG}/
