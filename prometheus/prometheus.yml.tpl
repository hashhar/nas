global:
  scrape_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "restic_rest_server"
    static_configs:
      - targets: ["restic-rest-server:${RESTIC_REST_SERVER_PORT}"]

  - job_name: "caddy"
    static_configs:
      - targets: ["caddy:80"]

  - job_name: "immich"
    static_configs:
      - targets: ["immich-server:8081"]
        labels:
          component: "api"
      - targets: ["immich-server:8082"]
        labels:
          component: "microservices"

  - job_name: "smartctl"
    scrape_interval: 60s
    static_configs:
      - targets: ["smartctl-exporter:9633"]

  - job_name: "node"
    static_configs:
      - targets: ["node-exporter:9100"]

storage:
  tsdb:
    retention:
      time: 90d
