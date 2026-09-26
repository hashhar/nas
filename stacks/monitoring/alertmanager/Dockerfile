FROM prom/alertmanager:v0.34.1

COPY alertmanager.yml /etc/alertmanager/alertmanager.yml.tpl
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
