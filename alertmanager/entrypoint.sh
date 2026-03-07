#!/bin/sh
envsubst '${SMTP_FROM},${SMTP_PASSWORD},${ALERT_EMAIL_TO}' \
    < /etc/alertmanager/alertmanager.yml.tpl \
    > /tmp/alertmanager.yml

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml "$@"
