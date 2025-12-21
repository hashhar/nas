Use the provided `collector.yaml` and place it in $DOCKER_DATA/scrutiny/config
to have the metrics get collected properly.

If the metrics are missing from the UI use
`sudo docker exec scrutiny /opt/scrutiny/bin/scrutiny-collector-metrics run` to
collect metrics on demand. By default it runs once per day.