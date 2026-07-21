#!/bin/sh
# shellcheck disable=SC2086 # $STACKS is a space-separated list; splitting is intended
# Operate the per-stack compose projects under stacks/.
#
#   ./compose.sh networks              create the shared external networks (idempotent)
#   ./compose.sh decrypt               render every stacks/*/*/secrets.enc.env to a
#                                      plaintext secrets.env sibling (needs sops + age key)
#   ./compose.sh up|down|pull|ps|logs|build [stack...]
#                                      run the compose action on the given stacks,
#                                      or on all of them (ordered) when none given
#   ./compose.sh gallery-dl            one-shot gallery-dl run (media stack profile)
#
# Docker actions typically need root on the NAS: sudo ./compose.sh up
set -eu

cd "$(dirname "$0")"

# Synology's sudo PATH misses /usr/local/bin, where docker and sops live
PATH="$PATH:/usr/local/bin"

# infra first (reverse for down); everything else talks over infra's networks
STACKS="infra monitoring photos media sync"

usage() {
	sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'
	exit 1
}

compose() {
	stack=$1
	shift
	docker compose -f "stacks/$stack/docker-compose.yml" "$@"
}

cmd=${1:-}
[ -n "$cmd" ] || usage
shift

case "$cmd" in
networks)
	docker network inspect nas_macvlan >/dev/null 2>&1 || docker network create \
		--driver macvlan --opt parent=eth0 \
		--subnet 192.168.2.0/24 \
		nas_macvlan
	# Dynamic containers get IPs from the upper half; .0.x stays free for the
	# static pins (caddy .3, immich-redis .10, immich-database .11).
	docker network inspect nas_bridge >/dev/null 2>&1 || docker network create \
		--driver bridge \
		--subnet 172.18.0.0/16 --ip-range 172.18.128.0/17 \
		nas_bridge
	;;
decrypt)
	for enc in stacks/*/*/secrets.enc.env; do
		[ -e "$enc" ] || continue
		plain=${enc%secrets.enc.env}secrets.env
		sops decrypt "$enc" >"$plain.tmp"
		chmod 600 "$plain.tmp"
		mv "$plain.tmp" "$plain"
		echo "rendered $plain"
	done
	;;
up)
	[ $# -gt 0 ] || set -- $STACKS
	for stack in "$@"; do
		compose "$stack" up --build --detach
	done
	;;
down)
	[ $# -gt 0 ] || set -- $STACKS
	reversed=""
	for stack in "$@"; do
		reversed="$stack $reversed"
	done
	for stack in $reversed; do
		compose "$stack" down
	done
	;;
pull | ps | build)
	[ $# -gt 0 ] || set -- $STACKS
	for stack in "$@"; do
		echo "== $stack"
		compose "$stack" "$cmd"
	done
	;;
logs)
	[ $# -gt 0 ] || set -- $STACKS
	for stack in "$@"; do
		compose "$stack" logs
	done
	;;
gallery-dl)
	compose media --profile gallery-dl up --build gallery-dl
	;;
*)
	usage
	;;
esac
