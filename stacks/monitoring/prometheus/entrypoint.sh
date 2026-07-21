#!/bin/sh

set -e

sed "s|\${RESTIC_REST_SERVER_PORT}|$RESTIC_REST_SERVER_PORT|g" \
    /etc/prometheus/prometheus.yml.tpl > /etc/prometheus/prometheus.yml

exec /bin/prometheus "$@"
