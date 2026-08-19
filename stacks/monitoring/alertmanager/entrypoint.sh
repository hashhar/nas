#!/bin/sh
set -e
umask 077

sed \
    -e "s|\${SMTP_FROM}|${SMTP_FROM}|g" \
    -e "s|\${ALERT_EMAIL_TO}|${ALERT_EMAIL_TO}|g" \
    /etc/alertmanager/alertmanager.yml.tpl \
    > /tmp/alertmanager.yml

# Kept out of the rendered config entirely - smtp_auth_password_file points
# here instead, so /api/v2/status (which serves smtp_from/smtp_auth_username
# in cleartext to any tailnet peer) never has a password to redact.
printf '%s' "${SMTP_PASSWORD}" > /tmp/smtp_password

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml "$@"
