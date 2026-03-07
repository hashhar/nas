FROM alpine:3.23 AS builder

RUN apk add --no-cache gettext

FROM prom/alertmanager:v0.31.1

COPY --from=builder /usr/bin/envsubst /usr/bin/envsubst
COPY --from=builder /usr/lib/libintl.so.8 /usr/lib/libintl.so.8
COPY alertmanager.yml /etc/alertmanager/alertmanager.yml.tpl
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
