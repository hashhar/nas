ARG VERSION

FROM alpine:latest AS builder

ARG RESTIC_REST_SERVER_PORT

RUN apk add --no-cache gettext
COPY prometheus.yml prometheus.yml.tpl
RUN envsubst '${RESTIC_REST_SERVER_PORT}' < prometheus.yml.tpl > prometheus.yml

FROM prom/prometheus:${VERSION}

COPY --from=builder prometheus.yml /etc/prometheus/prometheus.yml

CMD [ "--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/prometheus", "--storage.tsdb.retention.time=90d" ]
