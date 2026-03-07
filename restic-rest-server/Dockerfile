FROM restic/rest-server:0.14.0

RUN apk add --no-cache su-exec

ENV PUID=1000 PGID=1000 HOME=/var/restic

COPY su-exec-entrypoint.sh /su-exec-entrypoint.sh
ENTRYPOINT [ "/su-exec-entrypoint.sh", "/entrypoint.sh" ]
