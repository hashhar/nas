FROM alpine:3.23 AS builder

ARG RESTIC_REST_SERVER_PORT

RUN apk add --no-cache gettext
COPY prometheus.yml prometheus.yml.tpl
RUN envsubst '${RESTIC_REST_SERVER_PORT}' < prometheus.yml.tpl > prometheus.yml

FROM prom/prometheus:v3.10.0

COPY --from=builder prometheus.yml /etc/prometheus/prometheus.yml
COPY alerts.yml /etc/prometheus/alerts.yml

CMD [ "--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/prometheus" ]
