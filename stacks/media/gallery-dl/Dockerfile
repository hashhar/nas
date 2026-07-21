FROM python:3.14-alpine

WORKDIR /download

RUN apk add --no-cache su-exec yt-dlp ffmpeg \
    && pip3 install --upgrade --no-cache-dir pip setuptools wheel \
    && pip3 install --no-cache-dir gallery-dl

ENV PUID=1000 PGID=1000 HOME=/var/gallery-dl

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh", "gallery-dl" ]
