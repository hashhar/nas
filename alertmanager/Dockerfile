FROM prom/alertmanager:v0.32.0

COPY alertmanager.yml /etc/alertmanager/alertmanager.yml.tpl
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
