#!/bin/sh
sed \
    -e "s|\${SMTP_FROM}|${SMTP_FROM}|g" \
    -e "s|\${SMTP_PASSWORD}|${SMTP_PASSWORD}|g" \
    -e "s|\${ALERT_EMAIL_TO}|${ALERT_EMAIL_TO}|g" \
    /etc/alertmanager/alertmanager.yml.tpl \
    > /tmp/alertmanager.yml

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml "$@"
