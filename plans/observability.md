# Plan: Observability

## Context

The NAS already has Prometheus for metrics collection. This plan adds centralized log aggregation to complement metrics, enabling log searching, correlation across services, and log-based alerting — all from the Grafana UI.

---

## 8. Loki + Promtail for Log Aggregation

**Problem:** No centralized log viewing. Debugging requires SSH + `docker logs` per container. Logs aren't searchable or correlated.

**Recommendation:**
- Deploy [Loki](https://grafana.com/oss/loki/) (lightweight log aggregation, pairs with Grafana)
- Deploy Promtail as a sidecar to ship Docker container logs to Loki
- Add Loki as a Grafana datasource (once Grafana is deployed per existing plan)
- This enables log searching, filtering by service, and log-based alerting from one UI

**Files:**
- New `loki/` directory (config file)
- New `promtail/` directory (config file)
- `docker-compose.yml` — new `loki` and `promtail` services
- Grafana datasource provisioning config (once Grafana is set up)

---

## Verification

1. `docker compose config` — validate compose file syntax
2. `docker compose up --build -d` — deploy Loki and Promtail
3. `docker compose ps` — verify both containers are healthy
4. Open Grafana → Explore → select Loki datasource
5. Query `{container_name="caddy"}` and confirm recent log lines appear
6. Verify logs from at least 3 different services are visible and correctly labeled
7. Confirm log volume does not cause unexpected disk growth (check Loki retention config)
