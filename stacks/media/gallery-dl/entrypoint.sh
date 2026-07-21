#!/bin/sh

set -eu

if [ "$(id -u)" = '0' ]; then
  # Chown may fail, which may cause us to be unable to start; but maybe
  # it'll work anyway, so we let the error slide.
  chown "${PUID}:${PGID}" "${HOME}" || true
  exec su-exec "${PUID}:${PGID}" \
       env HOME="$HOME" "$@"
else
  exec "$@"
fi
